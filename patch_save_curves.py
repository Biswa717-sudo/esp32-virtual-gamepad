import os
import json

file_path = r"D:\gamepad\pc_gamepad.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

if "import json" not in content:
    content = content.replace("import time", "import time\nimport json")

# Modify __init__ to include hidden_frame and load settings
init_old = '''        self.use_pc_simulation = ctk.BooleanVar(value=True)
        self.lt_time = 0.0
        self.rt_time = 0.0
        self.last_update_time = time.time()
        self.lt_graph = None
        self.rt_graph = None
        
        try:'''

init_new = '''        self.use_pc_simulation = ctk.BooleanVar(value=True)
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
        
        try:'''

content = content.replace(init_old, init_new)

# Modify hide_window to save curves before hiding/closing
hide_old = '''    def hide_window(self):
        self.root.withdraw()'''

hide_new = '''    def hide_window(self):
        self.save_curves()
        self.root.withdraw()

    def save_curves(self):
        try:
            settings = {
                'lt_points': self.lt_graph.points,
                'lt_max_time': self.lt_graph.max_time,
                'rt_points': self.rt_graph.points,
                'rt_max_time': self.rt_graph.max_time,
            }
            with open("curves.json", "w") as cf:
                json.dump(settings, cf)
        except: pass'''

content = content.replace(hide_old, hide_new)


# Modify open_curve_editor to just pack the graphs in the new window!
curve_old = '''        lf = ctk.CTkFrame(frame)
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
        ctk.CTkButton(rf, text="Update Max Time (ms)", command=lambda: self.update_max_time(self.rt_graph, r_entry)).pack(pady=5)'''

# Instead of re-instantiating, we just use the existing self.lt_graph and repack it? No, in Tkinter you can't repack a Canvas into a new Toplevel without issues usually. But wait! A widget CAN be repacked to a new parent by using `.tk.call` or rebuilding it.
# Actually, the easiest is to just let it rebuild, and then on window close (or just update_max_time / on_drag), update the `curves.json`.
# Let's intercept `update_max_time` to save!

curve_new = '''        lf = ctk.CTkFrame(frame)
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
        ctk.CTkButton(rf, text="Update Max Time (ms)", command=lambda: self.update_max_time(self.rt_graph, r_entry)).pack(pady=5)'''

content = content.replace(curve_old, curve_new)

# Modify update_max_time to save
update_max_old = '''    def update_max_time(self, graph, entry):
        try:
            graph.max_time = int(entry.get())
            graph.draw()
        except: pass'''

update_max_new = '''    def update_max_time(self, graph, entry):
        try:
            graph.max_time = int(entry.get())
            graph.draw()
            self.save_curves()
        except: pass'''
        
content = content.replace(update_max_old, update_max_new)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Curves Save Patched!")
