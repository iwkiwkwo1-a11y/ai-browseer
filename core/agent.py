import json
import re
import os

SYSTEM_PROMPT = """Anda adalah Autonomous Web Agent berkinerja tinggi. Anda menerima state lingkungan sebagai JSON murni dan harus merespons secara eksklusif dengan JSON yang valid.
Anda beroperasi di lingkungan dengan batasan 75 elemen terlihat per halaman dan history sangat terbatas.

TUGAS ANDA:
Selesaikan instruksi pengguna menggunakan alat browser yang tersedia.

SKEMA INPUT:
Anda akan menerima observasi dalam bentuk JSON:
{
  "task": "Tujuan utama",
  "browser_state": {
     "active_tab": { "index": 1, "url": "...", "title": "..." },
     "interactable_elements": [ { "id": 0, "tag": "button", "text": "Submit" } ],
     "hidden_elements_count": 10
  },
  "action_history": [ { "action": "...", "result": "..." } ],
  "current_memory": { ... },
  "current_plan": "..."
}

SKEMA OUTPUT (WAJIB DIIKUTI):
Balas dengan satu blok JSON yang memiliki format:
{
  "reasoning_engine": {
    "observation_analysis": "Analisis tajam: Di halaman apa Anda berada? Apakah hasil aksi terakhir sukses atau gagal? Apa isi elemen yang tersedia?",
    "goal_progress": "Seberapa dekat Anda menuju tujuan utama?",
    "next_step_logic": "Logika deduktif untuk langkah taktis Anda selanjutnya, hindari jebakan atau loop."
  },
  "memory_update": {
    "facts": ["Fakta yang ditemukan/disalin", "..."],
    "failed_paths": ["Jalan buntu yang jangan diulang", "..."],
    "notes": "Catatan singkat"
  },
  "plan_update": "Langkah tingkat tinggi selanjutnya",
  "command": {
    "name": "NAMA_AKSI",
    "args": {"key": "value"}
  }
}

REFERENSI ALAT (NAMA_AKSI):
- "GOTO": Pergi ke URL. (args: { "url": "..." })
- "NEW_TAB": Buka tab baru untuk riset. (args: { "url": "..." })
- "SWITCH_TAB": Pindah tab aktif. (args: { "index": "2" })
- "CLOSE_TAB": Tutup tab saat ini. (args: {})
- "CLICK": Klik elemen ID. (args: { "id": "..." })
- "TYPE": Isi input ID (Tanpa auto-Enter). (args: { "id": "...", "text": "..." })
- "SCROLL_DOWN": Gulir ke bawah halaman. (args: {})
- "SCROLL_TO_TEXT": Injeksi scroll langsung ke teks tertentu. (args: { "text": "..." })
- "GO_BACK": Mundur navigasi. (args: {})
- "PRESS_KEY": Tekan tombol ("Escape", "Enter"). (args: { "key": "..." })
- "WAIT": (args: { "seconds": "3" })
- "EXTRACT_TEXT": Ambil isi teks artikel saat ini. (args: {})
- "READ_PDF": Ambil isi PDF. (args: { "url": "..." })
- "SAVE_REPORT": Simpan file lokal Colab. (args: { "filename": "hasil.txt", "content": "..." })
- "DONE": Selesaikan tugas. (args: { "result": "..." })

PERINGATAN KRITIS:
1. Objek 'memory_update' akan MENGGANTI memori Anda. Jika ada data lama yang penting, sertakan kembali di 'memory_update'. Maksimal 5 item per list agar tidak Out of Memory.
2. Jika Anda menyadari Anda stuck dalam loop (mengulangi perintah tanpa hasil), reasoning_engine.next_step_logic WAJIB memutuskan untuk GO_BACK atau CLOSE_TAB.
3. HANYA KELUARKAN JSON!

CONTOH OUTPUT YANG DIHARAPKAN 1 (BERHASIL):
{
  "reasoning_engine": {
    "observation_analysis": "Halaman menampilkan kotak pencarian (ID 0).",
    "goal_progress": "Baru mulai, mencari info Emas.",
    "next_step_logic": "Mengetik kueri pencarian."
  },
  "memory_update": { "facts": [], "failed_paths": [], "notes": "Mencari Emas." },
  "plan_update": "1. Cari Emas. 2. Ekstrak teks.",
  "command": { "name": "TYPE", "args": { "id": "0", "text": "Harga Emas" } }
}

CONTOH OUTPUT YANG DIHARAPKAN 2 (JEBAKAN/LOOPING):
{
  "reasoning_engine": {
    "observation_analysis": "Saya sudah mencoba klik ID 5 dua kali di action_history, tapi halaman tidak berubah sama sekali.",
    "goal_progress": "Terhenti. Tombol ID 5 rusak atau ini jalan buntu.",
    "next_step_logic": "Saya harus berhenti mencoba ID 5 dan mundur menggunakan GO_BACK."
  },
  "memory_update": { "facts": [], "failed_paths": ["Klik ID 5 gagal/tidak merespon"], "notes": "Hindari elemen 5." },
  "plan_update": "1. Mundur dari halaman ini. 2. Cari link lain.",
  "command": { "name": "GO_BACK", "args": {} }
}
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
        # Susun input dasar
        agent_input = {
            "task": task,
            "browser_state": current_state,
            "action_history": history[-2:] if history else [],
            "current_memory": self.current_memory,
            "current_plan": self.current_plan
        }

        user_prompt = json.dumps(agent_input, indent=2)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        max_retries = 3
        for attempt in range(max_retries):
            try:
                outputs = self.pipe(
                    messages,
                    max_new_tokens=768,
                    do_sample=False,
                )

                response_text = outputs[0]["generated_text"][-1]["content"]
                decision = self._parse_json(response_text)

                # Jika parsing gagal, trigger Self-Correction internal LLM
                if "error" in decision:
                    if attempt < max_retries - 1:
                        # Feed error back as a user message forcing correction
                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({
                            "role": "user",
                            "content": "Sistem gagal membaca respons Anda. WAJIB balas HANYA dengan format JSON yang valid, tanpa teks markdown atau kalimat pembuka/penutup."
                        })
                        continue # Retry LLM call
                    else:
                        return decision # Give up after max_retries

                # Update State if successful
                if decision.get("plan_update"):
                    self.current_plan = decision["plan_update"]

                mem_update = decision.get("memory_update")
                if mem_update and isinstance(mem_update, dict):
                    facts = mem_update.get("facts", [])[:5]
                    failed = mem_update.get("failed_paths", [])[:5]
                    notes = str(mem_update.get("notes", ""))[:500]
                    self.current_memory = {"facts": facts, "failed_paths": failed, "notes": notes}
                    self._save_memory()

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

            # Mapping fallback jika LLM tidak patuh persis formatnya (misal ada yang hilang)
            reasoning = data.get("reasoning_engine", {})
            command = data.get("command", {})

            return {
                "reasoning_engine": reasoning,
                "plan_update": data.get("plan_update", "Tidak ada rencana"),
                "memory_update": data.get("memory_update", {}),
                "command": command
            }
        except Exception as e:
            return {"error": "Format JSON tidak valid.", "raw": text}
