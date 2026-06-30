"""核心转换模块 — 将图片转换为拼豆图纸。"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from palette import BeadPalette


def load_image(filepath: str) -> Image.Image:
    """加载图片，统一转换为 RGB 模式。"""
    img = Image.open(filepath)
    if img.mode == "RGBA":
        # 透明背景转白色背景
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


def resize_image(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """缩放到精确的像素尺寸（每个像素对应一颗豆）。"""
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def quantize_image(image_array: np.ndarray, palette: BeadPalette) -> np.ndarray:
    """无抖动颜色量化：直接将每个像素匹配到最近的色板颜色。"""
    return palette.find_nearest_batch(image_array)


def apply_floyd_steinberg(image_array: np.ndarray, palette: BeadPalette) -> np.ndarray:
    """Floyd-Steinberg 误差扩散抖动。
    image_array: (H, W, 3) float64
    returns: (H, W) int32 色板索引
    """
    H, W, _ = image_array.shape
    img = image_array.copy().astype(np.float64)
    result = np.zeros((H, W), dtype=np.int32)

    for y in range(H):
        for x in range(W):
            old_pixel = img[y, x].copy()
            idx = palette.find_nearest(int(old_pixel[0]), int(old_pixel[1]), int(old_pixel[2]))
            result[y, x] = idx
            new_pixel = palette.rgb_array[idx].astype(np.float64)
            quant_error = old_pixel - new_pixel

            if x + 1 < W:
                img[y, x + 1] += quant_error * 7.0 / 16.0
            if x - 1 >= 0 and y + 1 < H:
                img[y + 1, x - 1] += quant_error * 3.0 / 16.0
            if y + 1 < H:
                img[y + 1, x] += quant_error * 5.0 / 16.0
            if x + 1 < W and y + 1 < H:
                img[y + 1, x + 1] += quant_error * 1.0 / 16.0

            # 钳制到 [0, 255]
            if x + 1 < W:
                img[y, x + 1] = np.clip(img[y, x + 1], 0, 255)
            if x - 1 >= 0 and y + 1 < H:
                img[y + 1, x - 1] = np.clip(img[y + 1, x - 1], 0, 255)
            if y + 1 < H:
                img[y + 1, x] = np.clip(img[y + 1, x], 0, 255)
            if x + 1 < W and y + 1 < H:
                img[y + 1, x + 1] = np.clip(img[y + 1, x + 1], 0, 255)

    return result


def render_pattern_image(
    indices: np.ndarray,
    palette: BeadPalette,
    bead_size: int = 16,
    show_numbers: bool = True,
) -> Image.Image:
    """渲染拼豆图纸为完整的 PIL 图片（含网格、编号、坐标、图例）。

    Args:
        indices: (H, W) 色板索引数组
        palette: 色板对象
        bead_size: 每个豆粒的像素大小
        show_numbers: 是否在格子上显示编号

    Returns:
        输出 PIL Image
    """
    H, W = indices.shape
    margin = 30  # 坐标标签边距
    grid_line_w = 1  # 网格线宽
    cell_step = bead_size + grid_line_w

    # 图例参数
    legend_width = 220
    legend_margin = 20
    legend_row_h = 26

    # 统计颜色用量
    color_counts = {}
    for idx in indices.flat:
        cid = palette.get_color_by_index(int(idx))["id"]
        color_counts[cid] = color_counts.get(cid, 0) + 1

    # 按 id 排序
    sorted_colors = sorted(color_counts.items(), key=lambda x: x[0])

    # 总图片尺寸
    grid_pixel_w = W * cell_step + 1
    grid_pixel_h = H * cell_step + 1
    total_w = margin + grid_pixel_w + legend_margin + legend_width
    total_h = margin + grid_pixel_h + legend_margin + 10

    img = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 尝试加载字体，失败则用默认字体
    font_small = None
    font_legend = None
    try:
        font_small = ImageFont.truetype("arial.ttf", size=max(8, bead_size // 2))
        font_legend = ImageFont.truetype("arial.ttf", size=12)
    except (IOError, OSError):
        pass

    # ── 绘制网格 ──
    colors_used = set()
    for y in range(H):
        for x in range(W):
            idx_val = int(indices[y, x])
            color_info = palette.get_color_by_index(idx_val)
            hex_color = color_info["hex"]
            rgb = tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
            colors_used.add(idx_val)

            px = margin + x * cell_step
            py = margin + y * cell_step
            draw.rectangle(
                [px, py, px + bead_size, py + bead_size],
                fill=rgb,
            )

            # 显示编号
            if show_numbers and bead_size >= 14:
                cid = color_info["id"]
                text = str(cid)
                text_color = _contrast_text_color(rgb)
                bbox = draw.textbbox((0, 0), text, font=font_small) if font_small else draw.textbbox((0, 0), text)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                tx = px + (bead_size - tw) / 2
                ty = py + (bead_size - th) / 2

                # 描边效果
                for ox, oy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    draw.text((tx + ox, ty + oy), text, fill=_opposite_color(text_color), font=font_small)
                draw.text((tx, ty), text, fill=text_color, font=font_small)

    # ── 网格线 ──
    grid_line_color = (180, 180, 180)
    for x in range(W + 1):
        lx = margin + x * cell_step
        draw.line([(lx, margin), (lx, margin + grid_pixel_h)], fill=grid_line_color, width=grid_line_w)
    for y in range(H + 1):
        ly = margin + y * cell_step
        draw.line([(margin, ly), (margin + grid_pixel_w, ly)], fill=grid_line_color, width=grid_line_w)

    # ── 坐标标签 ──
    coord_color = (50, 50, 50)
    # 列标签（顶部）
    for x in range(W):
        text = str(x + 1)
        bbox = draw.textbbox((0, 0), text, font=font_small) if font_small else draw.textbbox((0, 0), text)
        tw = bbox[2] - bbox[0]
        cx = margin + x * cell_step + bead_size / 2
        draw.text((cx - tw / 2, 2), text, fill=coord_color, font=font_small)
    # 行标签（左侧）
    for y in range(H):
        text = str(y + 1)
        bbox = draw.textbbox((0, 0), text, font=font_small) if font_small else draw.textbbox((0, 0), text)
        th = bbox[3] - bbox[1]
        cy = margin + y * cell_step + bead_size / 2
        draw.text((2, cy - th / 2), text, fill=coord_color, font=font_small)

    # ── 图例 ──
    legend_x = margin + grid_pixel_w + legend_margin
    legend_y_start = margin

    # 图例标题
    title = "颜色图例"
    if font_legend:
        draw.text((legend_x, legend_y_start - 18), title, fill=(0, 0, 0), font=font_legend)

    for i, (cid, count) in enumerate(sorted_colors):
        color_info = palette.get_color_by_id(cid)
        if color_info is None:
            continue
        hex_color = color_info["hex"]
        rgb = tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))

        ly = legend_y_start + i * legend_row_h
        # 色块
        draw.rectangle([legend_x, ly, legend_x + 18, ly + 18], fill=rgb, outline=(100, 100, 100))

        # 文字
        text = f"{cid} - {color_info['name']} ({count})"
        if font_legend:
            draw.text((legend_x + 24, ly - 1), text, fill=(0, 0, 0), font=font_legend)

    return img


def _contrast_text_color(bg_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """根据背景色返回适合对比的文字颜色（白/黑）。"""
    r, g, b = bg_rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def _opposite_color(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """返回相反色（用于描边）。"""
    return (255 - rgb[0], 255 - rgb[1], 255 - rgb[2])


def generate_pattern(
    image: Image.Image,
    palette: BeadPalette,
    width: int,
    height: int,
    dither: bool = True,
    bead_size: int = 16,
) -> tuple[Image.Image, dict[int, int]]:
    """完整流程：加载 → 缩放 → 量化 → 渲染。

    Returns:
        (输出 PIL 图片, {颜色ID: 用量, ...})
    """
    # 1. 缩放
    resized = resize_image(image, width, height)
    arr = np.array(resized, dtype=np.float64)

    # 2. 量化
    if dither:
        indices = apply_floyd_steinberg(arr, palette)
    else:
        indices = quantize_image(arr, palette)

    # 3. 统计用量
    color_counts = {}
    for idx in indices.flat:
        cid = palette.get_color_by_index(int(idx))["id"]
        color_counts[cid] = color_counts.get(cid, 0) + 1

    # 4. 渲染
    output_img = render_pattern_image(indices, palette, bead_size, show_numbers=True)

    return output_img, color_counts
