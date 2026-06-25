import ctypes
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

DRIVE_TYPES = {
    0: "Unknown",
    1: "No Root Dir",
    2: "Removable",
    3: "Fixed",
    4: "Network",
    5: "CD/DVD/Blu-Ray",
    6: "RAM Disk",
}


def get_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if not (bitmask & (1 << i)):
            continue
        letter = chr(ord("A") + i) + ":"
        root = letter + "\\"
        dtype = ctypes.windll.kernel32.GetDriveTypeW(root)

        vol_buf = ctypes.create_unicode_buffer(1024)
        fs_buf = ctypes.create_unicode_buffer(1024)
        try:
            ctypes.windll.kernel32.GetVolumeInformationW(
                root, vol_buf, ctypes.sizeof(vol_buf),
                None, None, None,
                fs_buf, ctypes.sizeof(fs_buf),
            )
            label = vol_buf.value.strip()
        except OSError:
            label = ""

        if not label:
            label = DRIVE_TYPES.get(dtype, "Drive")

        type_name = DRIVE_TYPES.get(dtype, "Unknown")
        display = f"{letter}  {label}  [{type_name}]"
        drives.append((letter, label, display))
    return drives


def get_exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def sanitize_filename(name):
    invalid = '<>:"/\\|?*'
    cleaned = "".join(c for c in name if c not in invalid).strip()
    return cleaned or "drive"


class ISOCreator:
    def __init__(self, root):
        self.root = root
        self.root.title("ISO Creation Tool")
        self.root.geometry("260x260")
        self.root.resizable(False, False)

        frame = tk.Frame(root, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Select Drive:", font=("Segoe UI", 10)).pack(anchor=tk.W)

        self.drive_var = tk.StringVar()
        self.dropdown = ttk.Combobox(
            frame, textvariable=self.drive_var, state="readonly", width=50
        )
        self.dropdown.pack(fill=tk.X, pady=(4, 10))

        self.refresh_btn = tk.Button(frame, text="Refresh Drives", command=self.refresh)
        self.refresh_btn.pack(pady=(0, 12))

        self.make_btn = tk.Button(
            frame, text="Make ISO", command=self.make_iso,
            bg="#2d7d2d", fg="white",
            font=("Segoe UI", 11, "bold"),
            activebackground="#1f5a1f", activeforeground="white",
            height=2, cursor="hand2",
        )
        self.make_btn.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(frame, textvariable=self.status_var, fg="#555").pack(pady=(12, 0))

        self.refresh()

    def refresh(self):
        self.drives = get_drives()
        options = [d[2] for d in self.drives]
        self.dropdown["values"] = options
        if options:
            self.dropdown.current(0)
        else:
            self.drive_var.set("")

    def make_iso(self):
        idx = self.dropdown.current()
        if idx < 0 or idx >= len(self.drives):
            messagebox.showwarning("No Drive", "Please select a drive first.")
            return

        letter, label, _ = self.drives[idx]

        output_dir = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=get_exe_dir(),
        )
        if not output_dir:
            return

        filename = sanitize_filename(label) + ".iso"
        output_path = os.path.join(output_dir, filename)

        if os.path.exists(output_path):
            overwrite = messagebox.askyesno(
                "File Exists",
                f"{filename} already exists.\nOverwrite?",
            )
            if not overwrite:
                return

        self.make_btn.config(state=tk.DISABLED)
        self.refresh_btn.config(state=tk.DISABLED)
        self.status_var.set("Starting")

        t = threading.Thread(
            target=self._rip, args=(letter, output_path), daemon=True
        )
        t.start()

    def _set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def _finish(self, success, message, output_path):
        def done():
            self.make_btn.config(state=tk.NORMAL)
            self.refresh_btn.config(state=tk.NORMAL)
            self.status_var.set("Ready")
            if success:
                messagebox.showinfo("Done", f"ISO Created:\n{output_path}")
            else:
                messagebox.showerror("Error", message)
        self.root.after(0, done)

    def _rip(self, letter, output_path):
        raw_path = r"\\.\{}".format(letter)
        chunk = 2048 * 64
        written = 0
        try:
            with open(raw_path, "rb") as src, open(output_path, "wb") as dst:
                while True:
                    try:
                        data = src.read(chunk)
                    except OSError as e:
                        if written > 0:
                            break
                        raise
                    if not data:
                        break
                    dst.write(data)
                    written += len(data)
                    if written % (chunk * 8) == 0:
                        mb = written / (1024 * 1024)
                        self._set_status(f"{mb:,.1f} MB")
            self._finish(True, "", output_path)
        except PermissionError:
            try:
                if os.path.exists(output_path) and written == 0:
                    os.remove(output_path)
            except OSError:
                pass
            self._finish(
                False,
                "Permission denied. Raw drive access requires administrator "
                "privileges.\nRight-click the program and choose "
                "\"Run as administrator\".",
                output_path,
            )
        except FileNotFoundError:
            self._finish(
                False,
                f"Could not open {letter}. The drive may be empty or not ready.",
                output_path,
            )
        except Exception as e:
            self._finish(False, f"{type(e).__name__}: {e}", output_path)


def main():
    root = tk.Tk()
    ISOCreator(root)
    root.mainloop()


if __name__ == "__main__":
    main()