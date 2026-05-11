import os
import subprocess
import sys
import time
import json
import base64
import re
import asyncio

def install_dependencies():
    print("Memeriksa dan menginstal library pendukung...")
    try:
        import transformers
        import playwright
        import bitsandbytes
        import accelerate
        import nest_asyncio
    except ImportError:
        print("Menginstal library: transformers, bitsandbytes, accelerate, playwright, nest_asyncio, ipython...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers", "bitsandbytes", "accelerate", "playwright", "nest_asyncio", "ipython"])
        print("Menginstal browser Playwright...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install-deps", "chromium"])
        print("Instalasi selesai! (Anda mungkin perlu me-restart session/kernel jika error)")

install_dependencies()

# Import nest_asyncio to allow asyncio in Colab/Jupyter loops
import nest_asyncio
nest_asyncio.apply()

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from playwright.async_api import async_playwright
from IPython.display import display, Image, clear_output, HTML

# -----------------
# 1. SETUP MODEL AI
# -----------------
model_id = "unsloth/Llama-3.1-8B-Instruct-bnb-4bit"

tokenizer = None
model = None
pipe = None

def setup_ai():
    global tokenizer, model, pipe
    if pipe is not None:
        return
    print("Lagi masukin otak AI ke VRAM... Tunggu bentar cuy.")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
    )
    print("Otak AI sudah terpasang di GPU!")

# -----------------
# 2. BROWSER UTILS
# -----------------

JS_EXTRACT_DOM = """
() => {
    let elements = [];
    let id_counter = 0;

    // Helper to check if element is visible
    function isVisible(e) {
        return !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && window.getComputedStyle(e).visibility !== 'hidden';
    }

    // Traverse DOM
    document.querySelectorAll('*').forEach(el => {
        if (!isVisible(el)) return;

        let isInteractable = false;
        const tag = el.tagName.toLowerCase();
        const role = el.getAttribute('role');

        if (['a', 'button', 'input', 'select', 'textarea'].includes(tag) ||
            el.onclick != null ||
            role === 'button' || role === 'link' ||
            window.getComputedStyle(el).cursor === 'pointer') {
            isInteractable = true;
        }

        if (isInteractable) {
            let text = el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.alt || "";
            text = text.replace(/\\n/g, ' ').trim().substring(0, 50);

            if (text) {
                // Add bounding rect for clicking later
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    elements.push({
                        id: id_counter++,
                        tag: tag,
                        text: text,
                        x: rect.left + rect.width / 2,
                        y: rect.top + rect.height / 2
                    });
                }
            }
        }
    });

    return elements;
}
"""

class BrowserEnv:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.interactable_elements = []

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        )
        self.page = await self.context.new_page()

    async def get_state(self):
        if not self.page:
            return "Browser belum dimulai.", [], None

        url = self.page.url
        title = await self.page.title()

        # Ambil screenshot
        screenshot_bytes = await self.page.screenshot(type='jpeg', quality=60)

        # Ekstrak elemen interactable
        elements = await self.page.evaluate(JS_EXTRACT_DOM)
        self.interactable_elements = elements

        dom_text = f"URL saat ini: {url}\nJudul: {title}\nElemen yang bisa diklik:\n"
        for el in elements:
            dom_text += f"[{el['id']}] {el['tag'].upper()}: {el['text']}\n"

        return dom_text, elements, screenshot_bytes

    async def execute_action(self, action_type, arg1=None, arg2=None):
        try:
            if action_type == "GOTO":
                url = arg1
                if not url.startswith("http"):
                    url = "https://" + url
                await self.page.goto(url, timeout=30000, wait_until="domcontentloaded")
                # Wait sedikit untuk JS rendering
                await self.page.wait_for_timeout(2000)
                return f"Berhasil pergi ke {url}"

            elif action_type == "CLICK":
                el_id = int(arg1)
                el = next((e for e in self.interactable_elements if e['id'] == el_id), None)
                if el:
                    await self.page.mouse.click(el['x'], el['y'])
                    await self.page.wait_for_timeout(2000)
                    return f"Berhasil klik elemen [{el_id}]"
                else:
                    return f"Error: Elemen dengan ID {el_id} tidak ditemukan di halaman."

            elif action_type == "TYPE":
                el_id = int(arg1)
                text_to_type = arg2
                el = next((e for e in self.interactable_elements if e['id'] == el_id), None)
                if el:
                    await self.page.mouse.click(el['x'], el['y'])
                    await self.page.wait_for_timeout(500)
                    await self.page.keyboard.type(text_to_type)
                    await self.page.keyboard.press("Enter")
                    await self.page.wait_for_timeout(2000)
                    return f"Berhasil mengetik '{text_to_type}' pada elemen [{el_id}]"
                else:
                    return f"Error: Elemen dengan ID {el_id} tidak ditemukan."

            elif action_type == "SCROLL_DOWN":
                await self.page.mouse.wheel(0, 600)
                await self.page.wait_for_timeout(1000)
                return "Berhasil scroll ke bawah."

            elif action_type == "DONE":
                return "Tugas dinyatakan selesai oleh AI."

            else:
                return f"Error: Aksi tidak dikenal: {action_type}"

        except Exception as e:
            return f"Error saat menjalankan {action_type}: {str(e)}"

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


