"""核心转换模块 — 将图片转换为拼豆图纸。"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from palette import BeadPalette


def load_image(filepath: str) -> Image.Image:
    """加载图片，统一转换为 RGB 模式。"""
    img = Image.open(filepath)
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


def resize_image(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """缩放到精确的像素尺寸（每个像素对应一颗豆）。"""
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def adjust_saturation(image: Image.Image, factor: float) -> Image.Image:
    """调整饱和度。1.0 = 原图，0.0 = 灰度，2.0 = 双倍饱和。"""
    enhancer = ImageEnhance.Color(image)
    return enhancer.enhance(factor)


def adjust_contrast(image: Image.Image, factor: float) -> Image.Image:
    """调整对比度。1.0 = 原图，0.0 = 全灰，2.0 = 高对比。"""
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)


def replace_background(image: Image.Image, bg_hex: str = "#FFFFFF") -> Image.Image:
    """将图片中接近边缘背景色的像素替换为目标色。
    bg_hex: 六位 hex 颜色，如 '#FFFFFF' '#000000' '#FF0000'
    """
    target_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (1, 3, 5))
    arr = np.array(image, dtype=np.float64)

    # 检测四角像素平均值作为背景参考色
    corners = [arr[0, 0], arr[0, -1], arr[-1, 0], arr[-1, -1]]
    bg = tuple(np.mean(corners, axis=0).astype(int))

    # 阈值判定背景像素
    threshold = 50
    mask = np.all(np.abs(arr - bg) < threshold, axis=2)

    for c in range(3):
        arr[:, :, c] = np.where(mask, target_rgb[c], arr[:, :, c])

    return Image.fromarray(arr.astype(np.uint8))


def quantize_image(image_array: np.ndarray, palette: BeadPalette) -> np.ndarray:
    """无抖动颜色量化。"""
    return palette.find_nearest_batch(image_array)


def quantize_image_with_limit(image_array: np.ndarray, palette: BeadPalette, max_colors: int) -> np.ndarray:
    """先降色再匹配色板 — 限制最终输出颜色种类。"""
    h, w = image_array.shape[:2]
    img_8bit = Image.fromarray(image_array.astype(np.uint8))
    quantized = img_8bit.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
    quantized_rgb = quantized.convert("RGB")
    reduced_arr = np.array(quantized_rgb, dtype=np.float64)
    return palette.find_nearest_batch(reduced_arr)


def apply_floyd_steinberg(image_array: np.ndarray, palette: BeadPalette) -> np.ndarray:
    """Floyd-Steinberg 误差扩散抖动。"""
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
    """渲染拼豆图纸为完整的 PIL 图片（含网格、编号、坐标、图例）。"""
    H, W = indices.shape
    margin = 20
    grid_line_w = 1
    cell_step = bead_size + grid_line_w

    legend_width = 220
    legend_margin = 16
    legend_row_h = 22

    # 统计颜色用量
    color_counts = {}
    for idx in indices.flat:
        cid = palette.get_color_by_index(int(idx))["id"]
        color_counts[cid] = color_counts.get(cid, 0) + 1
    sorted_colors = sorted(color_counts.items(), key=lambda x: x[0])

    # 总图片尺寸
    grid_pixel_w = W * cell_step + 1
    grid_pixel_h = H * cell_step + 1
    total_w = margin + grid_pixel_w + legend_margin + legend_width
    total_h = margin + grid_pixel_h + margin

    img = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 字体（不用 arial.ttf，用默认字体避免 exe 环境找不到）
    font_small = ImageFont.load_default()
    font_legend = ImageFont.load_default()

    # 字号放大（默认字体太小，改用 truetype 如果可用）
    try:
        font_small = ImageFont.truetype("arial.ttf", size=max(10, bead_size // 2))
        font_legend = ImageFont.truetype("arial.ttf", size=12)
    except Exception:
        try:
            font_small = ImageFont.truetype("DejaVuSans.ttf", size=max(10, bead_size // 2))
            font_legend = ImageFont.truetype("DejaVuSans.ttf", size=12)
        except Exception:
            pass

    # ── 绘制网格 ──
    for y in range(H):
        for x in range(W):
            idx_val = int(indices[y, x])
            color_info = palette.get_color_by_index(idx_val)
            hex_color = color_info["hex"]
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))

            px = margin + x * cell_step
            py = margin + y * cell_step
            draw.rectangle(
                [px, py, px + bead_size, py + bead_size],
                fill=rgb,
            )

            if show_numbers and bead_size >= 14:
                cid = color_info["id"]
                text = str(cid)
                text_color = _contrast_text_color(rgb)
                bbox = draw.textbbox((0, 0), text, font=font_small)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                tx = px + (bead_size - tw) / 2
                ty = py + (bead_size - th) / 2

                for ox, oy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    draw.text((tx + ox, ty + oy), text, fill=_opposite_color(text_color), font=font_small)
                draw.text((tx, ty), text, fill=text_color, font=font_small)

    # ── 网格线 ──
    grid_line_color = (200, 200, 200)
    for x in range(W + 1):
        lx = margin + x * cell_step
        draw.line([(lx, margin), (lx, margin + grid_pixel_h)], fill=grid_line_color, width=grid_line_w)
    for y in range(H + 1):
        ly = margin + y * cell_step
        draw.line([(margin, ly), (margin + grid_pixel_w, ly)], fill=grid_line_color, width=grid_line_w)

    # ── 坐标标签 ──
    coord_color = (80, 80, 80)
    for x in range(W):
        text = str(x + 1)
        bbox = draw.textbbox((0, 0), text, font=font_small)
        tw = bbox[2] - bbox[0]
        cx = margin + x * cell_step + bead_size / 2
        draw.text((cx - tw / 2, 2), text, fill=coord_color, font=font_small)
    for y in range(H):
        text = str(y + 1)
        bbox = draw.textbbox((0, 0), text, font=font_small)
        th = bbox[3] - bbox[1]
        cy = margin + y * cell_step + bead_size / 2
        draw.text((2, cy - th / 2), text, fill=coord_color, font=font_small)

    # ── 图例 ──
    legend_x = margin + grid_pixel_w + legend_margin
    legend_y = margin

    title = "颜色图例"
    draw.text((legend_x, legend_y - 14), title, fill=(0, 0, 0), font=font_legend)

    for i, (cid, count) in enumerate(sorted_colors):
        color_info = palette.get_color_by_id(cid)
        if color_info is None:
            continue
        hex_color = color_info["hex"]
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))

        ly = legend_y + i * legend_row_h
        draw.rectangle([legend_x, ly, legend_x + 16, ly + 16], fill=rgb, outline=(120, 120, 120))
        text = f"{cid} - {color_info['name']} ({count})"
        draw.text((legend_x + 22, ly - 1), text, fill=(0, 0, 0), font=font_legend)

    return img


def _contrast_text_color(bg_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = bg_rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def _opposite_color(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    return (255 - rgb[0], 255 - rgb[1], 255 - rgb[2])


def generate_pattern(
    image: Image.Image,
    palette: BeadPalette,
    width: int,
    height: int,
    dither: bool = True,
    bead_size: int = 16,
    saturation: float = 1.0,
    contrast: float = 1.0,
    max_colors: int = 0,
    bg_color: str = "",
) -> tuple[Image.Image, dict[int, int]]:
    """完整流程：加载 → 饱和度 → 对比度 → 背景色 → 缩放 → 量化 → 渲染。

    Returns:
        (输出 PIL 图片, {颜色ID: 用量, ...})
    """
    img = image.copy()

    # 1. 饱和度
    if saturation != 1.0:
        img = adjust_saturation(img, saturation)

    # 2. 对比度
    if contrast != 1.0:
        img = adjust_contrast(img, contrast)

    # 3. 背景色替换（仅在用户指定时）
    if bg_color and bg_color.strip():
        img = replace_background(img, bg_color.strip())

    # 4. 缩放
    resized = resize_image(img, width, height)
    arr = np.array(resized, dtype=np.float64)

    # 5. 量化
    if max_colors > 0 and max_colors < len(palette):
        indices = quantize_image_with_limit(arr, palette, max_colors)
    elif dither:
        indices = apply_floyd_steinberg(arr, palette)
    else:
        indices = quantize_image(arr, palette)

    # 6. 统计用量
    color_counts = {}
    for idx in indices.flat:
        cid = palette.get_color_by_index(int(idx))["id"]
        color_counts[cid] = color_counts.get(cid, 0) + 1

    # 7. 渲染
    output_img = render_pattern_image(indices, palette, bead_size, show_numbers=True)

    return output_img, color_counts
