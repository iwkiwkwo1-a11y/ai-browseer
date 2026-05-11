import asyncio
import io
import aiohttp
from pypdf import PdfReader
from playwright.async_api import async_playwright

JS_EXTRACT_DOM = r"""
() => {
    let elements = [];
    let id_counter = 0;

    function isVisible(e) {
        return !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && window.getComputedStyle(e).visibility !== 'hidden';
    }

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
            text = text.replace(/\n/g, ' ').trim().substring(0, 50);

            if (text) {
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

# Script kecil untuk membantu menghindari deteksi bot sederhana
STEALTH_SCRIPT = r"""
() => {
    Object.defineProperty(navigator, 'webdriver', {
      get: () => undefined
    });
}
"""

import os

class BrowserEnv:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.pages = []  # List untuk menyimpan multiple tabs
        self.interactable_elements = []

    async def start(self):
        self.playwright = await async_playwright().start()
        # Menggunakan chromium biasa namun dengan argumen tambahan untuk stealth
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--no-sandbox'
            ]
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # Injeksi stealth script ke setiap halaman baru
        await self.context.add_init_script(STEALTH_SCRIPT)
        self.page = await self.context.new_page()
        self.pages.append(self.page)

    async def get_state(self):
        if not self.page:
            return "Browser belum dimulai.", [], None

        # Pengecekan tab aktif
        try:
            url = self.page.url
            title = await self.page.title()
            screenshot_bytes = await self.page.screenshot(type='jpeg', quality=60)
        except Exception:
            # Jika tab terlanjur tertutup/mati, kembalikan ke tab sebelumnya jika ada
            if self.pages and len(self.pages) > 0:
                self.page = self.pages[-1]
                url = self.page.url
                title = await self.page.title()
                screenshot_bytes = await self.page.screenshot(type='jpeg', quality=60)
            else:
                return "Semua tab tertutup.", [], None

        # Ekstrak elemen interactable
        elements = await self.page.evaluate(JS_EXTRACT_DOM)
        self.interactable_elements = elements

        # Informasi Tab Aktif
        current_tab_idx = self.pages.index(self.page) if self.page in self.pages else 0
        total_tabs = len(self.pages)

        # Batasi agar tidak OOM (Out of Memory)
        MAX_ELEMENTS = 75
        limited_elements = elements[:MAX_ELEMENTS]

        dom_text = f"=== STATUS BROWSER ===\nTab Aktif: [{current_tab_idx + 1} dari {total_tabs}]\nURL saat ini: {url}\nJudul: {title}\n\nElemen yang bisa diklik (Maks {MAX_ELEMENTS}):\n"
        if not limited_elements:
            dom_text += "Tidak ada elemen interaktif yang ditemukan."
        for el in limited_elements:
            dom_text += f"[{el['id']}] {el['tag'].upper()}: {el['text']}\n"

        if len(elements) > MAX_ELEMENTS:
            dom_text += f"... (Ada {len(elements) - MAX_ELEMENTS} elemen lain disembunyikan agar memori aman. Gunakan SCROLL_DOWN jika perlu)\n"

        return dom_text, elements, screenshot_bytes

    async def execute_action(self, action_type, arg1=None, arg2=None):
        try:
            if action_type == "GOTO":
                url = arg1
                if not url.startswith("http"):
                    url = "https://" + url
                await self.page.goto(url, timeout=45000, wait_until="domcontentloaded")
                await asyncio.sleep(2) # Kasih napas
                return f"Berhasil pergi ke {url}"

            elif action_type == "CLICK":
                try:
                    el_id = int(arg1)
                except:
                    return "Error: arg1 harus berupa angka ID."

                el = next((e for e in self.interactable_elements if e['id'] == el_id), None)
                if el:
                    await self.page.mouse.click(el['x'], el['y'])
                    await asyncio.sleep(3) # Kasih napas nunggu efek klik
                    return f"Berhasil klik elemen [{el_id}] ({el['text']})"
                else:
                    return f"Error: Elemen ID {el_id} tidak ditemukan."

            elif action_type == "TYPE":
                try:
                    el_id = int(arg1)
                except:
                    return "Error: arg1 harus berupa angka ID."

                text_to_type = arg2
                el = next((e for e in self.interactable_elements if e['id'] == el_id), None)
                if el:
                    await self.page.mouse.click(el['x'], el['y'])
                    await asyncio.sleep(0.5)
                    await self.page.keyboard.type(text_to_type, delay=50) # Ketik layaknya manusia
                    await self.page.keyboard.press("Enter")
                    await asyncio.sleep(3)
                    return f"Berhasil mengetik '{text_to_type}' pada elemen [{el_id}]"
                else:
                    return f"Error: Elemen ID {el_id} tidak ditemukan."

            elif action_type == "SCROLL_DOWN":
                await self.page.mouse.wheel(0, 600)
                await asyncio.sleep(2)
                return "Berhasil scroll ke bawah."

            elif action_type == "GO_BACK":
                await self.page.go_back(wait_until="domcontentloaded")
                await asyncio.sleep(2)
                return "Berhasil mundur ke halaman sebelumnya."

            elif action_type == "PRESS_KEY":
                key = arg1 # misal "Escape", "Enter", "Tab"
                await self.page.keyboard.press(key)
                await asyncio.sleep(2)
                return f"Berhasil menekan tombol {key}"

            elif action_type == "WAIT":
                sec = 3
                if arg1:
                    try:
                        sec = int(arg1)
                    except:
                        pass
                await asyncio.sleep(sec)
                return f"Berhasil diam menunggu selama {sec} detik."

            elif action_type == "EXTRACT_TEXT":
                # Ekstrak semua teks bacaan di halaman (hanya teks yang terlihat)
                text_content = await self.page.evaluate('''() => {
                    return document.body.innerText;
                }''')
                # Bersihkan spasi kosong dan batasi panjang teks (limit keras agar tidak OOM)
                clean_text = ' '.join(text_content.split())
                return clean_text[:1200] + ("..." if len(clean_text) > 1200 else "")

            elif action_type == "NEW_TAB":
                url = arg1
                if url and not url.startswith("http"):
                    url = "https://" + url
                new_page = await self.context.new_page()
                self.pages.append(new_page)
                self.page = new_page # Pindah fokus
                if url:
                    await self.page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                    return f"Berhasil membuka tab baru dan pergi ke {url}."
                return "Berhasil membuka tab kosong baru."

            elif action_type == "SWITCH_TAB":
                try:
                    tab_index = int(arg1) - 1 # Agent pakai 1-based index
                    if 0 <= tab_index < len(self.pages):
                        self.page = self.pages[tab_index]
                        await self.page.bring_to_front()
                        await asyncio.sleep(1)
                        return f"Berhasil pindah ke Tab {tab_index + 1} ({self.page.url})."
                    else:
                        return f"Error: Tab {tab_index + 1} tidak ada. Total tab: {len(self.pages)}."
                except:
                    return "Error: arg1 harus berupa nomor tab."

            elif action_type == "CLOSE_TAB":
                if len(self.pages) > 1:
                    await self.page.close()
                    self.pages.remove(self.page)
                    self.page = self.pages[-1] # Fokus ke tab terakhir
                    await self.page.bring_to_front()
                    return "Tab saat ini ditutup. Fokus kembali ke tab sebelumnya."
                else:
                    return "Gagal menutup tab. Ini adalah tab terakhir."

            elif action_type == "SCROLL_TO_TEXT":
                search_text = arg1
                if not search_text:
                    return "Error: arg1 (teks pencarian) kosong."

                # Injeksi JS untuk mencari teks dan men-scroll
                found = await self.page.evaluate(f'''(text) => {{
                    let elements = Array.from(document.body.querySelectorAll("*:not(script):not(style)"));
                    for (let el of elements) {{
                        if (el.children.length === 0 && el.textContent.toLowerCase().includes(text.toLowerCase())) {{
                            el.scrollIntoView({{behavior: "smooth", block: "center"}});
                            return true;
                        }}
                    }}
                    return false;
                }}''', search_text)
                await asyncio.sleep(2)
                if found:
                    return f"Berhasil menemukan dan scroll ke bagian teks '{search_text}'."
                else:
                    return f"Teks '{search_text}' tidak ditemukan di halaman ini."

            elif action_type == "SAVE_REPORT":
                filename = arg1 if arg1 else "report.txt"
                content = arg2 if arg2 else ""

                # Mencegah escape/directory traversal
                filename = filename.replace("/", "_").replace("\\\\", "_")
                if not filename.endswith((".txt", ".md", ".csv")):
                    filename += ".md"

                filepath = os.path.join(os.getcwd(), filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Berhasil menyimpan laporan ke file: {filepath}"

            elif action_type == "READ_PDF":
                pdf_url = arg1
                if not pdf_url:
                    return "Error: URL PDF tidak diberikan."

                if not pdf_url.startswith("http"):
                    pdf_url = "https://" + pdf_url

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(pdf_url, timeout=30) as resp:
                            if resp.status == 200:
                                pdf_data = await resp.read()
                                reader = PdfReader(io.BytesIO(pdf_data))
                                text = ""
                                # Baca maksimal 5 halaman pertama untuk mencegah context overflow
                                max_pages = min(5, len(reader.pages))
                                for i in range(max_pages):
                                    page_text = reader.pages[i].extract_text()
                                    if page_text:
                                        text += page_text + " "

                                clean_text = ' '.join(text.split())
                                return clean_text[:1500] + ("..." if len(clean_text) > 1500 else "")
                            else:
                                return f"Error mengunduh PDF, HTTP status: {resp.status}"
                except Exception as e:
                    return f"Gagal membaca PDF: {str(e)}"

            elif action_type == "DONE":
                return "Tugas dinyatakan selesai oleh AI."

            else:
                return f"Error: Aksi tidak dikenal: {action_type}"

        except Exception as e:
            # Jika error (misal timeout), paksa kasih napas sebentar
            await asyncio.sleep(2)
            return f"Error saat menjalankan {action_type}: {str(e)}"

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