# -----------------
# 3. AGENT LOGIC
# -----------------
SYSTEM_PROMPT = """Anda adalah AI Browser Agent yang cerdas. Anda dapat menavigasi web untuk menyelesaikan tugas pengguna.
Anda menerima status halaman web (URL, Judul, dan Elemen Interaktif bernomor).
Anda harus merespons dengan format JSON yang ketat.

Tersedia Aksi:
1. GOTO: Pergi ke URL. (Argumen: url)
2. CLICK: Klik elemen berdasarkan ID. (Argumen: id)
3. TYPE: Ketik teks ke elemen berdasarkan ID. (Argumen: id, text)
4. SCROLL_DOWN: Gulir ke bawah halaman. (Argumen: tidak ada)
5. DONE: Selesaikan tugas. (Argumen: hasil atau kesimpulan)

Contoh Respons JSON:
{
  "thought": "Saya perlu mencari informasi di Wikipedia, saya akan pergi ke google.com",
  "action": "GOTO",
  "arg1": "google.com",
  "arg2": ""
}

{
  "thought": "Ada kotak pencarian dengan ID 5. Saya akan mengetik 'Berita AI hari ini'.",
  "action": "TYPE",
  "arg1": "5",
  "arg2": "Berita AI hari ini"
}

{
  "thought": "Saya sudah menemukan jawabannya. Tugas selesai.",
  "action": "DONE",
  "arg1": "Berita AI terbaru adalah...",
  "arg2": ""
}

PERINGATAN:
- HANYA keluarkan JSON yang valid, tanpa teks tambahan di luar JSON.
- Pastikan mematuhi nama action yang ada.
- Gunakan bahasa Indonesia untuk "thought".
"""

def parse_ai_response(response_text):
    # Mencoba mengekstrak blok JSON jika model memberikan teks ekstra (markdown)
    match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if match:
        json_str = match.group(0)
    else:
        json_str = response_text

    try:
        data = json.loads(json_str)
        return data
    except Exception as e:
        return {"error": "Format respons tidak valid. Harus berupa JSON.", "raw": response_text}

