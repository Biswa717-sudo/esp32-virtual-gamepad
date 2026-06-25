import os
import re

file_path = r"D:\gamepad\pc_gamepad.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove self.mode definition
content = content.replace('self.mode = ctk.StringVar(value="Bluetooth")\n', '')

# 2. Replace UI buttons
old_ui = '''        ctk.CTkRadioButton(btn_frame3, text="Bluetooth (DInput)", variable=self.mode, value="Bluetooth", command=self.switch_mode).pack(side="left", padx=15)
        ctk.CTkRadioButton(btn_frame3, text="USB", variable=self.mode, value="USB", command=self.switch_mode).pack(side="left", padx=15)'''
new_ui = '''        ctk.CTkLabel(btn_frame3, text="Auto Detect (Bluetooth & USB)").pack(side="left", padx=15)'''
content = content.replace(old_ui, new_ui)

# 3. Remove switch_mode usage
old_flash = '''                        if mode_flash == "bluetooth":
                            self.mode.set("Bluetooth")
                        else:
                            self.mode.set("USB")
                        self.root.after(0, self.switch_mode)'''
content = content.replace(old_flash, '')

# 4. Remove switch_mode function completely
old_switch = '''    def switch_mode(self):
        self.update_ui(0, 0, 0, 0, {})
        if self.mode.get() == "USB":
            self.status_var.set("Status: Connecting to Serial Port...")
        else:
            self.status_var.set("Status: Looking for physical controller...")
        
    def update_ui'''
content = content.replace(old_switch, '    def update_ui')

# 5. Replace emulator_loop, run_bluetooth_cycle, run_usb_cycle
# First find where emulator_loop starts and the end of run_usb_cycle
start_idx = content.find("    def emulator_loop(self):")
if start_idx != -1:
    new_methods = '''    def emulator_loop(self):
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
'''

    content = content[:start_idx] + new_methods

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched successfully")
