"""图形界面模块 — tkinter 实现的拼豆图纸生成器 GUI。"""

import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from palette import load_palette, list_available_palettes
from pattern_generator import generate_pattern, load_image


class BeadPatternApp:
    """拼豆图纸生成器主窗口。"""

    SUPPORTED_FORMATS = (
        ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tiff *.tif *.ico"),
        ("JPEG", "*.jpg *.jpeg"),
        ("PNG", "*.png"),
        ("BMP", "*.bmp"),
        ("GIF", "*.gif"),
        ("WEBP", "*.webp"),
        ("TIFF", "*.tiff *.tif"),
        ("所有文件", "*.*"),
    )

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("拼豆图纸生成器 — Perler Bead Pattern Generator")
        self.root.geometry("1300x900")
        self.root.minsize(1000, 700)

        # 状态变量
        self.original_image: Image.Image | None = None
        self.pattern_image: Image.Image | None = None
        self.current_palette = load_palette()
        self._processing = False

        # 设置样式
        self._setup_styles()
        # 构建界面
        self._create_widgets()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("vista" if "vista" in style.theme_names() else "clam")
        style.configure("TButton", padding=6)
        style.configure("Generate.TButton", font=("", 11, "bold"))

    def _create_widgets(self):
        # ── 顶部菜单栏 ──
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开图片", command=self.on_open_image, accelerator="Ctrl+O")
        file_menu.add_command(label="保存图纸", command=self.on_save, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        # 快捷键
        self.root.bind("<Control-o>", lambda e: self.on_open_image())
        self.root.bind("<Control-s>", lambda e: self.on_save())

        # ── 工具栏 ──
        toolbar = ttk.Frame(self.root, padding=(8, 4))
        toolbar.pack(fill=tk.X, side=tk.TOP)

        ttk.Button(toolbar, text="📂 打开图片", command=self.on_open_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🎨 生成图纸", style="Generate.TButton", command=self.on_generate).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 保存图纸", command=self.on_save).pack(side=tk.LEFT, padx=2)

        # ── 主内容区（左右分栏） ──
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))

        left_frame = ttk.LabelFrame(main_paned, text="原始图片", padding=(4, 4))
        right_frame = ttk.LabelFrame(main_paned, text="拼豆图纸", padding=(4, 4))

        main_paned.add(left_frame, weight=1)
        main_paned.add(right_frame, weight=1)

        # 左侧原始图 Canvas
        self.left_canvas = tk.Canvas(left_frame, bg="#F0F0F0", highlightthickness=0)
        self.left_canvas.pack(fill=tk.BOTH, expand=True)
        self.left_canvas.create_text(200, 200, text="点击「打开图片」选择图片", fill="#999999", font=("", 12), tags="placeholder")

        # 右侧图纸 Canvas + 滚动条
        right_inner = ttk.Frame(right_frame)
        right_inner.pack(fill=tk.BOTH, expand=True)

        self.h_scroll = ttk.Scrollbar(right_inner, orient=tk.HORIZONTAL)
        self.v_scroll = ttk.Scrollbar(right_inner, orient=tk.VERTICAL)
        self.right_canvas = tk.Canvas(
            right_inner, bg="#F0F0F0", highlightthickness=0,
            xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set,
        )
        self.h_scroll.config(command=self.right_canvas.xview)
        self.v_scroll.config(command=self.right_canvas.yview)

        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.right_canvas.create_text(250, 250, text="生成后图纸将显示在这里", fill="#999999", font=("", 12), tags="placeholder")

        # 滚动绑定
        self.right_canvas.bind("<Configure>", self._on_right_canvas_resize)

        # ── 底部控制面板 ──
        control_frame = ttk.LabelFrame(self.root, text="设置", padding=(8, 6))
        control_frame.pack(fill=tk.X, padx=8, pady=(4, 0))

        # 第一行
        row1 = ttk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="宽度:").pack(side=tk.LEFT)
        self.width_var = tk.IntVar(value=50)
        self.width_spin = ttk.Spinbox(row1, from_=5, to=200, textvariable=self.width_var, width=5)
        self.width_spin.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text="高度:", padx=(12, 0)).pack(side=tk.LEFT)
        self.height_var = tk.IntVar(value=50)
        self.height_spin = ttk.Spinbox(row1, from_=5, to=200, textvariable=self.height_var, width=5)
        self.height_spin.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text="色板:", padx=(12, 0)).pack(side=tk.LEFT)
        self.palette_var = tk.StringVar(value="perler")
        palette_names = list_available_palettes() or ["perler"]
        self.palette_combo = ttk.Combobox(row1, textvariable=self.palette_var, values=palette_names, width=12, state="readonly")
        self.palette_combo.pack(side=tk.LEFT, padx=2)
        self.palette_combo.bind("<<ComboboxSelected>>", self._on_palette_change)

        self.dither_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="启用抖动", variable=self.dither_var).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(row1, text="豆粒大小:", padx=(12, 0)).pack(side=tk.LEFT)
        self.bead_scale_var = tk.IntVar(value=16)
        self.bead_scale = ttk.Scale(row1, from_=8, to=32, variable=self.bead_scale_var, orient=tk.HORIZONTAL, length=100)
        self.bead_scale.pack(side=tk.LEFT, padx=2)
        self.bead_size_label = ttk.Label(row1, text="16px", width=6)
        self.bead_size_label.pack(side=tk.LEFT)
        self.bead_scale.config(command=lambda v: self.bead_size_label.config(text=f"{int(float(v))}px"))

        # ── 底部状态栏 ──
        status_frame = ttk.Frame(self.root, padding=(8, 4))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(status_frame, mode="indeterminate", length=120)
        self.progress_bar.pack(side=tk.RIGHT, padx=(8, 0))

    # ── 事件处理 ──

    def on_open_image(self):
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=self.SUPPORTED_FORMATS,
        )
        if not path:
            return

        try:
            self.original_image = load_image(path)
            self._display_original_preview()

            # 自动填充文件名
            base = os.path.splitext(os.path.basename(path))[0]
            self._suggested_name = base
            self.status_label.config(text=f"已加载: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开图片:\n{e}")
            self.original_image = None

    def on_generate(self):
        if self.original_image is None:
            messagebox.showwarning("提示", "请先打开一张图片！")
            return

        if self._processing:
            return

        w = self.width_var.get()
        h = self.height_var.get()

        # 超大尺寸警告
        if w * h > 40000:
            if not messagebox.askyesno("尺寸确认", f"图纸尺寸为 {w}×{h} = {w*h} 颗豆，\n处理可能需要较长时间。\n\n是否继续？"):
                return

        self._processing = True
        self.status_label.config(text="正在处理…")
        self.progress_bar.start(10)

        # 在后台线程中处理，避免 UI 卡顿
        def process():
            try:
                t0 = time.time()
                pattern, counts = generate_pattern(
                    self.original_image,
                    self.current_palette,
                    width=w,
                    height=h,
                    dither=self.dither_var.get(),
                    bead_size=self.bead_scale_var.get(),
                )
                elapsed = time.time() - t0
                self.root.after(0, self._on_generation_done, pattern, counts, elapsed)
            except Exception as e:
                self.root.after(0, self._on_generation_error, str(e))

        t = threading.Thread(target=process, daemon=True)
        t.start()

    def _on_generation_done(self, pattern: Image.Image, counts, elapsed: float):
        self.pattern_image = pattern
        self._display_pattern_preview()

        # 更新状态
        color_count = len(counts)
        self.status_label.config(
            text=f"完成! 耗时 {elapsed:.1f}s | {color_count} 种颜色 | 总豆数: {sum(counts.values())}"
        )
        self.progress_bar.stop()
        self._processing = False

    def _on_generation_error(self, error_msg: str):
        self.progress_bar.stop()
        self._processing = False
        self.status_label.config(text="处理失败")
        messagebox.showerror("生成失败", f"处理图片时出错:\n{error_msg}")

    def on_save(self):
        if self.pattern_image is None:
            messagebox.showwarning("提示", "还没有可保存的图纸，请先生成！")
            return

        suggested = getattr(self, "_suggested_name", "pattern")
        path = filedialog.asksaveasfilename(
            title="保存图纸",
            defaultextension=".png",
            initialfile=f"{suggested}_拼豆图纸",
            filetypes=[("PNG 图片", "*.png"), ("JPEG 图片", "*.jpg"), ("所有文件", "*.*")],
        )
        if not path:
            return

        try:
            self.pattern_image.save(path, "PNG")
            self.status_label.config(text=f"已保存: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("保存失败", f"无法保存图片:\n{e}")

    # ── 显示辅助 ──

    def _display_original_preview(self):
        if self.original_image is None:
            return
        max_w, max_h = 400, 400
        img = self.original_image.copy()
        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)

        self.left_canvas.delete("all")
        self.left_canvas.config(width=max_w, height=max_h)
        self.left_canvas.create_image(max_w // 2, max_h // 2, image=photo, anchor=tk.CENTER)
        # 保持引用防 GC
        self.left_canvas.image = photo

    def _display_pattern_preview(self):
        if self.pattern_image is None:
            return
        photo = ImageTk.PhotoImage(self.pattern_image)

        self.right_canvas.delete("all")
        self.right_canvas.config(scrollregion=(0, 0, self.pattern_image.width, self.pattern_image.height))
        self.right_canvas.create_image(0, 0, image=photo, anchor=tk.NW)
        self.right_canvas.image = photo

    def _on_right_canvas_resize(self, event):
        # 如果图纸小于画布，取消滚动条
        pass

    def _on_palette_change(self, event=None):
        name = self.palette_var.get()
        try:
            self.current_palette = load_palette(name)
            self.status_label.config(text=f"色板已切换: {name}")
        except Exception as e:
            messagebox.showerror("色板加载失败", f"{e}")

    def _show_about(self):
        messagebox.showinfo(
            "关于",
            "拼豆图纸生成器 v1.0\n\n"
            "将图片自动转换为拼豆图纸，\n"
            "支持 Perler 标准色板。\n\n"
            "基于 Python + Pillow + NumPy 构建。"
        )
