"""色板模块 — 加载拼豆颜色数据，提供最近色查找功能。"""

import json
import os
import numpy as np


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """将 '#FF8833' 转换为 (255, 136, 51)"""
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i : i + 2], 16) for i in (0, 2, 4))


class BeadPalette:
    """拼豆色板，加载 JSON 格式的颜色数据，支持最近色查找。"""

    def __init__(self, palette_path: str):
        with open(palette_path, "r", encoding="utf-8") as f:
            self.colors = json.load(f)

        # 构建 RGB 数组 (N, 3) uint8
        self.rgb_array = np.array(
            [hex_to_rgb(c["hex"]) for c in self.colors], dtype=np.uint8
        )

        # 构建 str -> int 的反向索引（用于图例去重）
        self._name_to_id = {c["name"]: c["id"] for c in self.colors}

    def find_nearest(self, r: int, g: int, b: int) -> int:
        """返回色板中与 (r,g,b) 最接近颜色的索引（0-based）。"""
        pixel = np.array([r, g, b], dtype=np.float64)
        distances = np.sqrt(np.sum((self.rgb_array.astype(np.float64) - pixel) ** 2, axis=1))
        return int(np.argmin(distances))

    def find_nearest_batch(self, pixels: np.ndarray) -> np.ndarray:
        """向量化批量查找。
        pixels: (H, W, 3) float64 或 uint8
        returns: (H, W) int32 色板索引数组
        """
        orig_shape = pixels.shape[:2]
        flat = pixels.reshape(-1, 3).astype(np.float64)
        palette_float = self.rgb_array.astype(np.float64)  # (M, 3)

        # 广播计算: (N,1,3) - (1,M,3) → (N,M,3)
        diff = flat[:, np.newaxis, :] - palette_float[np.newaxis, :, :]
        dist = np.sqrt(np.sum(diff ** 2, axis=2))  # (N, M)
        indices = np.argmin(dist, axis=1).astype(np.int32)  # (N,)
        return indices.reshape(orig_shape)

    def get_color_by_index(self, index: int) -> dict:
        """返回 {id, name, hex} 字典。"""
        return self.colors[index]

    def get_color_by_id(self, color_id: int) -> dict | None:
        """通过 id 查找颜色，未找到返回 None。"""
        for c in self.colors:
            if c["id"] == color_id:
                return c
        return None

    def __len__(self) -> int:
        return len(self.colors)


def load_palette(palette_name: str = "perler") -> BeadPalette:
    """按名称加载色板文件（默认加载 perler.json）。"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "palettes", f"{palette_name}.json")
    return BeadPalette(path)


def list_available_palettes() -> list[str]:
    """扫描 palettes/ 目录，返回所有 JSON 色板名称（不含扩展名）。"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    palettes_dir = os.path.join(base_dir, "palettes")
    if not os.path.isdir(palettes_dir):
        return []
    files = os.listdir(palettes_dir)
    return sorted(
        f[:-5] for f in files if f.endswith(".json") and os.path.isfile(os.path.join(palettes_dir, f))
    )
