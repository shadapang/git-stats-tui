"""git-stats-tui GUI Launcher - tkinter folder picker + auto dependency install."""

import sys
import subprocess
from pathlib import Path


def _get_root():
    """Get or create the single Tk root window (singleton pattern)."""
    import tkinter as tk
    try:
        root = tk._default_root
        if root is not None:
            return root
    except AttributeError:
        pass
    return tk.Tk()


def check_and_install_deps():
    """Check if textual/rich are installed, offer to install if missing."""
    missing = []
    for pkg in ["textual", "rich"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return True

    # Try auto-install
    from tkinter import messagebox
    root = _get_root()
    root.withdraw()
    msg = f"Missing dependencies: {', '.join(missing)}\n\nInstall now?"
    if messagebox.askyesno("git-stats-tui", msg):
        root.destroy()
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + missing,
                timeout=120,
            )
            return True
        except Exception as e:
            # Print error to stderr instead of creating a second Tk() instance
            print(f"Install failed: {e}\nPlease run manually:\npip install {' '.join(missing)}", file=sys.stderr)
            return False
    else:
        root.destroy()
        return False


def launch_gui():
    """Show a tkinter GUI to pick a repo folder and launch git-stats-tui."""
    import tkinter as tk
    from tkinter import filedialog

    # Check deps first
    if not check_and_install_deps():
        sys.exit(1)

    root = tk.Tk()
    root.title("git-stats-tui \u542f\u52a8\u5668")
    root.geometry("520x260")
    root.resizable(False, False)

    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 520) // 2
    y = (root.winfo_screenheight() - 260) // 2
    root.geometry(f"520x260+{x}+{y}")

    # Title
    title_label = tk.Label(
        root,
        text="git-stats-tui\nGit \u7edf\u8ba1\u53ef\u89c6\u5316\u5de5\u5177",
        font=("", 16, "bold"),
        fg="#58a6ff",
    )
    title_label.pack(pady=(15, 5))

    # Path frame
    path_frame = tk.Frame(root)
    path_frame.pack(pady=10, padx=20, fill="x")

    tk.Label(path_frame, text="\u4ed3\u5e93\u8def\u5f84:", font=("", 11)).pack(side="left")

    path_var = tk.StringVar()
    path_entry = tk.Entry(path_frame, textvariable=path_var, font=("", 10), width=38)
    path_entry.pack(side="left", padx=(5, 5), fill="x", expand=True)

    def browse():
        folder = filedialog.askdirectory(title="\u9009\u62e9 Git \u4ed3\u5e93\u6587\u4ef6\u5939")
        if folder:
            path_var.set(folder)

    browse_btn = tk.Button(
        path_frame, text="\u6d4f\u89c8...", command=browse, font=("", 10), width=6
    )
    browse_btn.pack(side="left")

    # Hint
    hint_label = tk.Label(
        root,
        text="\u63d0\u793a: \u9009\u62e9\u5305\u542b .git \u6587\u4ef6\u5939\u7684\u76ee\u5f55\uff0c\u6216\u7559\u7a7a\u4f7f\u7528\u5f53\u524d\u76ee\u5f55",
        font=("", 9),
        fg="gray",
    )
    hint_label.pack(pady=(0, 5))

    # Status
    status_var = tk.StringVar(value="")
    status_label = tk.Label(root, textvariable=status_var, font=("", 9), fg="orange")
    status_label.pack()

    # Buttons frame
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)

    def start():
        repo_path = path_var.get().strip()
        if not repo_path:
            repo_path = "."

        # Validate it's a git repo
        resolved = Path(repo_path).resolve()
        if not resolved.exists():
            status_var.set(f"\u274c \u8def\u5f84\u4e0d\u5b58\u5728: {resolved}")
            return
        if not (resolved / ".git").exists():
            status_var.set(f"\u274c \u4e0d\u662f git \u4ed3\u5e93: {resolved}")
            return

        status_var.set("\u2705 \u6b63\u5728\u542f\u52a8...")
        root.update()

        # Launch the TUI app
        root.destroy()
        try:
            from src.app import GitStatsApp
            app = GitStatsApp(repo_path=resolved)
            app.run()
        except Exception as e:
            # Print error to stderr instead of creating a second Tk() instance
            print(f'启动失败: {e}\n请尝试命令行运行:\ngit-stats "{resolved}"', file=sys.stderr)
            sys.exit(1)

    start_btn = tk.Button(
        btn_frame,
        text="\u5f00\u59cb\u5206\u6790",
        command=start,
        font=("", 12, "bold"),
        bg="#238636",
        fg="white",
        width=12,
        height=1,
        relief="flat",
        cursor="hand2",
    )
    start_btn.pack(side="left", padx=10)

    def quit_app():
        root.destroy()
        sys.exit(0)

    quit_btn = tk.Button(
        btn_frame,
        text="\u9000\u51fa",
        command=quit_app,
        font=("", 12),
        width=8,
        height=1,
        relief="flat",
        cursor="hand2",
    )
    quit_btn.pack(side="left", padx=10)

    # Keyboard shortcuts
    root.bind("<Return>", lambda e: start())
    root.bind("<Escape>", lambda e: quit_app())

    root.mainloop()


def main_gui():
    """Entry point for the GUI launcher."""
    launch_gui()


if __name__ == "__main__":
    main_gui()
