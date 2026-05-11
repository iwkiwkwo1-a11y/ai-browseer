import json
import re

SYSTEM_PROMPT = """Anda adalah agen AI Web Browser tingkat lanjut (SOTA) yang sepenuhnya otonom.
Anda memiliki kemampuan kognitif tingkat tinggi: perencanaan (planning), memori (memory), dan refleksi (reflection).

TUGAS ANDA: Selesaikan instruksi yang diberikan oleh pengguna dengan menavigasi web.

Anda menerima:
1. Tujuan (Task)
2. Status Halaman Web Saat Ini (URL, Judul, Teks Terlihat, dan Elemen Interaktif bernomor).
3. Sejarah Aksi & Refleksi Sebelumnya.
4. Memori Jangka Pendek & Rencana Anda saat ini.

Anda HARUS merespons dalam format JSON valid yang berisi atribut kognitif berikut:
{
  "reflection": "Evaluasi jujur atas hasil dari aksi Anda sebelumnya. Apakah berhasil? Apakah Anda di halaman yang benar? Jika gagal/looping, apa yang salah?",
  "plan": "Langkah-langkah tingkat tinggi yang akan Anda lakukan selanjutnya (To-Do list singkat).",
  "memory": "Informasi atau konteks penting yang perlu diingat (misal: harga barang, url, ringkasan teks). Biarkan kosong jika tidak ada yang baru.",
  "thought": "Pemikiran taktis spesifik untuk langkah SEKARANG berdasarkan refleksi dan rencana Anda.",
  "action": "NAMA_AKSI",
  "args": {"key": "value"}
}

Tersedia Action:
- "GOTO": Pergi ke URL. (args: { "url": "..." })
- "CLICK": Klik elemen berdasarkan ID. (args: { "id": "..." })
- "TYPE": Ketik teks ke elemen berdasarkan ID dan tekan Enter. (args: { "id": "...", "text": "..." })
- "SCROLL_DOWN": Gulir ke bawah halaman. (args: {})
- "GO_BACK": Mundur ke halaman sebelumnya. (args: {})
- "PRESS_KEY": Tekan tombol keyboard seperti "Escape", "Enter". (args: { "key": "..." })
- "WAIT": Tunggu beberapa detik jika web memuat. (args: { "seconds": "3" })
- "EXTRACT_TEXT": Mengambil seluruh teks artikel/bacaan dari halaman untuk dianalisis. (args: {})
- "READ_PDF": Membaca dan mengekstrak teks dari tautan PDF. (args: { "url": "..." })
- "DONE": Selesaikan tugas. (args: { "result": "..." })

ATURAN KRITIS (ANTI-LOOPING & KEAMANAN):
1. REFLEKSI adalah kunci! Jika Anda melihat 'History Aksi' menunjukkan Anda mengulangi aksi yang sama tanpa hasil (halaman tidak berubah), Anda HARUS mengubah strategi di 'thought' dan menggunakan 'GO_BACK' atau mencari elemen lain.
2. JANGAN muter-muter. Jika terjebak, segera refleksi dan putar balik.
3. Selalu perbarui 'memory' jika Anda menemukan data yang diminta pengguna.
"""

class BrowserAgent:
    def __init__(self, pipe):
        self.pipe = pipe
        self.current_plan = "Belum ada rencana."
        self.current_memory = "Kosong."

    def get_decision(self, task, history, current_state):
        # Batasi history ke 2 langkah terakhir saja untuk menghemat VRAM
        prompt_history = "\n".join(history[-2:]) if history else "Belum ada aksi."

        user_prompt = f"""TUGAS UTAMA: {task}

--- Rencana (Plan) Anda Saat Ini ---
{self.current_plan}

--- Memori Anda Saat Ini ---
{self.current_memory}

--- History Aksi Sebelumnya ---
{prompt_history}

--- Status Halaman Saat Ini ---
{current_state}

Tentukan langkah selanjutnya. Tuliskan refleksi Anda terlebih dahulu.
Balas HANYA dengan JSON valid."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # Gunakan Qwen 2.5
            outputs = self.pipe(
                messages,
                max_new_tokens=768, # Diperbesar karena output kognitif lebih panjang
                do_sample=False,
            )

            response_text = outputs[0]["generated_text"][-1]["content"]
            decision = self._parse_json(response_text)

            # Perbarui State Kognitif jika berhasil di-parse
            if "error" not in decision:
                if decision.get("plan"):
                    self.current_plan = decision["plan"]
                if decision.get("memory"):
                    self.current_memory = decision["memory"]

            return decision

        except Exception as e:
            return {"error": str(e), "raw": ""}

    def _parse_json(self, text):
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = text

        try:
            data = json.loads(json_str)
            return {
                "reflection": data.get("reflection", "Tidak ada refleksi"),
                "plan": data.get("plan", "Tidak ada rencana"),
                "memory": data.get("memory", "Tidak ada memori"),
                "thought": data.get("thought", "Tidak ada thought"),
                "action": data.get("action", ""),
                "args": data.get("args", {})
            }
        except Exception as e:
            return {"error": "Format JSON tidak valid.", "raw": text}
