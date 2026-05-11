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

        # Susun input JSON layaknya API OpenClaw
        agent_input = {
            "task": task,
            "browser_state": current_state, # current_state dari browser sekarang adalah dict
            "action_history": history[-2:] if history else [],
            "current_memory": self.current_memory,
            "current_plan": self.current_plan
        }

        user_prompt = json.dumps(agent_input, indent=2)

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

            if "error" not in decision:
                # Update Plan
                if decision.get("plan_update"):
                    self.current_plan = decision["plan_update"]

                # Update Memori
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
