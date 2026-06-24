import pygame
import vgamepad as vg
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
import threading
import time
import serial
import serial.tools.list_ports
import subprocess
import os
import sys
import pystray
from PIL import Image, ImageDraw
import urllib.request
import json
import ctypes

BAUD_RATE = 115200

# Set modern look
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class X360CE_EmulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Virtual Gamepad")
        self.root.geometry("620x750")
        
        # Intercept close ('X') button to hide instead of quit
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        self.running = True
        self.gamepad = None
        self.joystick = None
        self.ser = None
        
        self.mode = ctk.StringVar(value="Bluetooth") # "Bluetooth" or "USB"
        
        try:
            pygame.init()
            pygame.joystick.init()
        except Exception as e:
            messagebox.showerror("Pygame Error", f"Failed to initialize pygame: {e}")
            
        # Title
        title_lbl = ctk.CTkLabel(root, text="🎮 Controller Emulator", font=ctk.CTkFont(size=24, weight="bold"))
        title_lbl.pack(pady=(15, 5))
        
        # Updates Section
        frame_updates = ctk.CTkFrame(root)
        frame_updates.pack(pady=10, fill="x", padx=20)
        
        ctk.CTkLabel(frame_updates, text="Updates & Drivers", font=ctk.CTkFont(weight="bold")).pack(pady=(5, 0))
        btn_frame1 = ctk.CTkFrame(frame_updates, fg_color="transparent")
        btn_frame1.pack(pady=10)
        ctk.CTkButton(btn_frame1, text="Download / Update ViGEmBus", command=self.update_vigembus).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame1, text="Check for App Updates", command=self.check_app_updates).pack(side="right", padx=10)

        # Hardware Setup Section
        frame_flash = ctk.CTkFrame(root)
        frame_flash.pack(pady=10, fill="x", padx=20)
        
        ctk.CTkLabel(frame_flash, text="Hardware Setup (Flash ESP32)", font=ctk.CTkFont(weight="bold")).pack(pady=(5, 0))
        btn_frame2 = ctk.CTkFrame(frame_flash, fg_color="transparent")
        btn_frame2.pack(pady=10)
        ctk.CTkButton(btn_frame2, text="Flash USB Version", fg_color="#2b6b3e", hover_color="#215430", command=lambda: self.flash_firmware("wired")).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame2, text="Flash Bluetooth Version", fg_color="#a83232", hover_color="#822525", command=lambda: self.flash_firmware("bluetooth")).pack(side="right", padx=10)

        # Input Mode Toggle
        frame_toggle = ctk.CTkFrame(root)
        frame_toggle.pack(pady=10, fill="x", padx=20)
        
        ctk.CTkLabel(frame_toggle, text="Emulator Input Mode", font=ctk.CTkFont(weight="bold")).pack(pady=(5, 0))
        btn_frame3 = ctk.CTkFrame(frame_toggle, fg_color="transparent")
        btn_frame3.pack(pady=10)
        
        ctk.CTkRadioButton(btn_frame3, text="Bluetooth (DInput)", variable=self.mode, value="Bluetooth", command=self.switch_mode).pack(side="left", padx=15)
        ctk.CTkRadioButton(btn_frame3, text="USB", variable=self.mode, value="USB", command=self.switch_mode).pack(side="left", padx=15)
        
        self.com_var = ctk.StringVar()
        self.com_combo = ctk.CTkOptionMenu(btn_frame3, variable=self.com_var, width=100)
        self.com_combo.pack(side="left", padx=5)
        ctk.CTkButton(btn_frame3, text="↻", width=30, command=self.refresh_ports).pack(side="left")
        self.refresh_ports()
        
        # Mapping and Inversion container
        container_map = ctk.CTkFrame(root, fg_color="transparent")
        container_map.pack(pady=5, fill="x", padx=20)
        
        # Button Mapping Section
        frame_map = ctk.CTkFrame(container_map)
        frame_map.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(frame_map, text="Button Mapping", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, pady=(5, 0))
        
        btns = [str(i) for i in range(32)]
        
        ctk.CTkLabel(frame_map, text="A:").grid(row=1, column=0, padx=5, pady=5)
        self.map_a = ctk.CTkOptionMenu(frame_map, values=btns, width=60); self.map_a.grid(row=1, column=1, padx=5, pady=5); self.map_a.set("0")
        
        ctk.CTkLabel(frame_map, text="B:").grid(row=1, column=2, padx=5, pady=5)
        self.map_b = ctk.CTkOptionMenu(frame_map, values=btns, width=60); self.map_b.grid(row=1, column=3, padx=5, pady=5); self.map_b.set("1")
        
        ctk.CTkLabel(frame_map, text="X:").grid(row=2, column=0, padx=5, pady=5)
        self.map_x = ctk.CTkOptionMenu(frame_map, values=btns, width=60); self.map_x.grid(row=2, column=1, padx=5, pady=5); self.map_x.set("2")
        
        ctk.CTkLabel(frame_map, text="Y:").grid(row=2, column=2, padx=5, pady=5)
        self.map_y = ctk.CTkOptionMenu(frame_map, values=btns, width=60); self.map_y.grid(row=2, column=3, padx=5, pady=5); self.map_y.set("3")

        # Joystick Inversion Section
        frame_joy = ctk.CTkFrame(container_map)
        frame_joy.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        ctk.CTkLabel(frame_joy, text="Joystick Inversion", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=(5, 0))
        
        self.inv_lx = ctk.BooleanVar(value=False)
        self.inv_ly = ctk.BooleanVar(value=True) 
        self.inv_rx = ctk.BooleanVar(value=False)
        self.inv_ry = ctk.BooleanVar(value=True)
        
        ctk.CTkCheckBox(frame_joy, text="Inv Left X", variable=self.inv_lx).grid(row=1, column=0, padx=10, pady=5)
        ctk.CTkCheckBox(frame_joy, text="Inv Left Y", variable=self.inv_ly).grid(row=1, column=1, padx=10, pady=5)
        ctk.CTkCheckBox(frame_joy, text="Inv Right X", variable=self.inv_rx).grid(row=2, column=0, padx=10, pady=5)
        ctk.CTkCheckBox(frame_joy, text="Inv Right Y", variable=self.inv_ry).grid(row=2, column=1, padx=10, pady=5)
        
        # Status
        self.status_var = ctk.StringVar()
        self.status_var.set("Status: Ready.")
        ctk.CTkLabel(root, textvariable=self.status_var, font=("Helvetica", 12)).pack(pady=2)
        
        self.device_var = ctk.StringVar()
        self.device_var.set("Device: None")
        ctk.CTkLabel(root, textvariable=self.device_var, font=("Helvetica", 12), text_color="#1f6aa5").pack(pady=2)
        
        self.emulation_status = ctk.StringVar()
        self.emulation_status.set("Emulator OFF")
        self.lbl_emu = ctk.CTkLabel(root, textvariable=self.emulation_status, font=("Helvetica", 16, "bold"), text_color="#a83232")
        self.lbl_emu.pack(pady=2)
        
        # Canvas for visualizing inputs
        self.canvas = tk.Canvas(root, width=400, height=150, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(pady=10)
        
        # Left Joy
        self.canvas.create_text(100, 20, text="Left Joystick", fill="white", font=("Helvetica", 10, "bold"))
        self.joy_l_bg = self.canvas.create_oval(70, 40, 130, 100, outline="gray", width=2)
        self.joy_l_dot = self.canvas.create_oval(95, 65, 105, 75, fill="#a83232")
        
        # Right Joy
        self.canvas.create_text(300, 20, text="Right Joystick", fill="white", font=("Helvetica", 10, "bold"))
        self.joy_r_bg = self.canvas.create_oval(270, 40, 330, 100, outline="gray", width=2)
        self.joy_r_dot = self.canvas.create_oval(295, 65, 305, 75, fill="#1f6aa5")
        
        # Buttons indicators
        self.btn_a_ind = self.canvas.create_oval(180, 50, 200, 70, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(190, 60, text="A", fill="white")
        
        self.btn_b_ind = self.canvas.create_oval(210, 50, 230, 70, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(220, 60, text="B", fill="white")
        
        self.btn_x_ind = self.canvas.create_oval(180, 80, 200, 100, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(190, 90, text="X", fill="white")
        
        self.btn_y_ind = self.canvas.create_oval(210, 80, 230, 100, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(220, 90, text="Y", fill="white")
        
        # Virtual Gamepad
        try:
            self.gamepad = vg.VX360Gamepad()
            self.emulation_status.set("Emulator ON (Virtual Xbox 360)")
            self.lbl_emu.configure(text_color="#2b6b3e")
        except Exception as e:
            self.status_var.set(f"Status: Missing ViGEmBus! Click Update Driver.")
            self.gamepad = None

        # Setup System Tray
        self.setup_tray()

        # Start Thread
        self.thread = threading.Thread(target=self.emulator_loop)
        self.thread.daemon = True
        self.thread.start()

    def update_vigembus(self):
        def task():
            self.status_var.set("Status: Checking for ViGEmBus updates...")
            self.root.update()
            try:
                req = urllib.request.Request("https://api.github.com/repos/nefarius/ViGEmBus/releases/latest", headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                
                download_url = None
                for asset in data.get('assets', []):
                    if asset['name'].endswith('.exe') or asset['name'].endswith('.msi'):
                        download_url = asset['browser_download_url']
                        filename = asset['name']
                        break
                
                if not download_url:
                    messagebox.showerror("Error", "Could not find the driver installer on GitHub.")
                    return
                
                self.status_var.set("Status: Downloading ViGEmBus... Please wait.")
                self.root.update()
                
                save_path = os.path.join(os.getenv('TEMP', ''), filename)
                urllib.request.urlretrieve(download_url, save_path)
                
                self.status_var.set("Status: Launching ViGEmBus Installer...")
                os.startfile(save_path)
                messagebox.showinfo("Success", "ViGEmBus installer downloaded and launched! Please complete the installation.")
                
            except Exception as e:
                messagebox.showerror("Download Error", f"Failed to download ViGEmBus: {e}")
            finally:
                self.status_var.set("Status: Ready.")
        
        threading.Thread(target=task, daemon=True).start()

    def check_app_updates(self):
        messagebox.showinfo("Updater", "Checking for updates...\n\nYou are currently running the latest version of ESP32 Virtual Gamepad!")

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.com_combo.configure(values=ports)
            if not self.com_var.get() or self.com_var.get() not in ports:
                self.com_combo.set(ports[0])
        else:
            self.com_combo.configure(values=["No COM Ports"])
            self.com_combo.set("No COM Ports")

    def setup_tray(self):
        def create_image():
            width = 64
            height = 64
            color1 = (31, 106, 165)
            color2 = (255, 255, 255)
            image = Image.new('RGB', (width, height), color1)
            dc = ImageDraw.Draw(image)
            dc.ellipse((16, 16, 48, 48), fill=color2)
            return image
            
        menu = pystray.Menu(
            pystray.MenuItem('Show Settings', self.show_window, default=True),
            pystray.MenuItem('Quit', self.quit_app)
        )
        self.tray_icon = pystray.Icon("Virtual Gamepad", create_image(), "ESP32 Gamepad Emulator", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        
    def hide_window(self):
        self.root.withdraw()
        
    def show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, lambda: self.root.attributes("-topmost", True))
        self.root.after(100, lambda: self.root.attributes("-topmost", False))
        
    def quit_app(self, icon=None, item=None):
        self.tray_icon.stop()
        self.running = False
        try: pygame.quit()
        except: pass
        if self.ser:
            try: self.ser.close()
            except: pass
        self.root.after(0, self.root.destroy)
        
    def flash_firmware(self, mode_flash):
        if messagebox.askyesno("Confirm", f"Are you sure you want to flash the {mode_flash} version to the ESP32?"):
            self.running = False
            if self.ser:
                try: self.ser.close()
                except: pass
                
            self.status_var.set(f"Status: Flashing {mode_flash} version... Please wait.")
            self.root.update()
            
            def flash_thread():
                proj_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
                
                src_dir = os.path.join(proj_dir, "src")
                if not os.path.exists(src_dir):
                    src_dir = os.path.join(os.path.dirname(proj_dir), "src")
                    proj_dir = os.path.dirname(proj_dir)
                    
                main_cpp = os.path.join(src_dir, "main.cpp")
                
                try:
                    with open(main_cpp, "r", encoding="utf-8") as f:
                        content = f.read()
                    is_bluetooth = "BleGamepad" in content
                    
                    if mode_flash == "bluetooth" and not is_bluetooth:
                        os.rename(main_cpp, os.path.join(src_dir, "main_wired.cpp.disabled"))
                        os.rename(os.path.join(src_dir, "main_bluetooth.cpp.disabled"), main_cpp)
                    elif mode_flash == "wired" and is_bluetooth:
                        os.rename(main_cpp, os.path.join(src_dir, "main_bluetooth.cpp.disabled"))
                        os.rename(os.path.join(src_dir, "main_wired.cpp.disabled"), main_cpp)
                        
                    res = subprocess.run(["pio", "run", "-t", "upload"], cwd=proj_dir, shell=True, capture_output=True, text=True)
                    
                    if res.returncode == 0:
                        self.root.after(0, lambda: messagebox.showinfo("Success", f"Flashed {mode_flash} version successfully!"))
                        if mode_flash == "bluetooth":
                            self.mode.set("Bluetooth")
                        else:
                            self.mode.set("USB")
                        self.root.after(0, self.switch_mode)
                    else:
                        err_msg = res.stderr[-500:] if res.stderr else res.stdout[-500:]
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to flash firmware:\n{err_msg}"))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
                
                self.running = True
                threading.Thread(target=self.emulator_loop, daemon=True).start()
                self.root.after(0, lambda: self.status_var.set("Status: Running..."))

            threading.Thread(target=flash_thread, daemon=True).start()

    def switch_mode(self):
        self.update_ui(0, 0, 0, 0, {})
        if self.mode.get() == "USB":
            self.status_var.set("Status: Connecting to Serial Port...")
        else:
            self.status_var.set("Status: Looking for physical controller...")
        
    def update_ui(self, lx, ly, rx, ry, btns):
        self.canvas.coords(self.joy_l_dot, 95 + lx*30, 65 + ly*30, 105 + lx*30, 75 + ly*30)
        self.canvas.coords(self.joy_r_dot, 295 + rx*30, 65 + ry*30, 305 + rx*30, 75 + ry*30)
        
        self.canvas.itemconfig(self.btn_a_ind, fill="#2b6b3e" if btns.get('A') else "#2b2b2b")
        self.canvas.itemconfig(self.btn_b_ind, fill="#a83232" if btns.get('B') else "#2b2b2b")
        self.canvas.itemconfig(self.btn_x_ind, fill="#1f6aa5" if btns.get('X') else "#2b2b2b")
        self.canvas.itemconfig(self.btn_y_ind, fill="#b59c2a" if btns.get('Y') else "#2b2b2b")

    def get_mappings(self):
        try:
            return {
                "A": int(self.map_a.get()),
                "B": int(self.map_b.get()),
                "X": int(self.map_x.get()),
                "Y": int(self.map_y.get())
            }
        except ValueError:
            return {"A": 0, "B": 1, "X": 2, "Y": 3}

    def emulator_loop(self):
        while self.running:
            if not self.gamepad:
                time.sleep(1)
                continue
                
            current_mode = self.mode.get()
            
            if current_mode == "Bluetooth":
                if self.ser:
                    self.ser.close()
                    self.ser = None
                self.run_bluetooth_cycle()
            else:
                if self.joystick:
                    self.joystick.quit()
                    self.joystick = None
                self.run_usb_cycle()
                
            time.sleep(0.01)

    def run_bluetooth_cycle(self):
        pygame.event.pump()
        
        if not self.joystick:
            pygame.joystick.quit()
            pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                joy = pygame.joystick.Joystick(i)
                joy.init()
                name = joy.get_name()
                if "Xbox 360" not in name and "Virtual" not in name:
                    self.joystick = joy
                    self.root.after(0, lambda: self.status_var.set("Status: Physical Controller Connected!"))
                    self.root.after(0, lambda n=name: self.device_var.set(f"Device: {n}"))
                    break
                else:
                    joy.quit()
            if not self.joystick:
                time.sleep(1)
                return
                
        try:
            lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0
            btns_state = {}
            mapping = self.get_mappings()
            
            if self.joystick.get_numaxes() >= 2:
                lx = self.joystick.get_axis(0)
                ly = self.joystick.get_axis(1)
                
                if self.inv_lx.get(): lx = -lx
                if self.inv_ly.get(): ly = -ly
                
                self.gamepad.left_joystick(x_value=int(lx * 32767), y_value=int(ly * 32767))
                
            if self.joystick.get_numaxes() >= 4:
                rx = self.joystick.get_axis(2)
                ry = self.joystick.get_axis(3)
                
                if self.inv_rx.get(): rx = -rx
                if self.inv_ry.get(): ry = -ry
                
                self.gamepad.right_joystick(x_value=int(rx * 32767), y_value=int(ry * 32767))
                
            for btn_name, xbox_btn in [("A", vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
                                       ("B", vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
                                       ("X", vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
                                       ("Y", vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)]:
                hw_idx = mapping.get(btn_name, 0)
                if hw_idx < self.joystick.get_numbuttons():
                    is_pressed = self.joystick.get_button(hw_idx)
                    btns_state[btn_name] = is_pressed
                    if is_pressed: self.gamepad.press_button(button=xbox_btn)
                    else: self.gamepad.release_button(button=xbox_btn)
                else:
                    btns_state[btn_name] = False
                    self.gamepad.release_button(button=xbox_btn)
                
            self.gamepad.update()
            self.root.after(0, self.update_ui, lx, ly, rx, ry, btns_state)
        except Exception as e:
            self.joystick.quit()
            self.joystick = None
            self.root.after(0, lambda: self.status_var.set(f"Status: Controller Disconnected! ({e})"))
            self.root.after(0, lambda: self.device_var.set("Device: None"))
            
    def run_usb_cycle(self):
        port = self.com_var.get()
        if not port or port == "No COM Ports":
            time.sleep(1)
            return
            
        if not self.ser or self.ser.port != port:
            if self.ser:
                try: self.ser.close()
                except: pass
                self.ser = None
            try:
                self.ser = serial.Serial(port, BAUD_RATE, timeout=1)
                self.root.after(0, lambda: self.status_var.set("Status: Serial Connected!"))
                self.root.after(0, lambda: self.device_var.set(f"Device: {port}"))
            except:
                time.sleep(1)
                return
                
        try:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("X:"):
                    parts = line.split(',')
                    data = {}
                    for part in parts:
                        if ':' in part:
                            k, v = part.split(':')
                            try: data[k] = int(v)
                            except: pass
                            
                    if 'X' in data and 'Y' in data:
                        vx = data['X']
                        vy = data['Y']
                        
                        if self.inv_lx.get(): vx = -vx
                        if self.inv_ly.get(): vy = -vy
                        
                        self.gamepad.left_joystick(x_value=vx, y_value=vy)
                        
                        btns_state = {}
                        
                        if data.get('A'): self.gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A); btns_state['A']=1
                        else: self.gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A); btns_state['A']=0
                        
                        if data.get('B'): self.gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B); btns_state['B']=1
                        else: self.gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B); btns_state['B']=0
                        
                        if data.get('XBTN'): self.gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X); btns_state['X']=1
                        else: self.gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X); btns_state['X']=0
                        
                        if data.get('YBTN'): self.gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_Y); btns_state['Y']=1
                        else: self.gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_Y); btns_state['Y']=0
                        
                        self.gamepad.update()
                        
                        lx = vx / 32767.0
                        ly = vy / 32767.0 
                        self.root.after(0, self.update_ui, lx, ly, 0, 0, btns_state)
        except Exception as e:
            self.ser.close()
            self.ser = None
            self.root.after(0, lambda: self.status_var.set(f"Status: Serial Disconnected! ({e})"))
            self.root.after(0, lambda: self.device_var.set("Device: None"))

if __name__ == "__main__":
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\ESP32_Virtual_Gamepad_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:
        sys.exit(0)

    root = ctk.CTk()
    app = X360CE_EmulatorApp(root)
    
    if "--minimized" in sys.argv:
        app.hide_window()
        
    root.mainloop()