def get_ai_decision(task, history, current_state):
    prompt_history = "\n".join(history[-3:]) # Ambil 3 history terakhir untuk konteks

    user_prompt = f"""Tugas: {task}

Sejarah langkah sebelumnya:
{prompt_history if prompt_history else "Belum ada aksi."}

Status Halaman Saat Ini:
{current_state}

Tentukan langkah selanjutnya, balas HANYA dengan format JSON."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    # Text generation dengan Llama 3.1 Instruct
    outputs = pipe(
        messages,
        max_new_tokens=256,
        do_sample=False,
    )

    response_text = outputs[0]["generated_text"][-1]["content"]
    return parse_ai_response(response_text)


# -----------------
# 4. COLAB UI & MAIN LOOP
# -----------------
def render_dashboard(task, thought, action_str, screenshot_bytes, history_log):
    clear_output(wait=True)
    html_content = f"""
    <div style="font-family: Arial, sans-serif; padding: 15px; border: 1px solid #ddd; border-radius: 8px; max-width: 800px; margin: 0 auto; background-color: #f9f9f9;">
        <h2 style="color: #333; margin-top: 0;">🤖 AI Browser Agent</h2>
        <div style="background-color: #fff; padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 5px solid #2196F3;">
            <strong>🎯 Tugas:</strong> {task}
        </div>
        <div style="background-color: #fff; padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 5px solid #FF9800;">
            <strong>🧠 Pemikiran AI:</strong> {thought}
        </div>
        <div style="background-color: #fff; padding: 10px; border-radius: 5px; margin-bottom: 15px; border-left: 5px solid #4CAF50;">
            <strong>⚡ Aksi Saat Ini:</strong> {action_str}
        </div>
        <div style="margin-bottom: 15px;">
            <strong>🖥️ Layar Browser:</strong><br/>
    """
    display(HTML(html_content))
    if screenshot_bytes:
        display(Image(data=screenshot_bytes, width=800))

    log_html = "<div style='font-size: 12px; color: #666; margin-top: 15px;'><strong>Log Langkah Terakhir:</strong><ul>"
    for log in history_log[-5:]:
        log_html += f"<li>{log}</li>"
    log_html += "</ul></div></div>"
    display(HTML(log_html))


async def run_agent(task, max_steps=15):
    setup_ai()

    env = BrowserEnv()
    await env.start()

    history = []

    try:
        for step in range(max_steps):
            dom_text, elements, screenshot = await env.get_state()

            # Tampilkan dashboard dengan status sedang berpikir
            render_dashboard(task, "Menganalisis halaman dan merencanakan...", "Menunggu keputusan AI...", screenshot, history)

            # Meminta AI membuat keputusan
            decision = get_ai_decision(task, history, dom_text)

            if "error" in decision:
                history.append(f"AI Error: {decision['error']} - {decision.get('raw', '')}")
                thought = "Saya membuat kesalahan format JSON, mencoba lagi."
                action_str = "Koreksi format respons"
                render_dashboard(task, thought, action_str, screenshot, history)
                continue

            thought = decision.get("thought", "Tidak ada pemikiran.")
            action = decision.get("action", "")
            arg1 = decision.get("arg1", "")
            arg2 = decision.get("arg2", "")

            action_str = f"{action} ({arg1}, {arg2})"

            # Update dashboard dengan keputusan AI
            render_dashboard(task, thought, action_str, screenshot, history)

            if action == "DONE":
                history.append(f"Selesai! Hasil: {arg1}")
                render_dashboard(task, thought, f"TUGAS SELESAI: {arg1}", screenshot, history)
                print(f"\n✅ AI Menyelesaikan Tugas: {arg1}")
                break

            # Mengeksekusi aksi
            action_result = await env.execute_action(action, arg1, arg2)
            history.append(f"Aksi: {action_str} -> Hasil: {action_result}")

    except Exception as e:
        print(f"Error pada loop utama: {e}")
    finally:
        await env.close()

# Fungsi utama untuk dipanggil pengguna di sel Colab
def jalankan_ai(tugas, max_steps=15):
    # Mengelola event loop di lingkungan Colab/Jupyter Notebook
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # Karena nest_asyncio sudah di-apply, kita buat task
        task_coro = loop.create_task(run_agent(tugas, max_steps))
        return task_coro
    else:
        asyncio.run(run_agent(tugas, max_steps))

if __name__ == "__main__":
    print("Modul AI Browser Agent berhasil dimuat!")
    print("Cara penggunaan di sel Colab Anda:")
    print("-----------------------------------")
    print("import main")
    print("await main.jalankan_ai('Cari informasi tentang teknologi AI terbaru hari ini')")
    print("-----------------------------------")
