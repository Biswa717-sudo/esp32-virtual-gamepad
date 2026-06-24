import pygame
import vgamepad as vg
import tkinter as tk
import threading
import time

class X360CE_EmulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("x360ce Python Emulator")
        self.root.geometry("500x350")
        
        self.running = True
        self.gamepad = None
        self.joystick = None
        
        # Initialize pygame for joystick reading
        pygame.init()
        pygame.joystick.init()
        
        # UI Elements
        self.status_var = tk.StringVar()
        self.status_var.set("Status: Looking for physical controller...")
        
        tk.Label(root, text="x360ce Python Emulator", font=("Helvetica", 16, "bold")).pack(pady=10)
        tk.Label(root, textvariable=self.status_var, font=("Helvetica", 12)).pack(pady=5)
        
        self.device_var = tk.StringVar()
        self.device_var.set("Device: None")
        tk.Label(root, textvariable=self.device_var, font=("Helvetica", 10), fg="blue").pack(pady=5)
        
        self.emulation_status = tk.StringVar()
        self.emulation_status.set("Emulator OFF")
        self.lbl_emu = tk.Label(root, textvariable=self.emulation_status, font=("Helvetica", 12, "bold"), fg="red")
        self.lbl_emu.pack(pady=10)
        
        # Canvas for visualizing inputs
        self.canvas = tk.Canvas(root, width=400, height=150, bg="#e0e0e0")
        self.canvas.pack(pady=10)
        
        # Left Joy
        self.canvas.create_text(100, 20, text="Left Joystick")
        self.joy_l_bg = self.canvas.create_oval(70, 40, 130, 100, outline="gray", width=2)
        self.joy_l_dot = self.canvas.create_oval(95, 65, 105, 75, fill="red")
        
        # Right Joy
        self.canvas.create_text(300, 20, text="Right Joystick")
        self.joy_r_bg = self.canvas.create_oval(270, 40, 330, 100, outline="gray", width=2)
        self.joy_r_dot = self.canvas.create_oval(295, 65, 305, 75, fill="blue")
        
        # Buttons indicators
        self.btn_a_ind = self.canvas.create_oval(180, 50, 200, 70, fill="white")
        self.canvas.create_text(190, 60, text="A")
        
        self.btn_b_ind = self.canvas.create_oval(210, 50, 230, 70, fill="white")
        self.canvas.create_text(220, 60, text="B")
        
        self.btn_x_ind = self.canvas.create_oval(180, 80, 200, 100, fill="white")
        self.canvas.create_text(190, 90, text="X")
        
        self.btn_y_ind = self.canvas.create_oval(210, 80, 230, 100, fill="white")
        self.canvas.create_text(220, 90, text="Y")
        
        # Start Threads
        self.thread = threading.Thread(target=self.emulator_loop)
        self.thread.daemon = True
        self.thread.start()
        
    def update_ui(self, lx, ly, rx, ry, btns):
        # Update Joystick positions (-1.0 to 1.0) -> (-30 to 30)
        self.canvas.coords(self.joy_l_dot, 95 + lx*30, 65 + ly*30, 105 + lx*30, 75 + ly*30)
        self.canvas.coords(self.joy_r_dot, 295 + rx*30, 65 + ry*30, 305 + rx*30, 75 + ry*30)
        
        self.canvas.itemconfig(self.btn_a_ind, fill="green" if btns.get(0) else "white")
        self.canvas.itemconfig(self.btn_b_ind, fill="red" if btns.get(1) else "white")
        self.canvas.itemconfig(self.btn_x_ind, fill="blue" if btns.get(2) else "white")
        self.canvas.itemconfig(self.btn_y_ind, fill="yellow" if btns.get(3) else "white")

    def emulator_loop(self):
        # 1. Connect physical controller
        while self.running and not self.joystick:
            pygame.joystick.quit()
            pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                joy = pygame.joystick.Joystick(i)
                joy.init()
                name = joy.get_name()
                
                # Ignore virtual gamepads to prevent feedback loop
                if "Xbox 360" not in name and "Virtual" not in name:
                    self.joystick = joy
                    break
                else:
                    joy.quit()
                    
            if not self.joystick:
                time.sleep(1)
                
        if not self.running:
            return
            
        self.root.after(0, lambda: self.status_var.set("Status: Physical Controller Connected!"))
        self.root.after(0, lambda: self.device_var.set(f"Device: {self.joystick.get_name()}"))
        
        # 2. Turn on emulator
        try:
            self.gamepad = vg.VX360Gamepad()
            self.root.after(0, lambda: self.emulation_status.set("Emulator ON (Virtual Xbox 360 Controller)"))
            self.root.after(0, lambda: self.lbl_emu.config(fg="green"))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"Status: Failed to create virtual gamepad: {e}"))
            return
            
        # 3. Read & Forward
        while self.running:
            pygame.event.pump()
            
            lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0
            btns = {}
            
            if self.joystick.get_numaxes() >= 2:
                lx = self.joystick.get_axis(0)
                ly = self.joystick.get_axis(1)
                self.gamepad.left_joystick(x_value=int(lx * 32767), y_value=int(ly * -32767))
                
            if self.joystick.get_numaxes() >= 4:
                rx = self.joystick.get_axis(2)
                ry = self.joystick.get_axis(3)
                self.gamepad.right_joystick(x_value=int(rx * 32767), y_value=int(ry * -32767))
                
            for b in range(min(4, self.joystick.get_numbuttons())):
                is_pressed = self.joystick.get_button(b)
                btns[b] = is_pressed
                
                button_enum = None
                if b == 0: button_enum = vg.XUSB_BUTTON.XUSB_GAMEPAD_A
                elif b == 1: button_enum = vg.XUSB_BUTTON.XUSB_GAMEPAD_B
                elif b == 2: button_enum = vg.XUSB_BUTTON.XUSB_GAMEPAD_X
                elif b == 3: button_enum = vg.XUSB_BUTTON.XUSB_GAMEPAD_Y
                
                if button_enum:
                    if is_pressed: self.gamepad.press_button(button=button_enum)
                    else: self.gamepad.release_button(button=button_enum)
                    
            self.gamepad.update()
            
            # Update UI safely
            self.root.after(0, self.update_ui, lx, ly, rx, ry, btns)
            
            time.sleep(0.01)

if __name__ == "__main__":
    root = tk.Tk()
    app = X360CE_EmulatorApp(root)
    def on_closing():
        app.running = False
        pygame.quit()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
