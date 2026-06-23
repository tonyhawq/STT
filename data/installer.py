import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
import subprocess
import threading
import sys

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Installing Dependencies")
    root.geometry("450x150")
    root.resizable(True, True)
    status_label = tk.Label(root, text="Installing dependencies...\nThis may take several minutes.", justify="center", font=("Arial", 10))
    status_label.pack(pady=(20, 10))
    progress = ttk.Progressbar(root, mode="indeterminate", length=350)
    progress.pack(pady=10)
    progress.start(10)
    IS_DONE_INSTALLING = False
    PIP_PROCESS = None
    FINISH_RETURN_CODE = 0
    def window_close_hook():
        if IS_DONE_INSTALLING:
            root.destroy()
        else:
            if messagebox.askokcancel("Installation in progress", "The installation is still in progress! Are you sure you want to quit?", icon="warning"):
                root.destroy()
                if PIP_PROCESS is not None:
                    try:
                        PIP_PROCESS.terminate()
                    except Exception:
                        pass
    root.protocol("WM_DELETE_WINDOW", window_close_hook)
    def do_install():
        global IS_DONE_INSTALLING
        global PIP_PROCESS
        global FINISH_RETURN_CODE
        print("Installing dependencies...")
        PIP_PROCESS = subprocess.Popen("venv\\Scripts\\python.exe -m pip install -r requirements.txt --progress-bar=on")
        FINISH_RETURN_CODE = PIP_PROCESS.wait()
        if FINISH_RETURN_CODE != 0:
            messagebox.showerror("An error occurred", "An error occurred while downloading dependencies.")
        else:
            messagebox.showinfo("Installation complete", "The installation finished successfully! To use speech to text, just doubleclick run.bat!")
        IS_DONE_INSTALLING = True
        root.quit()
    threading.Thread(target = do_install, daemon=True).start()
    root.mainloop()
    if not IS_DONE_INSTALLING:
        sys.exit(1)
    if FINISH_RETURN_CODE != 0:
        sys.exit(FINISH_RETURN_CODE)
    sys.exit(0)