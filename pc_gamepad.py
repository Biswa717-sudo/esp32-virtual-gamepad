import pygame
import vgamepad as vg
import tkinter as tk
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
import threading
import time
import requests
import tempfile
import ctypes
import serial
import serial.tools.list_ports
import subprocess
import os
import sys
import pystray
from PIL import Image, ImageDraw
import urllib.request
import json

BAUD_RATE = 115200
APP_VERSION = "2.12"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DraggableGraph(tk.Canvas):
    def __init__(self, parent, width=250, height=150, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#1e1e1e", highlightthickness=1, highlightbackground="gray", **kwargs)
        self.width, self.height = width, height
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
                self.selected_point = i; break

    def on_drag(self, event):
        if self.selected_point:
            min_x, max_x = self.points[self.selected_point - 1][0], self.points[self.selected_point + 1][0]
            self.points[self.selected_point] = (max(min_x, min(max_x, event.x)), max(0, min(self.height, event.y)))
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
                y = p0[1] + ((xt - p0[0]) / (p1[0] - p0[0])) * (p1[1] - p0[1])
                return max(0.0, min(1.0, 1.0 - (y / self.height)))
        return 1.0


HW_INPUTS = ["A", "B", "X", "Y", "LB", "RB", "View", "Guide", "Menu", "D-Up", "D-Down", "D-Left", "D-Right", "LT", "RT"]
XBOX_OUTPUTS = ["Unmapped", "A", "B", "X", "Y", "LB", "RB", "View", "Guide", "Menu", "D-Up", "D-Down", "D-Left", "D-Right", "LT", "RT"]

class X360CE_EmulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"ESP32 Virtual Gamepad v{APP_VERSION}")
        self.root.geometry("680x850")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.running = True
        self.is_flashing = False
        self.gamepad = None
        self.joystick = None
        self.ser = None
        
        self.mappings = {}
        self.curves = {}
        self.sim_vars = {}
        self.target_vars = {}
        self.hw_times = {hw: 0.0 for hw in HW_INPUTS}
        self.last_update_time = time.time()
        
        for hw in HW_INPUTS:
            self.mappings[hw] = {"target": hw, "sim": False}
            self.curves[hw] = {"points": [(0,150), (83,100), (166,50), (250,0)], "max_time": 1000}
            
        self.load_curves()
        try: pygame.init(); pygame.joystick.init()
        except: pass

        self.build_ui()
        self.setup_tray()
        self.check_for_updates()
        self.thread = threading.Thread(target=self.emulator_loop, daemon=True)
        self.thread.start()

    def build_ui(self):
        title = ctk.CTkLabel(self.root, text="🎮 Controller Emulator Pro", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=10)
        ctk.CTkButton(self.root, text="Check for App Updates", fg_color="#3a7ebf", width=150, height=25, command=self.check_for_updates_manual).pack(pady=2)

        f_conn = ctk.CTkFrame(self.root)
        f_conn.pack(fill="x", padx=10, pady=5)
        self.com_var = ctk.StringVar()
        self.com_combo = ctk.CTkOptionMenu(f_conn, variable=self.com_var, width=120)
        self.com_combo.pack(side="left", padx=5, pady=5)
        ctk.CTkButton(f_conn, text="↻", width=30, command=self.refresh_ports).pack(side="left", padx=5)
        self.refresh_ports()

        self.status_var = ctk.StringVar(value="Status: Ready.")
        ctk.CTkLabel(f_conn, textvariable=self.status_var).pack(side="left", padx=10)
        self.device_var = ctk.StringVar(value="Device: None")
        ctk.CTkLabel(f_conn, textvariable=self.device_var, text_color="#1f6aa5").pack(side="left", padx=10)

        # Mapping Matrix
        f_map = ctk.CTkScrollableFrame(self.root, height=280)
        f_map.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_map, text="Hardware Input", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=2)
        ctk.CTkLabel(f_map, text="Xbox Output", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5, pady=2)
        ctk.CTkLabel(f_map, text="Analog Sim?", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=5, pady=2)
        
        for i, hw in enumerate(HW_INPUTS):
            r = i + 1
            ctk.CTkLabel(f_map, text=hw).grid(row=r, column=0, padx=5, pady=2)
            
            tvar = ctk.StringVar(value=self.mappings[hw]["target"])
            self.target_vars[hw] = tvar
            opt = ctk.CTkOptionMenu(f_map, variable=tvar, values=XBOX_OUTPUTS, command=lambda v, h=hw: self.on_target_change(h, v))
            opt.grid(row=r, column=1, padx=5, pady=2)
            
            svar = ctk.BooleanVar(value=self.mappings[hw]["sim"])
            self.sim_vars[hw] = svar
            chk = ctk.CTkCheckBox(f_map, text="", variable=svar, command=self.save_curves)
            chk.grid(row=r, column=2, padx=5, pady=2)
            
            btn = ctk.CTkButton(f_map, text="Edit Curve", width=80, command=lambda h=hw: self.open_curve(h))
            btn.grid(row=r, column=3, padx=5, pady=2)
            
            self.on_target_change(hw, tvar.get()) # init state

        # Joystick Inversion
        f_joy = ctk.CTkFrame(self.root)
        f_joy.pack(fill="x", padx=10, pady=5)
        self.inv_lx, self.inv_ly, self.inv_rx, self.inv_ry = (ctk.BooleanVar(value=False), ctk.BooleanVar(value=True), ctk.BooleanVar(value=False), ctk.BooleanVar(value=True))
        ctk.CTkCheckBox(f_joy, text="Inv L-X", variable=self.inv_lx).pack(side="left", padx=15, pady=5)
        ctk.CTkCheckBox(f_joy, text="Inv L-Y", variable=self.inv_ly).pack(side="left", padx=15, pady=5)
        ctk.CTkCheckBox(f_joy, text="Inv R-X", variable=self.inv_rx).pack(side="left", padx=15, pady=5)
        ctk.CTkCheckBox(f_joy, text="Inv R-Y", variable=self.inv_ry).pack(side="left", padx=15, pady=5)

        # Visual Checker
        f_vis = ctk.CTkFrame(self.root)
        f_vis.pack(fill="x", padx=10, pady=5)
        self.canvas = tk.Canvas(f_vis, width=400, height=120, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(pady=5)
        
        # Left Joy
        self.canvas.create_text(80, 15, text="Left Joystick", fill="white", font=("Helvetica", 10, "bold"))
        self.joy_l_bg = self.canvas.create_oval(50, 30, 110, 90, outline="gray", width=2)
        self.joy_l_dot = self.canvas.create_oval(75, 55, 85, 65, fill="#a83232")
        
        # Right Joy
        self.canvas.create_text(320, 15, text="Right Joystick", fill="white", font=("Helvetica", 10, "bold"))
        self.joy_r_bg = self.canvas.create_oval(290, 30, 350, 90, outline="gray", width=2)
        self.joy_r_dot = self.canvas.create_oval(315, 55, 325, 65, fill="#1f6aa5")
        
        # Buttons (A, B, X, Y)
        self.btn_a_ind = self.canvas.create_oval(190, 35, 210, 55, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(200, 45, text="A", fill="white")
        self.btn_b_ind = self.canvas.create_oval(220, 35, 240, 55, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(230, 45, text="B", fill="white")
        self.btn_x_ind = self.canvas.create_oval(190, 65, 210, 85, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(200, 75, text="X", fill="white")
        self.btn_y_ind = self.canvas.create_oval(220, 65, 240, 85, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(230, 75, text="Y", fill="white")
        
        # Bumpers (LB, RB)
        self.btn_lb_ind = self.canvas.create_oval(160, 35, 180, 55, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(170, 45, text="LB", fill="white")
        self.btn_rb_ind = self.canvas.create_oval(250, 35, 270, 55, fill="#2b2b2b", outline="gray")
        self.canvas.create_text(260, 45, text="RB", fill="white")
        
        # Triggers (LT, RT)
        self.canvas.create_text(20, 15, text="LT", fill="white", font=("Helvetica", 10, "bold"))
        self.lt_bg = self.canvas.create_rectangle(10, 30, 30, 90, outline="gray", width=2)
        self.lt_fill = self.canvas.create_rectangle(10, 90, 30, 90, fill="#a83232")

        self.canvas.create_text(380, 15, text="RT", fill="white", font=("Helvetica", 10, "bold"))
        self.rt_bg = self.canvas.create_rectangle(370, 30, 390, 90, outline="gray", width=2)
        self.rt_fill = self.canvas.create_rectangle(370, 90, 390, 90, fill="#1f6aa5")

        # Firmware Buttons
        f_flash = ctk.CTkFrame(self.root)
        f_flash.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(f_flash, text="Flash USB Firmware", fg_color="#2b6b3e", command=lambda: self.flash_firmware("wired")).pack(side="left", expand=True, padx=5, pady=5)
        ctk.CTkButton(f_flash, text="Flash BT Firmware", fg_color="#a83232", command=lambda: self.flash_firmware("bluetooth")).pack(side="left", expand=True, padx=5, pady=5)
        
        try:
            self.gamepad = vg.VX360Gamepad()
        except Exception:
            self.status_var.set("Status: ViGEmBus Missing!")
            ctk.CTkButton(self.root, text="Install ViGEmBus Driver", fg_color="red", command=self.update_vigembus).pack(pady=10)

    def on_target_change(self, hw, val):
        self.mappings[hw]["target"] = val
        self.save_curves()

    def update_visuals(self, lx, ly, rx, ry, lt, rt, btns):
        # joysticks (mapped from -1..1 to -25..25 offset)
        self.canvas.coords(self.joy_l_dot, 75 + lx*25, 55 + ly*25, 85 + lx*25, 65 + ly*25)
        self.canvas.coords(self.joy_r_dot, 315 + rx*25, 55 + ry*25, 325 + rx*25, 65 + ry*25)
        # triggers (mapped from 0..1 to 0..60 height offset)
        self.canvas.coords(self.lt_fill, 10, 90 - (lt * 60), 30, 90)
        self.canvas.coords(self.rt_fill, 370, 90 - (rt * 60), 390, 90)
        # buttons
        self.canvas.itemconfig(self.btn_a_ind, fill="#2b6b3e" if btns.get("A") else "#2b2b2b")
        self.canvas.itemconfig(self.btn_b_ind, fill="#a83232" if btns.get("B") else "#2b2b2b")
        self.canvas.itemconfig(self.btn_x_ind, fill="#1f6aa5" if btns.get("X") else "#2b2b2b")
        self.canvas.itemconfig(self.btn_y_ind, fill="#b59c28" if btns.get("Y") else "#2b2b2b")
        self.canvas.itemconfig(self.btn_lb_ind, fill="white" if btns.get("LB") else "#2b2b2b")
        self.canvas.itemconfig(self.btn_rb_ind, fill="white" if btns.get("RB") else "#2b2b2b")

    def open_curve(self, hw):
        win = ctk.CTkToplevel(self.root)
        win.title(f"Curve Editor: {hw}")
        win.geometry("300x250")
        win.attributes("-topmost", True)
        
        g = DraggableGraph(win, width=250, height=150)
        g.points = [tuple(p) for p in self.curves[hw]["points"]]
        g.max_time = self.curves[hw]["max_time"]
        g.draw()
        g.pack(pady=10)
        g.bind("<ButtonRelease-1>", lambda e: self.update_and_save_curve(hw, g))
        
        e = ctk.CTkEntry(win, width=80)
        e.insert(0, str(g.max_time))
        e.pack(pady=5)
        ctk.CTkButton(win, text="Update Max Time (ms)", command=lambda: self.update_max_time(hw, g, e)).pack()

    def update_and_save_curve(self, hw, g):
        self.curves[hw]["points"] = g.points
        self.save_curves()

    def update_max_time(self, hw, g, entry):
        try:
            g.max_time = int(entry.get())
            g.draw()
            self.curves[hw]["max_time"] = g.max_time
            self.save_curves()
        except: pass

    def load_curves(self):
        try:
            with open("curves.json", "r") as f:
                d = json.load(f)
                if "mappings" in d:
                    for hw, dat in d["mappings"].items():
                        if hw in self.mappings and isinstance(dat, dict):
                            self.mappings[hw] = dat
                if "curves" in d:
                    for hw, dat in d["curves"].items():
                        if hw in self.curves and isinstance(dat, dict):
                            self.curves[hw]["points"] = [tuple(p) for p in dat["points"]]
                            self.curves[hw]["max_time"] = dat["max_time"]
        except: pass

    def save_curves(self):
        for hw in HW_INPUTS:
            if hw in self.target_vars and hw in self.sim_vars:
                self.mappings[hw]["target"] = self.target_vars[hw].get()
                self.mappings[hw]["sim"] = self.sim_vars[hw].get()
        try:
            with open("curves.json", "w") as f:
                json.dump({"mappings": self.mappings, "curves": self.curves}, f)
        except: pass

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if ports:
            self.com_combo.configure(values=ports)
            if not self.com_var.get() or self.com_var.get() not in ports: self.com_combo.set(ports[0])
        else:
            self.com_combo.configure(values=["No COM Ports"]); self.com_combo.set("No COM Ports")

    def emulator_loop(self):
        while self.running:
            if self.is_flashing: time.sleep(1); continue
            if not self.gamepad: time.sleep(1); continue
            bt_active = self.run_bluetooth_cycle()
            usb_active = False
            if not bt_active: usb_active = self.run_usb_cycle()
            if not bt_active and not usb_active:
                self.root.after(0, lambda: self.status_var.set("Looking for controller..."))
                self.root.after(0, lambda: self.device_var.set("Device: None"))
            time.sleep(0.01)

    def process_hw_state(self, hw_state, lx, ly, rx, ry):
        curr_time = time.time()
        el = (curr_time - self.last_update_time) * 1000.0
        self.last_update_time = curr_time

        # Update times
        for hw in HW_INPUTS:
            if hw_state.get(hw, False):
                self.hw_times[hw] += el
            else:
                self.hw_times[hw] -= el * 2.0
            self.hw_times[hw] = max(0.0, min(self.curves[hw]["max_time"], self.hw_times[hw]))

        # Output states
        out_btns = {o: False for o in XBOX_OUTPUTS}
        out_lt = 0.0
        out_rt = 0.0

        for hw in HW_INPUTS:
            tgt = self.mappings[hw]["target"]
            if tgt == "Unmapped": continue
            
            is_pressed = hw_state.get(hw, False)
            
            if tgt in ["LT", "RT"]:
                val = 0.0
                if self.mappings[hw]["sim"]:
                    # Calc curve
                    t = self.hw_times[hw]
                    if t <= 0: val = 0.0
                    elif t >= self.curves[hw]["max_time"]: val = 1.0
                    else:
                        w, h = 250, 150
                        xt = (t / self.curves[hw]["max_time"]) * w
                        pts = self.curves[hw]["points"]
                        if xt <= pts[0][0]: val = 1.0 - (pts[0][1]/h)
                        else:
                            for i in range(len(pts)-1):
                                p0, p1 = pts[i], pts[i+1]
                                if p0[0] <= xt <= p1[0]:
                                    if p1[0] == p0[0]:
                                        val = 1.0 - (p1[1]/h)
                                    else:
                                        y = p0[1] + ((xt - p0[0])/(p1[0] - p0[0]))*(p1[1] - p0[1])
                                        val = max(0.0, min(1.0, 1.0 - (y/h)))
                                    break
                else:
                    val = 1.0 if is_pressed else 0.0
                    
                if tgt == "LT": out_lt = max(out_lt, val)
                if tgt == "RT": out_rt = max(out_rt, val)
            else:
                if is_pressed: out_btns[tgt] = True

        if self.inv_lx.get(): lx = -lx
        if self.inv_ly.get(): ly = -ly
        if self.inv_rx.get(): rx = -rx
        if self.inv_ry.get(): ry = -ry

        self.gamepad.left_joystick(x_value=int(lx * 32767), y_value=int(ly * 32767))
        self.gamepad.right_joystick(x_value=int(rx * 32767), y_value=int(ry * 32767))
        self.gamepad.left_trigger_float(value_float=out_lt)
        self.gamepad.right_trigger_float(value_float=out_rt)

        bmaps = {
            "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A, "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X, "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER, "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "View": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK, "Guide": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE, "Menu": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "D-Up": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, "D-Down": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            "D-Left": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT, "D-Right": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT
        }
        for k, btn in bmaps.items():
            if out_btns[k]: self.gamepad.press_button(button=btn)
            else: self.gamepad.release_button(button=btn)
        self.gamepad.update()
        
        self.root.after(0, lambda: self.update_visuals(lx, ly, rx, ry, out_lt, out_rt, out_btns))

    def run_usb_cycle(self):
        port = self.com_var.get()
        if not port or port == "No COM Ports": return False
        if not self.ser or self.ser.port != port:
            try:
                if self.ser: self.ser.close()
                self.ser = serial.Serial(port, 115200, timeout=0)
                self.root.after(0, lambda: self.status_var.set("USB Connected!"))
                self.root.after(0, lambda p=port: self.device_var.set(f"ESP32 ({p})"))
                if self.joystick: self.joystick.quit(); self.joystick = None
            except:
                if self.ser: self.ser.close(); self.ser = None
                return False

        try:
            line = self.ser.readline().decode('utf-8').strip()
            if not line: return True
            parts = line.split(',')
            lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0
            hw_state = {hw: False for hw in HW_INPUTS}
            b = 0
            for part in parts:
                if ':' not in part: continue
                k, v = part.split(':')
                try: v = int(v)
                except: continue
                if k == 'LX': lx = max(-1.0, min(1.0, v / 32767.0))
                elif k == 'LY': ly = max(-1.0, min(1.0, v / 32767.0))
                elif k == 'B': b = v
            
            hw_state["A"] = bool(b & (1<<0))
            hw_state["B"] = bool(b & (1<<1))
            hw_state["X"] = bool(b & (1<<2))
            hw_state["Y"] = bool(b & (1<<3))
            hw_state["LB"] = bool(b & (1<<4))
            hw_state["RB"] = bool(b & (1<<5))
            hw_state["View"] = bool(b & (1<<6))
            hw_state["Guide"] = bool(b & (1<<7))
            hw_state["Menu"] = bool(b & (1<<8))
            hw_state["D-Up"] = bool(b & (1<<9))
            hw_state["D-Down"] = bool(b & (1<<10))
            hw_state["D-Left"] = bool(b & (1<<11))
            hw_state["D-Right"] = bool(b & (1<<12))
            
            rsUp = bool(b & (1<<13))
            rsDown = bool(b & (1<<14))
            rsLeft = bool(b & (1<<15))
            rsRight = bool(b & (1<<16))
            if rsLeft: rx = -1.0
            elif rsRight: rx = 1.0
            if rsUp: ry = 1.0
            elif rsDown: ry = -1.0
            
            hw_state["LT"] = bool(b & (1<<17))
            hw_state["RT"] = bool(b & (1<<18))

            self.process_hw_state(hw_state, lx, ly, rx, ry)
            return True
        except:
            return False

    def run_bluetooth_cycle(self):
        pygame.event.pump()
        if not self.joystick:
            pygame.joystick.quit(); pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                joy = pygame.joystick.Joystick(i); joy.init()
                name = joy.get_name()
                if "Xbox" not in name and "Virtual" not in name:
                    self.joystick = joy
                    self.root.after(0, lambda: self.status_var.set("Bluetooth Connected!"))
                    self.root.after(0, lambda n=name: self.device_var.set(f"{n} (BT)"))
                    if self.ser: self.ser.close(); self.ser = None
                    break
                else: joy.quit()
            if not self.joystick: return False
                
        try:
            hw_state = {hw: False for hw in HW_INPUTS}
            lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0
            if self.joystick.get_numaxes() >= 2:
                lx = self.joystick.get_axis(0); ly = self.joystick.get_axis(1)
            
            if self.joystick.get_numaxes() >= 6:
                rx = self.joystick.get_axis(2); ry = self.joystick.get_axis(5)
                hw_state["LT"] = self.joystick.get_axis(3) > 0.5
                hw_state["RT"] = self.joystick.get_axis(4) > 0.5
            elif self.joystick.get_numaxes() >= 4:
                rx = self.joystick.get_axis(2); ry = self.joystick.get_axis(3)

            # Pygame Button mapping: 0=A, 1=B, 2=X, 3=Y, 4=LB, 5=RB, 6=Back, 7=Start, 8=L3, 9=R3, 10=Guide
            # In BLEGamepad: BUTTON_1 is A, BUTTON_2 is B...
            # The indices align mostly. 
            num = self.joystick.get_numbuttons()
            if num > 0: hw_state["A"] = self.joystick.get_button(0)
            if num > 1: hw_state["B"] = self.joystick.get_button(1)
            if num > 2: hw_state["X"] = self.joystick.get_button(2)
            if num > 3: hw_state["Y"] = self.joystick.get_button(3)
            if num > 4: hw_state["LB"] = self.joystick.get_button(4)
            if num > 5: hw_state["RB"] = self.joystick.get_button(5)
            if num > 8: hw_state["View"] = self.joystick.get_button(8) # BUTTON_9
            if num > 9: hw_state["Menu"] = self.joystick.get_button(9) # BUTTON_10
            if num > 12: hw_state["Guide"] = self.joystick.get_button(12) # BUTTON_13

            if self.joystick.get_numhats() > 0:
                hx, hy = self.joystick.get_hat(0)
                if hx == -1: hw_state["D-Left"] = True
                elif hx == 1: hw_state["D-Right"] = True
                if hy == 1: hw_state["D-Up"] = True
                elif hy == -1: hw_state["D-Down"] = True

            self.process_hw_state(hw_state, lx, ly, rx, ry)
            return True
        except:
            self.joystick.quit(); self.joystick = None
            return False

    def flash_firmware(self, mode):
        win = ctk.CTkToplevel(self.root)
        win.title(f"Flashing {mode.upper()} Firmware...")
        win.geometry("600x400")
        win.attributes("-topmost", True)
        
        txt = ctk.CTkTextbox(win, width=580, height=380, font=("Courier", 12))
        txt.pack(padx=10, pady=10)
        txt.insert("end", f"Starting {mode} flash process...\n")
        
        def run_flash():
            self.is_flashing = True
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                
            src_dir = os.path.join(base_dir, "src")
            main_cpp = os.path.join(src_dir, "main.cpp")
            main_wired = os.path.join(src_dir, "main_wired.cpp.disabled")
            
            if mode == "wired":
                if os.path.exists(main_cpp): os.rename(main_cpp, main_cpp + ".disabled")
                if os.path.exists(main_wired): os.rename(main_wired, main_cpp)
            
            try:
                if self.ser: 
                    self.ser.close()
                    self.ser = None
                    
                import shutil
                pio_cmd = ["pio", "run", "-t", "upload"]
                if not shutil.which("pio"):
                    py_exe = "python" if shutil.which("python") else ("python3" if shutil.which("python3") else None)
                    if not py_exe:
                        self.root.after(0, lambda: (txt.insert("end", "\nCRITICAL ERROR: Python is not installed on this PC!\nYou must download and install Python from python.org (ensure 'Add to PATH' is checked) before you can flash the firmware.\n"), txt.see("end")))
                        return
                        
                    try:
                        subprocess.check_output([py_exe, "-m", "platformio", "--version"], stderr=subprocess.STDOUT)
                        pio_cmd = [py_exe, "-m", "platformio", "run", "-t", "upload"]
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        self.root.after(0, lambda: (txt.insert("end", "PlatformIO not found! Attempting to auto-install via Python...\n"), txt.see("end")))
                        install_proc = subprocess.Popen([py_exe, "-m", "pip", "install", "platformio"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        for line in iter(install_proc.stdout.readline, ""):
                            self.root.after(0, lambda l=line: (txt.insert("end", l), txt.see("end")))
                        install_proc.wait()
                        pio_cmd = [py_exe, "-m", "platformio", "run", "-t", "upload"]
                        
                process = subprocess.Popen(pio_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=base_dir)
                for line in iter(process.stdout.readline, ""):
                    self.root.after(0, lambda l=line: (txt.insert("end", l), txt.see("end")))
                process.stdout.close()
                process.wait()
                if process.returncode == 0:
                    self.root.after(0, lambda: txt.insert("end", "\nFLASH SUCCESSFUL!\n"))
                else:
                    self.root.after(0, lambda: txt.insert("end", f"\nFLASH FAILED with code {process.returncode}\n"))
            except Exception as e:
                self.root.after(0, lambda: txt.insert("end", f"\nERROR: {str(e)}\nIs PlatformIO (pio) installed and in your system PATH?\n"))
                
            finally:
                if mode == "wired":
                    if os.path.exists(main_cpp): os.rename(main_cpp, main_wired)
                    if os.path.exists(main_cpp + ".disabled"): os.rename(main_cpp + ".disabled", main_cpp)
                self.is_flashing = False
                    
        threading.Thread(target=run_flash, daemon=True).start()

    def update_vigembus(self):
        def task():
            self.root.after(0, lambda: self.status_var.set("Status: Checking for ViGEmBus updates..."))
            try:
                req = urllib.request.Request("https://api.github.com/repos/nefarius/ViGEmBus/releases/latest", headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                
                download_url = None
                filename = ""
                for asset in data.get('assets', []):
                    if asset['name'].endswith('.exe') or asset['name'].endswith('.msi'):
                        download_url = asset['browser_download_url']
                        filename = asset['name']
                        break
                
                if not download_url:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Could not find the driver installer on GitHub."))
                    return
                
                self.root.after(0, lambda: self.status_var.set("Status: Downloading ViGEmBus..."))
                save_path = os.path.join(tempfile.gettempdir(), filename)
                urllib.request.urlretrieve(download_url, save_path)
                
                self.root.after(0, lambda: self.status_var.set("Status: Launching ViGEmBus Installer..."))
                os.startfile(save_path)
                self.root.after(0, lambda: messagebox.showinfo("Success", "ViGEmBus installer downloaded and launched! Please complete the installation."))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Download Error", f"Failed to download ViGEmBus: {e}"))
            finally:
                self.root.after(0, lambda: self.status_var.set("Status: Ready."))
        
        threading.Thread(target=task, daemon=True).start()

    def check_for_updates(self, manual=False):
        def _check():
            if manual:
                self.root.after(0, lambda: self.status_var.set("Checking for updates..."))
            try:
                response = requests.get("https://api.github.com/repos/Biswa717-sudo/esp32-virtual-gamepad/releases/latest", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    latest_version = data["tag_name"].replace("v", "")
                    if latest_version != APP_VERSION:
                        for asset in data.get("assets", []):
                            if asset["name"].endswith(".exe"):
                                download_url = asset["browser_download_url"]
                                self.root.after(0, lambda: self.prompt_update(latest_version, download_url))
                                break
                    elif manual:
                        self.root.after(0, lambda: messagebox.showinfo("No Updates", "You are on the latest version!"))
            except Exception as e:
                if manual: self.root.after(0, lambda: messagebox.showerror("Update Error", str(e)))
            finally:
                if manual: self.root.after(0, lambda: self.status_var.set("Status: Ready."))
        threading.Thread(target=_check, daemon=True).start()

    def check_for_updates_manual(self):
        self.check_for_updates(manual=True)

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
                ctypes.windll.shell32.ShellExecuteW(None, "runas", installer_path, "/SILENT", None, 1)
                self.root.after(0, self.quit_app)
            except Exception as e:
                self.root.after(0, lambda: label.configure(text=f"Download failed! {str(e)}"))
                
        threading.Thread(target=_download, daemon=True).start()

    def setup_tray(self):
        def create_image():
            img = Image.new('RGB', (64, 64), (31, 106, 165))
            ImageDraw.Draw(img).ellipse((16, 16, 48, 48), fill=(255, 255, 255))
            return img
        menu = pystray.Menu(pystray.MenuItem('Show', self.show_window, default=True), pystray.MenuItem('Quit', self.quit_app))
        self.tray_icon = pystray.Icon("Virtual Gamepad", create_image(), "Gamepad Emulator", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_window(self):
        self.save_curves()
        self.root.withdraw()
        
    def show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)
        
    def quit_app(self, icon=None, item=None):
        self.tray_icon.stop()
        self.running = False
        try: pygame.quit()
        except: pass
        if self.ser:
            try: self.ser.close()
            except: pass
        self.root.after(0, self.root.destroy)

if __name__ == "__main__":
    app = ctk.CTk()
    X360CE_EmulatorApp(app)
    app.mainloop()
