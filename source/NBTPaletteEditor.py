import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import nbtlib
from nbtlib import tag

# ----------------- COLORS -----------------
BG_COLOR = "#0d1b2a"
ENTRY_BG = "#122235"
ENTRY_HIGHLIGHT = "#1f4570"
TEXT_COLOR = "#e0e1dd"
ORIGINAL_TEXT_COLOR = "#9ad3e8"
HEADER_COLOR = "#0a84d0"
ENTRY_TEXT_COLOR = "#ffffff"
FONT = ("Consolas", 10)

# ----------------- App Setup -----------------
root = tk.Tk()
root.title("NBT Block Replacer")
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)

icon_path = os.path.join(base_path, "icon.ico")
if os.path.exists(icon_path):
    try:
        root.iconbitmap(icon_path)
    except tk.TclError:
        pass
root.geometry("1100x700")
root.configure(bg=BG_COLOR)

style = ttk.Style(root)
style.theme_use("clam")
style.configure("TButton", padding=6)

# variables (create after root)
modid_var = tk.StringVar(root)
selected_folder = ""
entries_map = {}
all_files_data = {}

# Ctrl+D multi-edit state
multi_group = []            
multi_original_texts = {}
multi_selected_substring = ""


# ----------------- Helper Functions -----------------
def select_folder_action():
    global selected_folder
    folder = filedialog.askdirectory(title="Select Input Folder")
    if folder:
        selected_folder = folder
        folder_label.config(text=selected_folder)
        load_files(selected_folder)

def load_files(folder):
    for widget in scroll_frame.winfo_children():
        widget.destroy()
    entries_map.clear()
    all_files_data.clear()
    clear_multi_group()

    modid = modid_var.get().strip()
    if not modid:
        messagebox.showerror("Error", "Please enter a Mod ID (e.g. ad_astra) before loading.")
        return

    nb_files = [f for f in os.listdir(folder) if f.lower().endswith(".nbt")]
    if not nb_files:
        messagebox.showinfo("No files", "No .nbt files found in the selected folder.")
        return

    unique_blocks = set()
    for filename in nb_files:
        path = os.path.join(folder, filename)
        try:
            nbt_data = nbtlib.load(path)
        except Exception as e:
            print(f"Failed to load {filename}: {e}")
            continue
        all_files_data[path] = nbt_data

        if "palette" in nbt_data:
            try:
                palette = nbt_data["palette"]
                for entry in palette:
                    try:
                        name_value = entry.get("Name")
                    except Exception:
                        name_value = None
                    if name_value is not None:
                        name_str = str(name_value)
                        if name_str.startswith(f"{modid}:"):
                            unique_blocks.add(name_str)
            except Exception:
                pass

    unique_blocks = sorted(unique_blocks)

    header_orig = tk.Label(scroll_frame, text="Original", bg=BG_COLOR, fg=ORIGINAL_TEXT_COLOR, font=("Segoe UI", 10, "bold"))
    header_new  = tk.Label(scroll_frame, text="Replacement", bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 10, "bold"))
    header_orig.grid(row=0, column=0, sticky="w", padx=6, pady=(6,2))
    header_new.grid(row=0, column=1, sticky="w", padx=6, pady=(6,2))

    for i, block in enumerate(unique_blocks, start=1):
        lbl = tk.Label(scroll_frame, text=block, bg=BG_COLOR, fg=ORIGINAL_TEXT_COLOR, anchor="w", font=FONT)
        lbl.grid(row=i, column=0, sticky="w", padx=(6,12), pady=2)

        ent = tk.Entry(scroll_frame, bg=ENTRY_BG, fg=ENTRY_TEXT_COLOR, insertbackground="white", font=FONT, width=70)
        ent.insert(0, block)
        ent.grid(row=i, column=1, sticky="ew", padx=(6,12), pady=2)

        entries_map[ent] = block

        ent.bind("<Button-1>", lambda e: e.widget.focus_set())

    scroll_frame.grid_columnconfigure(0, weight=0)
    scroll_frame.grid_columnconfigure(1, weight=1)

    messagebox.showinfo("Loaded", f"Loaded {len(unique_blocks)} unique blocks from '{modid}' across {len(all_files_data)} files.")


