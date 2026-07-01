import sys

with open('pc_gamepad.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add imports
if 'import requests' not in code:
    code = code.replace('import time', 'import time\nimport requests\nimport tempfile\nimport subprocess\nimport threading\nfrom tkinter import messagebox')

# Add APP_VERSION
if 'APP_VERSION =' not in code:
    code = code.replace('class X360CE_EmulatorApp:', 'APP_VERSION = "2.1"\n\nclass X360CE_EmulatorApp:')

# Add updater method
updater_code = '''
    def check_for_updates(self):
        def _check():
            try:
                response = requests.get("https://api.github.com/repos/Biswa717-sudo/esp32-virtual-gamepad/releases/latest", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    latest_version = data["tag_name"].replace("v", "")
                    if latest_version != APP_VERSION:
                        # Found update!
                        for asset in data.get("assets", []):
                            if asset["name"].endswith(".exe"):
                                download_url = asset["browser_download_url"]
                                self.root.after(0, lambda: self.prompt_update(latest_version, download_url))
                                break
            except:
                pass
        threading.Thread(target=_check, daemon=True).start()

    def prompt_update(self, version, url):
        if messagebox.askyesno("Update Available", f"Version {version} is available! Do you want to download and install it now?"):
            self.download_update(url)

    def download_update(self, url):
        win = ctk.CTkToplevel(self.root)
        win.title("Downloading Update")
        win.geometry("300x100")
        win.attributes("-topmost", True)
        label = ctk.CTkLabel(win, text="Downloading... Please wait.")
        label.pack(pady=20)
        
        def _download():
            try:
                response = requests.get(url, stream=True)
                installer_path = os.path.join(tempfile.gettempdir(), "ESP32_Gamepad_Setup_Update.exe")
                with open(installer_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Run the installer silently and kill the current app
                subprocess.Popen([installer_path, "/SILENT"])
                self.root.after(0, self.quit_app)
            except Exception as e:
                self.root.after(0, lambda: label.configure(text=f"Download failed! {str(e)}"))
                
        threading.Thread(target=_download, daemon=True).start()
'''

if 'def check_for_updates' not in code:
    code = code.replace('def __init__(self, root):', updater_code + '\n    def __init__(self, root):')

if 'self.check_for_updates()' not in code:
    code = code.replace('self.running = True', 'self.running = True\n        self.check_for_updates()')

# Update Window Title to include version
if 'self.root.title("ESP32' in code:
    code = code.replace('self.root.title("ESP32 Virtual Gamepad & Flasher")', 'self.root.title(f"ESP32 Virtual Gamepad & Flasher v{APP_VERSION}")')
    code = code.replace('self.root.title("ESP32 Virtual Gamepad")', 'self.root.title(f"ESP32 Virtual Gamepad v{APP_VERSION}")')

with open('pc_gamepad.py', 'w', encoding='utf-8') as f:
    f.write(code)
