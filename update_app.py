import sys
import time

with open('pc_gamepad.py', 'r', encoding='utf-8') as f:
    code = f.read()

graph_class = '''
class DraggableGraph(tk.Canvas):
    def __init__(self, parent, width=250, height=150, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#1e1e1e", highlightthickness=1, highlightbackground="gray", **kwargs)
        self.width = width
        self.height = height
        self.points = [(0, height), (width//2, height//2), (width, 0)]
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
            x = max(0, min(self.width, event.x))
            y = max(0, min(self.height, event.y))
            self.points[self.selected_point] = (x, y)
            self.points.sort(key=lambda p: p[0])
            self.draw()

    def on_release(self, event): self.selected_point = None
        
    def get_pressure(self, current_time):
        if current_time >= self.max_time: return 1.0
        if current_time <= 0: return 0.0
        xt = (current_time / self.max_time) * self.width
        for i in range(len(self.points)-1):
            p0, p1 = self.points[i], self.points[i+1]
            if p0[0] <= xt <= p1[0]:
                if p1[0] == p0[0]: return 1.0 - (p1[1]/self.height)
                t = (xt - p0[0]) / (p1[0] - p0[0])
                y = p0[1] + t * (p1[1] - p0[1])
                return max(0.0, min(1.0, 1.0 - (y / self.height)))
        return 1.0
'''

if 'class DraggableGraph' not in code:
    code = code.replace('class X360CE_EmulatorApp:', graph_class + '\nclass X360CE_EmulatorApp:')

# Inject state variables
init_inj = '''        self.use_pc_simulation = ctk.BooleanVar(value=True)
        self.lt_time = 0.0
        self.rt_time = 0.0
        self.last_update_time = time.time()
        self.lt_graph = None
        self.rt_graph = None
'''
if 'self.use_pc_simulation' not in code:
    code = code.replace('self.mode = ctk.StringVar(value="Bluetooth")', 'self.mode = ctk.StringVar(value="Bluetooth")\n' + init_inj)

# Inject Graph UI
ui_inj = '''
        # Graph Editor Button
        ctk.CTkButton(btn_frame3, text="Open Curve Editor", command=self.open_curve_editor, fg_color="#1f6aa5").pack(side="left", padx=10)
'''
if 'Open Curve Editor' not in code:
    code = code.replace('self.refresh_ports()', 'self.refresh_ports()\n' + ui_inj)

methods_inj = '''
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
        if not self.lt_graph: self.lt_graph = DraggableGraph(lf, width=250, height=150)
        else:
            old_pts = self.lt_graph.points; old_max = self.lt_graph.max_time
            self.lt_graph = DraggableGraph(lf, width=250, height=150)
            self.lt_graph.points = old_pts; self.lt_graph.max_time = old_max; self.lt_graph.draw()
        self.lt_graph.pack(pady=5)
        
        l_entry = ctk.CTkEntry(lf, width=80)
        l_entry.insert(0, str(self.lt_graph.max_time))
        l_entry.pack()
        ctk.CTkButton(lf, text="Update Max Time (ms)", command=lambda: self.update_max_time(self.lt_graph, l_entry)).pack(pady=5)
        
        rf = ctk.CTkFrame(frame)
        rf.pack(side="right", expand=True, fill="both", padx=5)
        ctk.CTkLabel(rf, text="Right Trigger (RT)").pack()
        if not self.rt_graph: self.rt_graph = DraggableGraph(rf, width=250, height=150)
        else:
            old_pts = self.rt_graph.points; old_max = self.rt_graph.max_time
            self.rt_graph = DraggableGraph(rf, width=250, height=150)
            self.rt_graph.points = old_pts; self.rt_graph.max_time = old_max; self.rt_graph.draw()
        self.rt_graph.pack(pady=5)
        
        r_entry = ctk.CTkEntry(rf, width=80)
        r_entry.insert(0, str(self.rt_graph.max_time))
        r_entry.pack()
        ctk.CTkButton(rf, text="Update Max Time (ms)", command=lambda: self.update_max_time(self.rt_graph, r_entry)).pack(pady=5)
        
    def update_max_time(self, graph, entry):
        try:
            graph.max_time = int(entry.get())
            graph.draw()
        except: pass
'''
if 'def open_curve_editor' not in code:
    code = code.replace('def get_mappings', methods_inj + '\n    def get_mappings')

# Inject PC simulation logic into emulator_loop
sim_logic = '''
            curr_time = time.time()
            elapsed_ms = (curr_time - self.last_update_time) * 1000.0
            self.last_update_time = curr_time
'''
if 'curr_time = time.time()' not in code:
    code = code.replace('current_mode = self.mode.get()', sim_logic + '\n            current_mode = self.mode.get()')

bt_sim = '''
                if self.use_pc_simulation.get() and self.lt_graph and self.rt_graph and self.joystick.get_numbuttons() >= 8:
                    lt_btn = self.joystick.get_button(6) # Button 7 is index 6
                    rt_btn = self.joystick.get_button(7) # Button 8 is index 7
                    
                    if lt_btn: self.lt_time += elapsed_ms
                    else: self.lt_time -= elapsed_ms * 2.0 # Ramp down twice as fast
                    self.lt_time = max(0.0, min(self.lt_graph.max_time, self.lt_time))
                    
                    if rt_btn: self.rt_time += elapsed_ms
                    else: self.rt_time -= elapsed_ms * 2.0
                    self.rt_time = max(0.0, min(self.rt_graph.max_time, self.rt_time))
                    
                    lt_val = self.lt_graph.get_pressure(self.lt_time)
                    rt_val = self.rt_graph.get_pressure(self.rt_time)
                    
                    self.gamepad.left_trigger_float(value_float=lt_val)
                    self.gamepad.right_trigger_float(value_float=rt_val)
'''
if 'if self.use_pc_simulation.get()' not in code:
    code = code.replace('self.gamepad.right_trigger_float(value_float=rt_val)', 'self.gamepad.right_trigger_float(value_float=rt_val)\n' + bt_sim)

with open('pc_gamepad.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Updated pc_gamepad.py successfully")
