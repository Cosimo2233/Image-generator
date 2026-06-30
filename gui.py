"""图形界面模块 — tkinter 实现的拼豆图纸生成器 GUI。"""

import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageTk

from palette import load_palette, list_available_palettes
from pattern_generator import generate_pattern, load_image, rerender_with_removed_colors


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

    BG_COLOR_OPTIONS = [
        ("不替换", ""),
        ("白色 #FFFFFF", "#FFFFFF"),
        ("黑色 #000000", "#000000"),
        ("红色 #FF0000", "#FF0000"),
        ("蓝色 #0000FF", "#0000FF"),
        ("绿色 #00FF00", "#00FF00"),
        ("黄色 #FFFF00", "#FFFF00"),
    ]

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
        self._indices: np.ndarray | None = None  # 原始索引数组 (H,W)
        self._removed_color_ids: set[int] = set()  # 用户删除的颜色 ID

        self._setup_styles()
        self._create_widgets()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("vista" if "vista" in style.theme_names() else "clam")
        style.configure("TButton", padding=6)
        style.configure("Generate.TButton", font=("", 11, "bold"))

    def _create_widgets(self):
        # ── 菜单栏 ──
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
        right_frame = ttk.LabelFrame(main_paned, text="拼豆图纸（点击图例中的颜色可删除）", padding=(4, 4))

        main_paned.add(left_frame, weight=1)
        main_paned.add(right_frame, weight=1)

        # 左侧原始图 Canvas
        self.left_canvas = tk.Canvas(left_frame, bg="#F0F0F0", highlightthickness=0)
        self.left_canvas.pack(fill=tk.BOTH, expand=True)
        self.left_canvas.create_text(200, 176, text="点击「打开图片」选择图片", fill="#999999", font=("", 10), tags="placeholder")

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
        self.right_canvas.create_text(250, 205, text="生成后图纸将显示在这里\n点击图例中的颜色可以删除它", fill="#999999", font=("", 10), tags="placeholder")

        # ── 底部控制面板（两行） ──
        control_frame = ttk.LabelFrame(self.root, text="设置", padding=(8, 6))
        control_frame.pack(fill=tk.X, padx=8, pady=(4, 0))

        # 第一行：尺寸 + 色板 + 抖动 + 豆粒
        row1 = ttk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="宽度:").pack(side=tk.LEFT)
        self.width_var = tk.IntVar(value=50)
        ttk.Spinbox(row1, from_=5, to=200, textvariable=self.width_var, width=5).pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text="高度:").pack(side=tk.LEFT, padx=(8, 0))
        self.height_var = tk.IntVar(value=50)
        ttk.Spinbox(row1, from_=5, to=200, textvariable=self.height_var, width=5).pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text="色板:").pack(side=tk.LEFT, padx=(8, 0))
        self.palette_var = tk.StringVar(value="perler")
        palette_names = list_available_palettes() or ["perler"]
        self.palette_combo = ttk.Combobox(row1, textvariable=self.palette_var, values=palette_names, width=10, state="readonly")
        self.palette_combo.pack(side=tk.LEFT, padx=2)
        self.palette_combo.bind("<<ComboboxSelected>>", self._on_palette_change)

        self.dither_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="抖动", variable=self.dither_var).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(row1, text="豆粒:").pack(side=tk.LEFT, padx=(8, 0))
        self.bead_scale_var = tk.IntVar(value=16)
        self.bead_scale = ttk.Scale(row1, from_=8, to=32, variable=self.bead_scale_var, orient=tk.HORIZONTAL, length=80)
        self.bead_scale.pack(side=tk.LEFT, padx=2)
        self.bead_size_label = ttk.Label(row1, text="16px", width=5)
        self.bead_size_label.pack(side=tk.LEFT)
        self.bead_scale.config(command=lambda v: self.bead_size_label.config(text=f"{int(float(v))}px"))

        # 第二行：饱和度 + 对比度 + 最大颜色数 + 背景色
        row2 = ttk.Frame(control_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text="饱和度:").pack(side=tk.LEFT)
        self.saturation_var = tk.DoubleVar(value=1.0)
        ttk.Scale(row2, from_=0.0, to=2.0, variable=self.saturation_var, orient=tk.HORIZONTAL, length=100).pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="−", width=2, command=lambda: self._adj_saturation(-0.1)).pack(side=tk.LEFT)
        ttk.Button(row2, text="+", width=2, command=lambda: self._adj_saturation(0.1)).pack(side=tk.LEFT)
        self.saturation_label = ttk.Label(row2, text="1.0", width=4)
        self.saturation_label.pack(side=tk.LEFT)
        self.saturation_var.trace_add("write", lambda *a: self.saturation_label.config(text=f"{self.saturation_var.get():.1f}"))

        ttk.Label(row2, text="对比度:").pack(side=tk.LEFT, padx=(8, 0))
        self.contrast_var = tk.DoubleVar(value=1.0)
        ttk.Scale(row2, from_=0.0, to=2.0, variable=self.contrast_var, orient=tk.HORIZONTAL, length=100).pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="−", width=2, command=lambda: self._adj_contrast(-0.1)).pack(side=tk.LEFT)
        ttk.Button(row2, text="+", width=2, command=lambda: self._adj_contrast(0.1)).pack(side=tk.LEFT)
        self.contrast_label = ttk.Label(row2, text="1.0", width=4)
        self.contrast_label.pack(side=tk.LEFT)
        self.contrast_var.trace_add("write", lambda *a: self.contrast_label.config(text=f"{self.contrast_var.get():.1f}"))

        ttk.Label(row2, text="最大颜色:").pack(side=tk.LEFT, padx=(8, 0))
        self.max_colors_var = tk.IntVar(value=0)
        ttk.Spinbox(row2, from_=0, to=49, textvariable=self.max_colors_var, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(row2, text="(0=不限)").pack(side=tk.LEFT)

        ttk.Label(row2, text="背景色:").pack(side=tk.LEFT, padx=(8, 0))
        self.bg_color_var = tk.StringVar(value="")
        bg_labels = [opt[0] for opt in self.BG_COLOR_OPTIONS]
        ttk.Combobox(row2, textvariable=self.bg_color_var, values=bg_labels, width=16, state="readonly").pack(side=tk.LEFT, padx=2)
        self.bg_color_var.set("不替换")

        # ── 状态栏 ──
        status_frame = ttk.Frame(self.root, padding=(8, 4))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(status_frame, mode="indeterminate", length=120)
        self.progress_bar.pack(side=tk.RIGHT, padx=(8, 0))

    # ── 事件处理 ──

    def _adj_saturation(self, delta: float):
        v = self.saturation_var.get() + delta
        self.saturation_var.set(round(max(0.0, min(2.0, v)), 1))

    def _adj_contrast(self, delta: float):
        v = self.contrast_var.get() + delta
        self.contrast_var.set(round(max(0.0, min(2.0, v)), 1))

    def _get_bg_hex(self) -> str:
        selected = self.bg_color_var.get()
        for label, hex_val in self.BG_COLOR_OPTIONS:
            if label == selected:
                return hex_val
        return ""

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

        if w * h > 40000:
            if not messagebox.askyesno("尺寸确认", f"图纸尺寸为 {w}×{h} = {w*h} 颗豆，\n处理可能需要较长时间。\n\n是否继续？"):
                return

        self._processing = True
        self.status_label.config(text="正在处理…")
        self.progress_bar.start(10)

        # 重置删除状态
        self._removed_color_ids.clear()

        def process():
            try:
                t0 = time.time()
                pattern, counts, indices = generate_pattern(
                    self.original_image,
                    self.current_palette,
                    width=w,
                    height=h,
                    dither=self.dither_var.get(),
                    bead_size=self.bead_scale_var.get(),
                    saturation=self.saturation_var.get(),
                    contrast=self.contrast_var.get(),
                    max_colors=self.max_colors_var.get(),
                    bg_color=self._get_bg_hex(),
                )
                elapsed = time.time() - t0
                self.root.after(0, self._on_generation_done, pattern, counts, indices, elapsed)
            except Exception as e:
                self.root.after(0, self._on_generation_error, str(e))

        t = threading.Thread(target=process, daemon=True)
        t.start()

    def _on_generation_done(self, pattern: Image.Image, counts, indices: np.ndarray, elapsed: float):
        self.pattern_image = pattern
        self._indices = indices
        self._removed_color_ids.clear()
        self._display_pattern_preview()

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
        cw = self.left_canvas.winfo_width() or 400
        ch = self.left_canvas.winfo_height() or 380
        img = self.original_image.copy()
        img.thumbnail((cw - 10, ch - 10), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)

        self.left_canvas.delete("all")
        self.left_canvas.create_image(cw // 2, ch // 2, image=photo, anchor=tk.CENTER)
        self.left_canvas.image = photo

    def _display_pattern_preview(self):
        if self.pattern_image is None:
            return
        photo = ImageTk.PhotoImage(self.pattern_image)

        self.right_canvas.delete("all")
        self.right_canvas.config(scrollregion=(0, 0, self.pattern_image.width, self.pattern_image.height))
        self.right_canvas.create_image(0, 0, image=photo, anchor=tk.NW)
        self.right_canvas.image = photo

        # 绑定点击事件
        self.right_canvas.bind("<Button-1>", self._on_pattern_click)

    def _on_pattern_click(self, event):
        """点击图纸区域 — 检测是否点击到了图例中的颜色，如果是则删除该颜色。"""
        if self._indices is None or self._processing:
            return

        # 获取点击坐标（考虑滚动偏移）
        x = self.right_canvas.canvasx(event.x)
        y = self.right_canvas.canvasy(event.y)

        # 图例位于图片右侧区域
        # 图例起始 x = margin + grid_pixel_w + legend_margin
        # 需要从图片属性反算
        if self.pattern_image is None:
            return

        # 图例区域检测：右侧大约 220px 宽的区域是图例
        img_w = self.pattern_image.width
        legend_start_x = img_w - 220 - 16  # ~236px from right edge

        if x < legend_start_x:
            return  # 点击在网格区域，忽略

        # 图例行高 22px + 起始位置
        margin = 20
        legend_y_start = margin

        # 计算点击到了图例的第几行
        row = int((y - legend_y_start) // 22)
        if row < 0:
            return

        # 获取当前展示的所有颜色 ID（按 ID 排序）
        current_counts = {}
        for idx in self._indices.flat:
            cid = self.current_palette.get_color_by_index(int(idx))["id"]
            current_counts[cid] = current_counts.get(cid, 0) + 1
        sorted_colors = sorted(current_counts.items(), key=lambda x: x[0])

        if row >= len(sorted_colors):
            return

        cid_to_remove = sorted_colors[row][0]

        # 如果是最后一种颜色，不允许删除
        if len(sorted_colors) <= 1:
            messagebox.showwarning("提示", "至少保留一种颜色！")
            return

        # 如果已经删除了，忽略
        if cid_to_remove in self._removed_color_ids:
            return

        # 确认
        color_info = self.current_palette.get_color_by_id(cid_to_remove)
        name = color_info["name"] if color_info else str(cid_to_remove)

        if not messagebox.askyesno("删除颜色", f"确定要删除颜色「{name}」(编号 {cid_to_remove}) 吗？\n\n该颜色的所有豆子将替换为色板中最接近的其他颜色。"):
            return

        self._removed_color_ids.add(cid_to_remove)
        self.status_label.config(text=f"已删除颜色 {name}，正在重新渲染…")

        # 后台重新渲染
        def process():
            try:
                new_pattern, new_counts, new_indices = rerender_with_removed_colors(
                    self._indices, self.current_palette,
                    self._removed_color_ids, self.bead_scale_var.get(),
                )
                self.root.after(0, self._on_rerender_done, new_pattern, new_indices, new_counts)
            except Exception as e:
                self.root.after(0, self._on_generation_error, str(e))

        t = threading.Thread(target=process, daemon=True)
        t.start()

    def _on_rerender_done(self, new_pattern: Image.Image, new_indices: np.ndarray, new_counts):
        self.pattern_image = new_pattern
        self._indices = new_indices
        self._display_pattern_preview()
        self.status_label.config(
            text=f"已删除颜色 | 剩余 {len(new_counts)} 种颜色 | 总豆数: {sum(new_counts.values())}"
        )

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
            "拼豆图纸生成器 v1.2\n\n"
            "将图片自动转换为拼豆图纸\n"
            "支持 Perler 标准色板\n"
            "可调饱和度 / 对比度 / 颜色数量 / 背景色\n"
            "支持点击图纸图例删除不想要的颜色\n\n"
            "基于 Python + Pillow + NumPy 构建。"
        )
