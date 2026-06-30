"""拼豆图纸生成器 — 启动入口"""

import sys
import tkinter as tk
from gui import BeadPatternApp


def main():
    # Windows DPI 感知（高分辨率显示器下界面更清晰）
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    root.title("拼豆图纸生成器")
    root.geometry("1300x900")
    root.minsize(1000, 700)

    app = BeadPatternApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
