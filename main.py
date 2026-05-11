import os
import subprocess
import sys
import asyncio
import time

def check_and_install_deps():
    print("[SYSTEM] Memeriksa dependensi...")
    try:
        import transformers
        import playwright
        import bitsandbytes
        import accelerate
        import nest_asyncio
        import IPython
        import pypdf
        import aiohttp
    except ImportError:
        print("[SYSTEM] Menginstal dependensi (transformers, playwright, pypdf, aiohttp, etc)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-U",
                               "transformers", "bitsandbytes", "accelerate",
                               "playwright", "nest_asyncio", "ipython", "pypdf", "aiohttp"])
        print("[SYSTEM] Menginstal Chromium untuk Playwright...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install-deps", "chromium"])
        print("\n=======================================================")
        print("INSTALASI SELESAI. HARAP RESTART SESSION/RUNTIME COLAB ANDA!")
        print("Lalu jalankan ulang sel ini.")
        print("=======================================================\n")
        sys.exit()

# Jalankan instalasi jika belum ada
check_and_install_deps()

# Terapkan nest_asyncio agar asyncio berjalan mulus di Jupyter/Colab loop
import nest_asyncio
nest_asyncio.apply()

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# Import modul internal
from core.browser import BrowserEnv
from core.agent import BrowserAgent
from core.ui import render_terminal_ui

# Setup Global AI
pipe = None

def load_ai_model():
    global pipe
    if pipe is not None:
        return pipe

    print("[SYSTEM] Memuat Model Qwen-2.5-7B-Instruct (Tunggu sebentar)...")
    # Menggunakan Qwen-2.5-7B versi 4-bit agar muat di Google Colab T4
    model_id = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"

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
    print("[SYSTEM] Model berhasil dimuat ke VRAM GPU!")
    return pipe

async def run_loop(task, max_steps=15):
    pipe = load_ai_model()
    agent = BrowserAgent(pipe)

    env = BrowserEnv()
    await env.start()

    history = []
    action_result = "Browser baru saja dibuka."

    try:
        for step in range(1, max_steps + 1):
            dom_text, elements, screenshot = await env.get_state()

            # Mempersiapkan state UI kosong
            ui_state = {
                "reflection": "...",
                "plan": agent.current_plan,
                "memory": agent.current_memory,
                "thought": "Membaca DOM dan Memikirkan langkah selanjutnya..."
            }

            # Tampilkan ke UI sebelum diproses (Status: Thinking)
            render_terminal_ui(task, step, max_steps, ui_state, "...", action_result, screenshot)

            # Agent mengambil keputusan
            decision = agent.get_decision(task, history, dom_text)

            # Validasi Error parsing
            if "error" in decision:
                action_result = f"Error dari AI: {decision['error']}"
                history.append(f"AI ERROR: {decision['error']}")
                ui_state["thought"] = "Gagal memproses JSON. Mencoba lagi."
                render_terminal_ui(task, step, max_steps, ui_state, "Koreksi JSON", action_result, screenshot)
                await asyncio.sleep(2)
                continue

            thought = decision.get("thought", "Tidak ada thought")
            action = decision.get("action", "")
            args = decision.get("args", {})

            ui_state = decision
            ui_state["plan"] = agent.current_plan
            ui_state["memory"] = agent.current_memory

            # Format Argumen menjadi string rapi
            if isinstance(args, dict):
                args_str = ", ".join([f"{k}={v}" for k, v in args.items()])
            else:
                args_str = str(args)

            action_str = f"{action}({args_str})"

            # Update UI dengan keputusan sebelum eksekusi
            render_terminal_ui(task, step, max_steps, ui_state, action_str, "Mengeksekusi...", screenshot)

            # Eksekusi DONE
            if action == "DONE":
                final_res = args.get("result", "")
                render_terminal_ui(task, step, max_steps, ui_state, "SELESAI", f"Tugas Selesai: {final_res}", screenshot)
                print(f"\n✅ [AI SELESAI] Hasil: {final_res}")
                break

            # Eksekusi di Browser
            # Menyusun argument untuk execute_action dari BrowserEnv
            arg1, arg2 = None, None
            if action == "GOTO":
                arg1 = args.get("url")
            elif action == "CLICK":
                arg1 = args.get("id")
            elif action == "TYPE":
                arg1 = args.get("id")
                arg2 = args.get("text")
            elif action == "PRESS_KEY":
                arg1 = args.get("key")
            elif action == "WAIT":
                arg1 = args.get("seconds")
            elif action == "EXTRACT_TEXT":
                pass # tidak butuh args
            elif action == "READ_PDF":
                arg1 = args.get("url")

            action_result = await env.execute_action(action, arg1, arg2)

            # Catat history (Penting agar tidak looping)
            history.append(f"Aksi: {action_str} -> Hasil: {action_result}")

    except Exception as e:
        print(f"\n❌ [SYSTEM ERROR] {str(e)}")
    finally:
        await env.close()

def run(task, max_steps=20):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        task_coro = loop.create_task(run_loop(task, max_steps))
        return task_coro
    else:
        asyncio.run(run_loop(task, max_steps))

if __name__ == "__main__":
    print("[SYSTEM] Modul Utama Berhasil Diinisialisasi.")
    print("Cara Pakai di Colab:")
    print("import main")
    print("await main.run('Pergi ke wikipedia dan cari info AI')")