def apply_replacements():
    if not entries_map:
        messagebox.showerror("Error", "No blocks loaded to replace.")
        return
    if not selected_folder:
        messagebox.showerror("Error", "No folder selected.")
        return

    replacements = {}
    for widget, orig_name in entries_map.items():
        newval = widget.get().strip()
        if newval != orig_name:
            replacements[orig_name] = newval

    output_folder = selected_folder.rstrip("/\\") + "_modified"
    os.makedirs(output_folder, exist_ok=True)

    for filepath, nbt_data in all_files_data.items():
        if "palette" in nbt_data:
            palette = nbt_data["palette"]
            for entry in palette:
                try:
                    name_value = entry.get("Name")
                except Exception:
                    name_value = None
                if name_value is None:
                    continue
                name_str = str(name_value)
                if name_str in replacements:
                    new_name = replacements[name_str]
                    entry["Name"] = tag.String(new_name)

        out_path = os.path.join(output_folder, os.path.basename(filepath))
        try:
            nbt_data.save(out_path)
        except Exception as e:
            messagebox.showerror("Save error", f"Failed to save {out_path}:\n{e}")
            return

    messagebox.showinfo("Done", f"Modified files saved to:\n{output_folder}")


# ----------------- Ctrl+D Multi-edit Implementation -----------------
def clear_multi_group():
    global multi_group, multi_original_texts, multi_selected_substring
    for w in multi_group:
        try:
            w.config(bg=ENTRY_BG)
            w.selection_clear()
        except Exception:
            pass
    multi_group = []
    multi_original_texts = {}
    multi_selected_substring = ""

def ctrl_d_handler(event=None):
    """Triggered on Ctrl+D. Collect all occurrences of the selected substring in all replacement entries,
       open an overlay entry where typing will replace that substring across matched entries."""
    global multi_group, multi_original_texts, multi_selected_substring

    focused = root.focus_get()
    if not isinstance(focused, tk.Entry):
        messagebox.showinfo("Info", "Focus an input box and select some text (Ctrl+D works on the replacement/entry boxes).")
        return "break"

    try:
        sel = focused.selection_get()
    except tk.TclError:
        messagebox.showinfo("Info", "Please select the substring you want to replace inside a replacement input box.")
        return "break"

    sel = str(sel)
    if not sel:
        messagebox.showinfo("Info", "Please select a substring to replace.")
        return "break"

    matched = []
    for widget in list(entries_map.keys()):
        try:
            text = widget.get()
        except Exception:
            continue
        if sel in text:
            matched.append(widget)

    if not matched:
        messagebox.showinfo("No matches", f"No occurrences of '{sel}' found across replacement fields.")
        return "break"

    multi_group = matched
    multi_original_texts = {w: w.get() for w in multi_group}
    multi_selected_substring = sel
    for w in multi_group:
        try:
            w.config(bg=ENTRY_HIGHLIGHT)
            idx = w.get().find(sel)
            if idx >= 0:
                w.selection_range(idx, idx + len(sel))
        except Exception:
            pass

    open_overlay_for_replacement(sel)
    return "break"


overlay_win = None
overlay_entry = None

def open_overlay_for_replacement(selected_text):
    """Create a small overlay Toplevel where user types replacement; updates all matched entries live."""
    global overlay_win, overlay_entry
    if overlay_win is not None and overlay_win.winfo_exists():
        overlay_win.lift()
        return

    overlay_win = tk.Toplevel(root)
    overlay_win.title("Multi Replace")
    overlay_win.configure(bg=HEADER_COLOR)
    overlay_win.transient(root)
    overlay_win.resizable(False, False)

    x = root.winfo_rootx() + 200
    y = root.winfo_rooty() + 80
    overlay_win.geometry(f"+{x}+{y}")

    lbl = tk.Label(overlay_win, text=f"Replace occurrences of: '{selected_text}'", bg=HEADER_COLOR, fg="white", font=("Segoe UI", 9, "bold"))
    lbl.pack(padx=8, pady=(8,4))

    overlay_entry = tk.Entry(overlay_win, width=40, font=FONT)
    overlay_entry.insert(0, selected_text)
    overlay_entry.pack(padx=8, pady=(0,8))
    overlay_entry.focus_set()
    overlay_entry.selection_range(0, tk.END)

    btn_frame = tk.Frame(overlay_win, bg=HEADER_COLOR)
    btn_frame.pack(pady=(0,8), padx=6, fill="x")
    apply_btn = ttk.Button(btn_frame, text="Apply (Enter)", command=overlay_commit)
    apply_btn.pack(side="left", padx=6)
    cancel_btn = ttk.Button(btn_frame, text="Cancel (Esc)", command=overlay_cancel)
    cancel_btn.pack(side="left", padx=6)

    overlay_entry.bind("<KeyRelease>", overlay_live_update)
    overlay_entry.bind("<Return>", lambda e: overlay_commit())
    overlay_entry.bind("<Escape>", lambda e: overlay_cancel())

