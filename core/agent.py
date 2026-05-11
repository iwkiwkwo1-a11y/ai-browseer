import json
import re
import os

SYSTEM_PROMPT = """Anda adalah agen AI Web Browser tingkat lanjut (SOTA) yang sepenuhnya otonom.
Anda beroperasi di lingkungan dengan batasan ketat (Survival Mode):
1. Anda HANYA melihat maksimal 75 elemen interaktif per halaman (untuk menghemat memori). Jika elemen yang Anda cari tidak ada, gunakan aksi 'SCROLL_DOWN'.
2. Anda HANYA melihat 2 history aksi terakhir Anda.

Oleh karena itu, Anda menggunakan Structured Memory (Memori Terstruktur) untuk menyimpan state secara permanen.
Anda WAJIB memperbarui kategori memori ini: fakta yang ditemukan, jalur yang gagal (agar tidak diulangi), dan catatan.

Anda menerima:
1. Tujuan (Task)
2. Status Halaman Web Saat Ini (URL, Judul, Teks Terlihat, dan Elemen Interaktif bernomor).
3. Sejarah Aksi & Refleksi Sebelumnya (Sangat Terbatas).
4. Memori Terstruktur Anda saat ini & Rencana Anda saat ini.

Anda HARUS merespons dalam format JSON valid yang berisi atribut kognitif berikut:
{
  "reflection": "Evaluasi ketat hasil aksi sebelumnya. Apakah halaman berubah? Jika terjebak/gagal, apa alasannya?",
  "plan": "Langkah tingkat tinggi selanjutnya. Perbarui jika langkah sebelumnya selesai.",
  "memory": {
    "facts": ["fakta 1", "fakta 2..."],
    "failed_paths": ["gagal login di url X karena Y", "elemen 5 rusak..."],
    "notes": "Catatan singkat lainnya"
  },
  "thought": "Pemikiran taktis spesifik untuk langkah SEKARANG berdasarkan refleksi, memory, dan batas pandangan layar Anda.",
  "action": "NAMA_AKSI",
  "args": {"key": "value"}
}

Tersedia Action:
- "GOTO": Pergi ke URL. (args: { "url": "..." })
- "NEW_TAB": Buka tab baru. Gunakan untuk meneliti tautan dari hasil pencarian agar Anda tidak kehilangan halaman utama. (args: { "url": "..." })
- "SWITCH_TAB": Pindah ke tab lain. (args: { "index": "2" })
- "CLOSE_TAB": Tutup tab saat ini. (args: {})
- "CLICK": Klik elemen berdasarkan ID. (args: { "id": "..." })
- "TYPE": Isi teks ke elemen input berdasarkan ID. Ini HANYA mengisi teks, TIDAK menekan Enter. (Gunakan PRESS_KEY "Enter" atau CLICK tombol submit setelahnya jika perlu). (args: { "id": "...", "text": "..." })
- "SCROLL_DOWN": Gulir ke bawah halaman. (args: {})
- "SCROLL_TO_TEXT": Cari dan gulir layar langsung ke teks tertentu. Jauh lebih efektif daripada SCROLL_DOWN manual! (args: { "text": "..." })
- "GO_BACK": Mundur ke halaman sebelumnya. (Gunakan jika tersesat/buntu). (args: {})
- "PRESS_KEY": Tekan tombol keyboard seperti "Escape" (untuk tutup popup), "Enter". (args: { "key": "..." })
- "WAIT": Tunggu jika web memuat lambat. (args: { "seconds": "3" })
- "EXTRACT_TEXT": Mengambil seluruh teks artikel (terbatas 1200 char) dari halaman untuk dianalisis. (args: {})
- "READ_PDF": Membaca dan mengekstrak teks (terbatas 1500 char) dari tautan PDF. (args: { "url": "..." })
- "SAVE_REPORT": Menyimpan data penting/laporan dari memory Anda ke file fisik. Lakukan ini sebelum 'DONE' jika pengguna meminta data dicatat. (args: { "filename": "hasil.txt", "content": "..." })
- "DONE": Selesaikan tugas, berikan jawaban akhir. (args: { "result": "..." })

ATURAN KRITIS (ANTI-LOOPING & MEMORI):
1. MANAJEMEN TAB: Jangan ragu menggunakan 'NEW_TAB' saat membaca artikel dari Google agar Anda bisa kembali ke halaman pencarian dengan 'CLOSE_TAB'.
2. JANGAN MENGULANG: Jika history aksi menunjukkan Anda melakukan hal yang sama tanpa hasil, JANGAN ULANGI! Tambahkan ke array 'failed_paths' di memori, lalu gunakan 'GO_BACK' atau 'SCROLL_TO_TEXT'.
3. UPDATE MEMORI: Objek 'memory' di JSON akan MENIMPA memori lama. Oleh karena itu, ANDA WAJIB MENG-COPY isi 'facts' dan 'failed_paths' lama yang masih penting, lalu menambahkan yang baru. (Maksimal 5 item per array).
"""

class BrowserAgent:
    def __init__(self, pipe):
        self.pipe = pipe
        self.current_plan = "Belum ada rencana."
        self.memory_file = "agent_memory.json"
        self.current_memory = self._load_memory()

    def _load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"facts": [], "failed_paths": [], "notes": "Memori kosong."}

    def _save_memory(self):
        try:
            with open(self.memory_file, "w") as f:
                json.dump(self.current_memory, f, indent=2)
        except:
            pass

    def get_decision(self, task, history, current_state):
        # Batasi history ke 2 langkah terakhir saja untuk menghemat VRAM
        prompt_history = "\n".join(history[-2:]) if history else "Belum ada aksi."

        # Ubah memory dict jadi string JSON rapi untuk prompt
        memory_str = json.dumps(self.current_memory, indent=2)

        user_prompt = f"""TUGAS UTAMA: {task}

--- Rencana (Plan) Anda Saat Ini ---
{self.current_plan}

--- Memori Terstruktur Saat Ini ---
{memory_str}

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
                if decision.get("memory") and isinstance(decision["memory"], dict):
                    # Ambil memori terstruktur, enforce limits
                    mem = decision["memory"]
                    facts = mem.get("facts", [])[:5] # Max 5
                    failed = mem.get("failed_paths", [])[:5] # Max 5
                    notes = str(mem.get("notes", ""))[:500] # Max 500 chars

                    self.current_memory = {
                        "facts": facts,
                        "failed_paths": failed,
                        "notes": notes
                    }
                    self._save_memory() # Simpan ke disk

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
                "memory": data.get("memory", {}),
                "thought": data.get("thought", "Tidak ada thought"),
                "action": data.get("action", ""),
                "args": data.get("args", {})
            }
        except Exception as e:
            return {"error": "Format JSON tidak valid.", "raw": text}
