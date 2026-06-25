import pygame
import vgamepad as vg
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
import threading
import time
import requests
import tempfile
import subprocess
import threading
from tkinter import messagebox
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


class DraggableGraph(tk.Canvas):
    def __init__(self, parent, width=250, height=150, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#1e1e1e", highlightthickness=1, highlightbackground="gray", **kwargs)
        self.width = width
        self.height = height
        # 4 points: start, mid1, mid2, end
        self.points = [(0, height), (width//3, 2*height//3), (2*width//3, height//3), (width, 0)]
        self.selected_point = None
        self.max_time = 1000
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.draw()

    def draw(self):
        self.delete("all")
        for i in range(0, self.width, 50): self.create_line(i, 0, i, self.height, fill="#333333")
        for i in range(0, self.height, 50): self.create_line(0, i, self.width, i, fill="#333333")
        coords = []
        for x, y in self.points: coords.extend([x, y])
        self.create_line(coords, fill="#a83232", width=3)
        for i, (x, y) in enumerate(self.points):
            self.create_oval(x-6, y-6, x+6, y+6, fill="#ffffff" if i > 0 and i < len(self.points)-1 else "#888888")
        self.create_text(5, self.height-5, text="0ms", fill="white", anchor="sw")
        self.create_text(self.width-5, self.height-5, text=f"{self.max_time}ms", fill="white", anchor="se")
        self.create_text(5, 5, text="100%", fill="white", anchor="nw")

    def on_click(self, event):
        for i, (px, py) in enumerate(self.points):
            if i > 0 and i < len(self.points)-1 and abs(event.x - px) < 15 and abs(event.y - py) < 15:
                self.selected_point = i
                break

    def on_drag(self, event):
        if self.selected_point:
            # Constrain X dynamically so points never cross each other
            min_x = self.points[self.selected_point - 1][0]
            max_x = self.points[self.selected_point + 1][0]
            x = max(min_x, min(max_x, event.x))
            y = max(0, min(self.height, event.y))
            self.points[self.selected_point] = (x, y)
            self.draw()

    def on_release(self, event): self.selected_point = None
        
    def get_pressure(self, current_time):
        if current_time >= self.max_time: return 1.0
        if current_time <= 0: return 0.0
        xt = (current_time / self.max_time) * self.width
        if xt <= self.points[0][0]: return 1.0 - (self.points[0][1]/self.height)
        
        for i in range(len(self.points)-1):
            p0, p1 = self.points[i], self.points[i+1]
            if p0[0] <= xt <= p1[0]:
                if p1[0] == p0[0]: return 1.0 - (p1[1]/self.height)
                t = (xt - p0[0]) / (p1[0] - p0[0])
                y = p0[1] + t * (p1[1] - p0[1])
                return max(0.0, min(1.0, 1.0 - (y / self.height)))
        return 1.0

APP_VERSION = "2.4"

class X360CE_EmulatorApp:
    
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
                
                # Run the installer and kill the current app
                ctypes.windll.shell32.ShellExecuteW(None, "runas", installer_path, "/SILENT", None, 1)
                self.root.after(0, self.quit_app)
            except Exception as e:
                self.root.after(0, lambda: label.configure(text=f"Download failed! {str(e)}"))
                
        threading.Thread(target=_download, daemon=True).start()

    def __init__(self, root):
        self.root = root
        self.root.title(f"ESP32 Virtual Gamepad v{APP_VERSION}")
        self.root.geometry("620x750")
        
        # Intercept close ('X') button to hide instead of quit
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        self.running = True
        self.check_for_updates()
        self.gamepad = None
        self.joystick = None
        self.ser = None
        
        self.use_pc_simulation = ctk.BooleanVar(value=True)
        self.lt_time = 0.0
        self.rt_time = 0.0
        self.last_update_time = time.time()
        
        self.hidden_frame = tk.Frame(self.root)
        self.lt_graph = DraggableGraph(self.hidden_frame, width=250, height=150)
        self.rt_graph = DraggableGraph(self.hidden_frame, width=250, height=150)
        
        # Load curves
        try:
            with open("curves.json", "r") as cf:
                cset = json.load(cf)
                self.lt_graph.points = [tuple(p) for p in cset.get('lt_points', self.lt_graph.points)]
                self.lt_graph.max_time = cset.get('lt_max_time', 1000)
                self.rt_graph.points = [tuple(p) for p in cset.get('rt_points', self.rt_graph.points)]
                self.rt_graph.max_time = cset.get('rt_max_time', 1000)
        except: pass
        
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
        
        ctk.CTkLabel(btn_frame3, text="Auto Detect (Bluetooth & USB)").pack(side="left", padx=15)
        
        self.com_var = ctk.StringVar()
        self.com_combo = ctk.CTkOptionMenu(btn_frame3, variable=self.com_var, width=100)
        self.com_combo.pack(side="left", padx=5)
        ctk.CTkButton(btn_frame3, text="↻", width=30, command=self.refresh_ports).pack(side="left")
        self.refresh_ports()

        # Graph Editor Button
        ctk.CTkButton(btn_frame3, text="Open Curve Editor", command=self.open_curve_editor, fg_color="#1f6aa5").pack(side="left", padx=10)

        
        # Mapping and Inversion container
        container_map = ctk.CTkFrame(root, fg_color="transparent")
        container_map.pack(pady=5, fill="x", padx=20)
        
        # Button Mapping Section
        frame_map = ctk.CTkFrame(container_map)
        frame_map.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(frame_map, text="Button Mapping", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, pady=(5, 0))
        
        btns = [str(i) for i in range(32)]
        
        ctk.CTkLabel(frame_map, text="A:").grid(row=1, column=0, padx=5, pady=5)
        self.map_a = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves()); self.map_a.grid(row=1, column=1, padx=5, pady=5); self.map_a.set("0")
        
        ctk.CTkLabel(frame_map, text="B:").grid(row=1, column=2, padx=5, pady=5)
        self.map_b = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves()); self.map_b.grid(row=1, column=3, padx=5, pady=5); self.map_b.set("1")
        
        ctk.CTkLabel(frame_map, text="X:").grid(row=2, column=0, padx=5, pady=5)
        self.map_x = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves()); self.map_x.grid(row=2, column=1, padx=5, pady=5); self.map_x.set("2")
        
        ctk.CTkLabel(frame_map, text="Y:").grid(row=2, column=2, padx=5, pady=5)
        self.map_y = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves()); self.map_y.grid(row=2, column=3, padx=5, pady=5); self.map_y.set("3")

        ctk.CTkLabel(frame_map, text="LB:").grid(row=3, column=0, padx=5, pady=5)
        self.map_lb = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves()); self.map_lb.grid(row=3, column=1, padx=5, pady=5); self.map_lb.set("4")
        
        ctk.CTkLabel(frame_map, text="RB:").grid(row=3, column=2, padx=5, pady=5)
        self.map_rb = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves()); self.map_rb.grid(row=3, column=3, padx=5, pady=5); self.map_rb.set("5")
        
        # Load mappings
        try:
            with open("curves.json", "r") as cf:
                cset = json.load(cf)
                if 'mappings' in cset:
                    m = cset['mappings']
                    if "A" in m: self.map_a.set(str(m["A"]))
                    if "B" in m: self.map_b.set(str(m["B"]))
                    if "X" in m: self.map_x.set(str(m["X"]))
                    if "Y" in m: self.map_y.set(str(m["Y"]))
                    if "LB" in m: self.map_lb.set(str(m["LB"]))
                    if "RB" in m: self.map_rb.set(str(m["RB"]))
        except: pass


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
        
        self.btn_lb_ind = self.canvas.create_oval(150, 50, 170, 70, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(160, 60, text="LB", fill="white")
        
        self.btn_rb_ind = self.canvas.create_oval(240, 50, 260, 70, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(250, 60, text="RB", fill="white")
        
        # Triggers indicators
        self.canvas.create_text(30, 20, text="LT", fill="white", font=("Helvetica", 10, "bold"))
        self.lt_bg = self.canvas.create_rectangle(20, 40, 40, 100, outline="gray", width=2)
        self.lt_fill = self.canvas.create_rectangle(20, 100, 40, 100, fill="#a83232")

        self.canvas.create_text(370, 20, text="RT", fill="white", font=("Helvetica", 10, "bold"))
        self.rt_bg = self.canvas.create_rectangle(360, 40, 380, 100, outline="gray", width=2)
        self.rt_fill = self.canvas.create_rectangle(360, 100, 380, 100, fill="#1f6aa5")
        
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
        self.check_for_updates()
        # The background thread will prompt if an update is found.
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
        self.save_curves()
        self.root.withdraw()

    def save_curves(self):
        try:
            settings = {
                'lt_points': self.lt_graph.points,
                'lt_max_time': self.lt_graph.max_time,
                'rt_points': self.rt_graph.points,
                'rt_max_time': self.rt_graph.max_time,
                'mappings': self.get_mappings(),
            }
            with open("curves.json", "w") as cf:
                json.dump(settings, cf)
        except: pass
        
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

                    else:
                        err_msg = res.stderr[-500:] if res.stderr else res.stdout[-500:]
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to flash firmware:\n{err_msg}"))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
                
                self.running = True
                threading.Thread(target=self.emulator_loop, daemon=True).start()
                self.root.after(0, lambda: self.status_var.set("Status: Running..."))

            threading.Thread(target=flash_thread, daemon=True).start()

    def update_ui(self, lx, ly, rx, ry, btns, lt_val=0.0, rt_val=0.0):
        self.canvas.coords(self.joy_l_dot, 95 + lx*30, 65 + ly*30, 105 + lx*30, 75 + ly*30)
        self.canvas.coords(self.joy_r_dot, 295 + rx*30, 65 + ry*30, 305 + rx*30, 75 + ry*30)
        
        self.canvas.itemconfig(self.btn_a_ind, fill="#2b6b3e" if btns.get('A') else "#2b2b2b")
        self.canvas.itemconfig(self.btn_b_ind, fill="#a83232" if btns.get('B') else "#2b2b2b")
        self.canvas.itemconfig(self.btn_x_ind, fill="#1f6aa5" if btns.get('X') else "#2b2b2b")
        self.canvas.itemconfig(self.btn_y_ind, fill="#b59c2a" if btns.get('Y') else "#2b2b2b")
        self.canvas.itemconfig(self.btn_lb_ind, fill="#2b6b3e" if btns.get('LB') else "#2b2b2b")
        self.canvas.itemconfig(self.btn_rb_ind, fill="#2b6b3e" if btns.get('RB') else "#2b2b2b")
        
        lt_val = max(0.0, min(1.0, lt_val))
        rt_val = max(0.0, min(1.0, rt_val))
        self.canvas.coords(self.lt_fill, 20, 100 - (lt_val * 60), 40, 100)
        self.canvas.coords(self.rt_fill, 360, 100 - (rt_val * 60), 380, 100)

    
    def open_curve_editor(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Trigger Curve Editor")
        win.geometry("600x400")
        win.attributes("-topmost", True)
        
        ctk.CTkSwitch(win, text="Use PC Curve Simulation (Ignores ESP32 linear scaling)", variable=self.use_pc_simulation).pack(pady=10)
        
        frame = ctk.CTkFrame(win, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10)
        
        lf = ctk.CTkFrame(frame)
        lf.pack(side="left", expand=True, fill="both", padx=5)
        ctk.CTkLabel(lf, text="Left Trigger (LT)").pack()
        old_pts = self.lt_graph.points; old_max = self.lt_graph.max_time
        self.lt_graph = DraggableGraph(lf, width=250, height=150)
        self.lt_graph.points = old_pts; self.lt_graph.max_time = old_max; self.lt_graph.draw()
        self.lt_graph.pack(pady=5)
        self.lt_graph.bind("<ButtonRelease-1>", lambda e: self.save_curves())
        
        l_entry = ctk.CTkEntry(lf, width=80)
        l_entry.insert(0, str(self.lt_graph.max_time))
        l_entry.pack()
        ctk.CTkButton(lf, text="Update Max Time (ms)", command=lambda: self.update_max_time(self.lt_graph, l_entry)).pack(pady=5)
        
        rf = ctk.CTkFrame(frame)
        rf.pack(side="right", expand=True, fill="both", padx=5)
        ctk.CTkLabel(rf, text="Right Trigger (RT)").pack()
        old_pts = self.rt_graph.points; old_max = self.rt_graph.max_time
        self.rt_graph = DraggableGraph(rf, width=250, height=150)
        self.rt_graph.points = old_pts; self.rt_graph.max_time = old_max; self.rt_graph.draw()
        self.rt_graph.pack(pady=5)
        self.rt_graph.bind("<ButtonRelease-1>", lambda e: self.save_curves())
        
        r_entry = ctk.CTkEntry(rf, width=80)
        r_entry.insert(0, str(self.rt_graph.max_time))
        r_entry.pack()
        ctk.CTkButton(rf, text="Update Max Time (ms)", command=lambda: self.update_max_time(self.rt_graph, r_entry)).pack(pady=5)
        
    def update_max_time(self, graph, entry):
        try:
            graph.max_time = int(entry.get())
            graph.draw()
            self.save_curves()
        except: pass

    def get_mappings(self):
        try:
            return {
                "A": int(self.map_a.get()),
                "B": int(self.map_b.get()),
                "X": int(self.map_x.get()),
                "Y": int(self.map_y.get()),
                "LB": int(self.map_lb.get()),
                "RB": int(self.map_rb.get())
            }
        except ValueError:
            return {"A": 0, "B": 1, "X": 2, "Y": 3, "LB": 4, "RB": 5}

    def emulator_loop(self):
        while self.running:
            if not self.gamepad:
                time.sleep(1)
                continue
                
            bt_active = self.run_bluetooth_cycle()
            
            usb_active = False
            if not bt_active:
                usb_active = self.run_usb_cycle()
                
            if not bt_active and not usb_active:
                self.root.after(0, lambda: self.status_var.set("Status: Looking for controller (BT/USB)..."))
                self.root.after(0, lambda: self.device_var.set("Device: None"))
                
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
                    self.root.after(0, lambda: self.status_var.set("Status: Bluetooth Controller Connected!"))
                    self.root.after(0, lambda n=name: self.device_var.set(f"Device: {n} (Bluetooth)"))
                    if self.ser:
                        self.ser.close()
                        self.ser = None
                    break
                else:
                    joy.quit()
            if not self.joystick:
                return False
                
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
                
            if self.joystick.get_numaxes() >= 6:
                rx = self.joystick.get_axis(2)
                ry = self.joystick.get_axis(5)
                
                if self.inv_rx.get(): rx = -rx
                if self.inv_ry.get(): ry = -ry
                
                self.gamepad.right_joystick(x_value=int(rx * 32767), y_value=int(ry * 32767))
                
                lt_val = self.joystick.get_axis(3)
                rt_val = self.joystick.get_axis(4)
                
                lt_val = (lt_val + 1.0) / 2.0
                rt_val = (rt_val + 1.0) / 2.0
                
                self.gamepad.left_trigger_float(value_float=lt_val)
                self.gamepad.right_trigger_float(value_float=rt_val)

                if self.use_pc_simulation.get() and self.lt_graph and self.rt_graph and self.joystick.get_numbuttons() >= 8:
                    lt_btn = self.joystick.get_button(6) 
                    rt_btn = self.joystick.get_button(7) 
                    
                    curr_time = time.time()
                    elapsed_ms = (curr_time - getattr(self, 'last_update_time', curr_time)) * 1000.0
                    self.last_update_time = curr_time
                    
                    if lt_btn: self.lt_time += elapsed_ms
                    else: self.lt_time -= elapsed_ms * 2.0 
                    self.lt_time = max(0.0, min(self.lt_graph.max_time, self.lt_time))
                    
                    if rt_btn: self.rt_time += elapsed_ms
                    else: self.rt_time -= elapsed_ms * 2.0
                    self.rt_time = max(0.0, min(self.rt_graph.max_time, self.rt_time))
                    
                    lt_val = self.lt_graph.get_pressure(self.lt_time)
                    rt_val = self.rt_graph.get_pressure(self.rt_time)
                    
                    self.gamepad.left_trigger_float(value_float=lt_val)
                    self.gamepad.right_trigger_float(value_float=rt_val)

            elif self.joystick.get_numaxes() >= 4:
                rx = self.joystick.get_axis(2)
                ry = self.joystick.get_axis(3)
                if self.inv_rx.get(): rx = -rx
                if self.inv_ry.get(): ry = -ry
                self.gamepad.right_joystick(x_value=int(rx * 32767), y_value=int(ry * 32767))
                lt_val, rt_val = 0.0, 0.0
                
            for btn_name, xbox_btn in [("A", vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
                                       ("B", vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
                                       ("X", vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
                                       ("Y", vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
                                       ("LB", vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
                                       ("RB", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)]:
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
            self.root.after(0, self.update_ui, lx, ly, rx, ry, btns_state, lt_val, rt_val)
            return True
            
        except Exception as e:
            self.joystick.quit()
            self.joystick = None
            err_msg = str(e)
            self.root.after(0, lambda m=err_msg: self.status_var.set(f"Status: Controller Disconnected! ({m})"))
            self.root.after(0, lambda: self.device_var.set("Device: None"))
            return False
            
    def run_usb_cycle(self):
        port = self.com_var.get()
        if not port or port == "No COM Ports" or port == "Select COM Port":
            return False
            
        if not self.ser or self.ser.port != port:
            try:
                if self.ser: self.ser.close()
                self.ser = serial.Serial(port, 115200, timeout=0)
                self.root.after(0, lambda: self.status_var.set("Status: USB Serial Connected!"))
                self.root.after(0, lambda p=port: self.device_var.set(f"Device: ESP32 ({p})"))
                if self.joystick:
                    self.joystick.quit()
                    self.joystick = None
            except:
                if self.ser:
                    self.ser.close()
                    self.ser = None
                return False

        try:
            line = self.ser.readline().decode('utf-8').strip()
            if not line: return True
            
            parts = line.split(',')
            lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0
            btns_state = {}
            mapping = self.get_mappings()
            
            for part in parts:
                if ':' not in part: continue
                key, val = part.split(':')
                try: val = int(val)
                except: continue
                
                if key == 'X':
                    lx = (val - 1800) / 1800.0
                    lx = max(-1.0, min(1.0, lx))
                elif key == 'Y':
                    ly = (val - 1800) / 1800.0
                    ly = max(-1.0, min(1.0, ly))
                elif key == 'B':
                    for btn_name, xbox_btn in [("A", vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
                                               ("B", vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
                                               ("X", vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
                                               ("Y", vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
                                               ("LB", vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
                                               ("RB", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)]:
                        hw_idx = mapping.get(btn_name, 0)
                        is_pressed = not bool(val & (1 << hw_idx))
                        btns_state[btn_name] = is_pressed
                        if is_pressed: self.gamepad.press_button(button=xbox_btn)
                        else: self.gamepad.release_button(button=xbox_btn)
            
            if self.inv_lx.get(): lx = -lx
            if self.inv_ly.get(): ly = -ly
            
            self.gamepad.left_joystick(x_value=int(lx * 32767), y_value=int(ly * 32767))
            
            lt_val, rt_val = 0.0, 0.0
            if self.use_pc_simulation.get() and self.lt_graph and self.rt_graph:
                lt_btn = btns_state.get('LT', False) # If LT is not physically wired, we map it manually or assume from a button? 
                # Wait, mapping doesn't have LT/RT, they mapped LB/RB. Let's use mapping logic:
                # Actually earlier the user wanted button 4 for RT and 22 for LT
                lt_btn = not bool(val & (1 << 22)) if 'val' in locals() else False
                rt_btn = not bool(val & (1 << 4)) if 'val' in locals() else False
                
                curr_time = time.time()
                elapsed_ms = (curr_time - getattr(self, 'last_update_time', curr_time)) * 1000.0
                self.last_update_time = curr_time
                
                if lt_btn: self.lt_time += elapsed_ms
                else: self.lt_time -= elapsed_ms * 2.0
                self.lt_time = max(0.0, min(self.lt_graph.max_time, self.lt_time))
                
                if rt_btn: self.rt_time += elapsed_ms
                else: self.rt_time -= elapsed_ms * 2.0
                self.rt_time = max(0.0, min(self.rt_graph.max_time, self.rt_time))
                
                lt_val = self.lt_graph.get_pressure(self.lt_time)
                rt_val = self.rt_graph.get_pressure(self.rt_time)
                
                self.gamepad.left_trigger_float(value_float=lt_val)
                self.gamepad.right_trigger_float(value_float=rt_val)
                
            self.gamepad.update()
            self.root.after(0, self.update_ui, lx, ly, rx, ry, btns_state, lt_val, rt_val)
            return True
            
        except Exception as e:
            self.ser.close()
            self.ser = None
            err_msg = str(e)
            self.root.after(0, lambda m=err_msg: self.status_var.set(f"Status: Serial Disconnected! ({m})"))
            self.root.after(0, lambda: self.device_var.set("Device: None"))
            return False

if __name__ == "__main__":
    import customtkinter as ctk
    root = ctk.CTk()
    app = X360CE_EmulatorApp(root)
    root.mainloop()
