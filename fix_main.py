import os

file_path = r"D:\gamepad\pc_gamepad.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

missing_code = '''
def create_image():
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (64, 64), color = (30, 30, 30))
    d = ImageDraw.Draw(image)
    d.text((10,25), "ESP32", fill=(255,255,255))
    return image

def setup_tray(app):
    import pystray
    image = create_image()
    menu = pystray.Menu(
        pystray.MenuItem('Show', lambda icon, item: app.show_window()), 
        pystray.MenuItem('Quit', lambda icon, item: app.quit_app())
    )
    app.icon = pystray.Icon("gamepad", image, "ESP32 Virtual Gamepad", menu)
    app.icon.run_detached()

if __name__ == "__main__":
    import customtkinter as ctk
    root = ctk.CTk()
    app = X360CE_EmulatorApp(root)
    setup_tray(app)
    root.mainloop()
'''

if "if __name__ == \"__main__\":" not in content:
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(missing_code)
    print("Fixed missing main block!")
else:
    print("Main block already exists.")
