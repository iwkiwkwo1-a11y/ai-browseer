import json
import re

SYSTEM_PROMPT = """Anda adalah agen AI ahli browser otonom. Anda dapat menavigasi web untuk menyelesaikan tugas pengguna.
Anda menerima status halaman web (URL, Judul, dan Elemen Interaktif bernomor).

Anda HARUS merespons dalam format JSON valid yang berisi tiga key: 'thought', 'action', dan 'args'.

Tersedia Action:
- "GOTO": Pergi ke URL. (args: { "url": "..." })
- "CLICK": Klik elemen berdasarkan ID. (args: { "id": "..." })
- "TYPE": Ketik teks ke elemen berdasarkan ID dan tekan Enter. (args: { "id": "...", "text": "..." })
- "SCROLL_DOWN": Gulir ke bawah halaman. (args: {})
- "GO_BACK": Mundur ke halaman sebelumnya. (args: {})
- "PRESS_KEY": Tekan tombol keyboard seperti "Escape", "Enter". (args: { "key": "..." })
- "WAIT": Tunggu beberapa detik jika web sedang memuat. (args: { "seconds": "3" })
- "DONE": Selesaikan tugas. (args: { "result": "..." })

PERHATIAN (MENCEGAH LOOPING):
1. Selalu periksa "History Aksi Sebelumnya".
2. JIKA Anda baru saja menekan tombol atau mengetik, NAMUN status halaman tidak berubah, JANGAN lakukan hal yang sama lagi!
3. Jika terjebak di halaman yang sama, gunakan "GO_BACK", "PRESS_KEY" (dengan key "Escape" untuk menutup popup), atau cari ID elemen lain.
4. JANGAN muter-muter mengulangi aksi yang gagal berulang kali.

Contoh Respons JSON:
{
  "thought": "Halaman login tidak berubah setelah saya klik tombol submit, mungkin ada error. Saya akan coba mundur.",
  "action": "GO_BACK",
  "args": {}
}
"""

class BrowserAgent:
    def __init__(self, pipe):
        self.pipe = pipe

    def get_decision(self, task, history, current_state):
        prompt_history = "\n".join(history[-4:]) if history else "Belum ada aksi."

        user_prompt = f"""Tugas: {task}

--- History Aksi Sebelumnya ---
{prompt_history}

--- Status Halaman Saat Ini ---
{current_state}

Tentukan langkah selanjutnya. Pikirkan matang-matang agar tidak looping.
Balas HANYA dengan format JSON."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # Gunakan Qwen 2.5
            outputs = self.pipe(
                messages,
                max_new_tokens=512,
                do_sample=False, # Supaya stabil
            )

            response_text = outputs[0]["generated_text"][-1]["content"]
            return self._parse_json(response_text)

        except Exception as e:
            return {"error": str(e), "raw": ""}

    def _parse_json(self, text):
        # Cari blok JSON jika model menyelipkan markdown
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = text

        try:
            data = json.loads(json_str)
            # Normalisasi output jika model bandel
            thought = data.get("thought", "Tidak ada thought")
            action = data.get("action", "")
            args = data.get("args", {})
            return {"thought": thought, "action": action, "args": args}
        except Exception as e:
            return {"error": "Format JSON tidak valid.", "raw": text}