def overlay_live_update(event=None):
    """On each keystroke in overlay, replace selected substring in all matched entries live (preview)."""
    global multi_group, multi_original_texts, multi_selected_substring
    if not multi_group:
        return
    if overlay_entry is None:
        return

    new_sub = overlay_entry.get()
    old_sub = multi_selected_substring

    for w in multi_group:
        orig_text = multi_original_texts.get(w, w.get())
        try:
            updated = orig_text.replace(old_sub, new_sub)
            w.delete(0, tk.END)
            w.insert(0, updated)
        except Exception:
            pass

def overlay_commit():
    """Finalize the replacement: close overlay and clear highlight state (the Entry widgets now contain updated text)."""
    global overlay_win, overlay_entry, multi_group, multi_original_texts, multi_selected_substring
    if overlay_win is not None:
        try:
            overlay_win.destroy()
        except Exception:
            pass
    overlay_win = None
    overlay_entry = None
    for w in multi_group:
        try:
            w.config(bg=ENTRY_BG)
            w.selection_clear()
        except Exception:
            pass
    multi_group = []
    multi_original_texts = {}
    multi_selected_substring = ""

def overlay_cancel():
    """Cancel: restore original texts and clear overlay."""
    global overlay_win, overlay_entry, multi_group, multi_original_texts, multi_selected_substring
    for w, txt in multi_original_texts.items():
        try:
            w.delete(0, tk.END)
            w.insert(0, txt)
            w.config(bg=ENTRY_BG)
            w.selection_clear()
        except Exception:
            pass
    if overlay_win is not None:
        try:
            overlay_win.destroy()
        except Exception:
            pass
    overlay_win = None
    overlay_entry = None
    multi_group = []
    multi_original_texts = {}
    multi_selected_substring = ""


root.bind_all("<Control-d>", lambda e: ctrl_d_handler(e))


# ----------------- Top Bar UI -----------------
top_bar = tk.Frame(root, bg=HEADER_COLOR, height=40)
top_bar.pack(fill="x")

left_frame = tk.Frame(top_bar, bg=HEADER_COLOR)
left_frame.pack(side="left", padx=8, pady=6)

tk.Label(left_frame, text="Mod ID:", bg=HEADER_COLOR, fg=TEXT_COLOR, font=FONT).pack(side="left", padx=(0,6))
modid_entry = tk.Entry(left_frame, textvariable=modid_var, bg=ENTRY_BG, fg=ENTRY_TEXT_COLOR, insertbackground="white", font=FONT)
modid_entry.pack(side="left", padx=(0,10))

select_btn = ttk.Button(left_frame, text="Select Folder", command=select_folder_action)
select_btn.pack(side="left")

apply_btn = ttk.Button(top_bar, text="Apply and Save", command=apply_replacements)
apply_btn.pack(side="right", padx=12, pady=6)

folder_label = tk.Label(root, text="No folder selected", bg=BG_COLOR, fg=TEXT_COLOR, anchor="w")
folder_label.pack(fill="x", padx=12, pady=(8,0))


# ----------------- Scrollable area -----------------
container = tk.Frame(root, bg=BG_COLOR)
container.pack(fill="both", expand=True, padx=12, pady=12)

canvas = tk.Canvas(container, bg=BG_COLOR, highlightthickness=0)
v_scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=v_scroll.set)

canvas.pack(side="left", fill="both", expand=True)
v_scroll.pack(side="right", fill="y")

scroll_frame = tk.Frame(canvas, bg=BG_COLOR)
canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

def on_frame_config(event):
    canvas.configure(scrollregion=canvas.bbox("all"))

scroll_frame.bind("<Configure>", on_frame_config)

def _on_mousewheel(event):
    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
canvas.bind_all("<MouseWheel>", _on_mousewheel)


# ----------------- Run -----------------
root.mainloop()
