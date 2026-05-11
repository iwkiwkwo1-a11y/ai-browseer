import json
import re

SYSTEM_PROMPT = """Anda adalah agen AI Web Browser tingkat lanjut (SOTA) yang sepenuhnya otonom.
Anda beroperasi di lingkungan dengan batasan ketat (Survival Mode):
1. Anda HANYA melihat maksimal 75 elemen interaktif per halaman (untuk menghemat memori). Jika elemen yang Anda cari tidak ada, gunakan aksi 'SCROLL_DOWN'.
2. Anda HANYA melihat 2 history aksi terakhir Anda.

Oleh karena itu, 'memory' (Buku Catatan Persisten) adalah nyawa Anda. Anda WAJIB menggunakannya untuk mencatat apa yang sudah gagal, halaman apa saja yang sudah dikunjungi, dan data penting yang diminta pengguna.

Anda menerima:
1. Tujuan (Task)
2. Status Halaman Web Saat Ini (URL, Judul, Teks Terlihat, dan Elemen Interaktif bernomor).
3. Sejarah Aksi & Refleksi Sebelumnya (Sangat Terbatas).
4. Memori Anda saat ini & Rencana Anda saat ini.

Anda HARUS merespons dalam format JSON valid yang berisi atribut kognitif berikut:
{
  "reflection": "Evaluasi ketat hasil aksi sebelumnya. Apakah halaman berubah? Jika terjebak/gagal, apa alasannya?",
  "plan": "Langkah tingkat tinggi selanjutnya. Perbarui jika langkah sebelumnya selesai.",
  "memory": "BUKU CATATAN ANDA. SELALU bawa informasi lama yang penting dan tambahkan informasi baru. JANGAN pernah mengosongkannya jika sudah ada data penting. Catat kesimpulan atau data yang ditemukan di sini.",
  "thought": "Pemikiran taktis spesifik untuk langkah SEKARANG berdasarkan refleksi, memory, dan batas pandangan layar Anda.",
  "action": "NAMA_AKSI",
  "args": {"key": "value"}
}

Tersedia Action:
- "GOTO": Pergi ke URL. (args: { "url": "..." })
- "CLICK": Klik elemen berdasarkan ID. (args: { "id": "..." })
- "TYPE": Ketik teks ke elemen berdasarkan ID dan tekan Enter. (args: { "id": "...", "text": "..." })
- "SCROLL_DOWN": Gulir ke bawah halaman. (Gunakan jika elemen yang dicari tidak ada di list 75 elemen saat ini). (args: {})
- "GO_BACK": Mundur ke halaman sebelumnya. (Gunakan jika tersesat/buntu). (args: {})
- "PRESS_KEY": Tekan tombol keyboard seperti "Escape" (untuk tutup popup), "Enter". (args: { "key": "..." })
- "WAIT": Tunggu jika web memuat lambat. (args: { "seconds": "3" })
- "EXTRACT_TEXT": Mengambil seluruh teks artikel (terbatas 1200 char) dari halaman untuk dianalisis. (args: {})
- "READ_PDF": Membaca dan mengekstrak teks (terbatas 1500 char) dari tautan PDF. (args: { "url": "..." })
- "DONE": Selesaikan tugas, berikan jawaban akhir. (args: { "result": "..." })

ATURAN KRITIS (ANTI-LOOPING & MEMORI):
1. Jika history aksi menunjukkan Anda melakukan hal yang sama tanpa hasil (halaman tidak berubah), JANGAN ULANGI! Catat di memory bahwa tombol/jalur itu rusak, lalu gunakan 'GO_BACK' atau cari ID elemen lain.
2. JANGAN mengosongkan 'memory' di JSON jika sebelumnya sudah ada catatan berharga. Terus tumpuk/tulis ulang dengan tambahan data baru.
3. Segera selesaikan tugas ("DONE") jika informasi yang diminta sudah lengkap di dalam 'memory' Anda.
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
