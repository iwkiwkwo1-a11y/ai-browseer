import asyncio
from playwright.async_api import async_playwright

JS_EXTRACT_DOM = """
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
STEALTH_SCRIPT = """
() => {
    Object.defineProperty(navigator, 'webdriver', {
      get: () => undefined
    });
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
        if not elements:
            dom_text += "Tidak ada elemen interaktif yang ditemukan."
        for el in elements:
            dom_text += f"[{el['id']}] {el['tag'].upper()}: {el['text']}\n"

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
