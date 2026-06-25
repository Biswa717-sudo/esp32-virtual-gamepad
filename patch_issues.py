import os
import json

file_path = r"D:\gamepad\pc_gamepad.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix the updater
if "import ctypes" not in content:
    content = content.replace("import time\nimport json", "import time\nimport json\nimport ctypes")

old_updater = '''                # Run the installer silently and kill the current app
                subprocess.Popen([installer_path, "/SILENT"])'''
new_updater = '''                # Run the installer and kill the current app
                ctypes.windll.shell32.ShellExecuteW(None, "runas", installer_path, "/SILENT", None, 1)'''
content = content.replace(old_updater, new_updater)

# 2. Add 'mappings' to curves.json save block
old_save = '''            settings = {
                'lt_points': self.lt_graph.points,
                'lt_max_time': self.lt_graph.max_time,
                'rt_points': self.rt_graph.points,
                'rt_max_time': self.rt_graph.max_time,
            }'''
new_save = '''            settings = {
                'lt_points': self.lt_graph.points,
                'lt_max_time': self.lt_graph.max_time,
                'rt_points': self.rt_graph.points,
                'rt_max_time': self.rt_graph.max_time,
                'mappings': self.get_mappings(),
            }'''
content = content.replace(old_save, new_save)

# 3. Load mappings after OptionMenu creation
old_lb_rb = '''        ctk.CTkLabel(frame_map, text="LB:").grid(row=3, column=0, padx=5, pady=5)
        self.map_lb = ctk.CTkOptionMenu(frame_map, values=btns, width=60); self.map_lb.grid(row=3, column=1, padx=5, pady=5); self.map_lb.set("4")
        
        ctk.CTkLabel(frame_map, text="RB:").grid(row=3, column=2, padx=5, pady=5)
        self.map_rb = ctk.CTkOptionMenu(frame_map, values=btns, width=60); self.map_rb.grid(row=3, column=3, padx=5, pady=5); self.map_rb.set("5")'''

new_lb_rb = '''        ctk.CTkLabel(frame_map, text="LB:").grid(row=3, column=0, padx=5, pady=5)
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
'''
content = content.replace(old_lb_rb, new_lb_rb)

# Add bind to save when mappings change
content = content.replace('''self.map_a = ctk.CTkOptionMenu(frame_map, values=btns, width=60);''', '''self.map_a = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves());''')
content = content.replace('''self.map_b = ctk.CTkOptionMenu(frame_map, values=btns, width=60);''', '''self.map_b = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves());''')
content = content.replace('''self.map_x = ctk.CTkOptionMenu(frame_map, values=btns, width=60);''', '''self.map_x = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves());''')
content = content.replace('''self.map_y = ctk.CTkOptionMenu(frame_map, values=btns, width=60);''', '''self.map_y = ctk.CTkOptionMenu(frame_map, values=btns, width=60, command=lambda e: self.save_curves());''')


with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched settings and updater!")
