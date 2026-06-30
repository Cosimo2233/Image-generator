# 拼豆图纸生成器 (Perler Bead Pattern Generator)

一个简单易用的 Python 桌面应用，将任意图片转换为**带有颜色编号的拼豆图纸**。

## 功能特点

- 🖼️ **支持多种图片格式** — JPG, PNG, BMP, GIF, WEBP, TIFF 等常见格式
- 🎨 **颜色自动匹配** — 将图片像素自动匹配到最接近的拼豆颜色
- 🔢 **彩色图纸输出** — 每个格子标注颜色编号，行/列坐标清晰可见
- 📋 **颜色图例** — 自动生成颜色列表（编号 + 颜色名 + 所需数量）
- 🌀 **可选抖动算法** — Floyd-Steinberg 抖动使渐变色过渡更自然
- 📐 **灵活尺寸设置** — 自定义图纸的宽高（豆粒数量）
- 💾 **保存为 PNG** — 一键导出高分辨率图纸

## 快速开始

### 前置要求

- Python 3.9 或更高版本
- pip（Python 包管理器）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/perler-bead-pattern-generator.git
cd perler-bead-pattern-generator

# 2. 创建虚拟环境（推荐）
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行程序
python main.py
```

## 使用指南

1. **打开图片** — 点击「打开图片」按钮或菜单 `文件 → 打开图片`
2. **调整设置** — 设置图纸尺寸（宽 × 高，单位：豆粒数量）
3. **选择色板** — 默认使用 Perler 品牌色板
4. **启用抖动**（可选）— 勾选后渐变色更平滑
5. **生成图纸** — 点击「生成图纸」，等待处理完成
6. **保存导出** — 点击「保存图纸」导出为 PNG 图片

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 宽度 | 图纸的豆粒列数 | 50 |
| 高度 | 图纸的豆粒行数 | 50 |
| 豆粒大小 | 预览中每个豆粒的像素大小 | 16px |
| 启用抖动 | 使用 Floyd-Steinberg 抖动算法 | 开启 |

## 项目结构

```
perler-bead-pattern-generator/
├── main.py                 # 程序入口
├── gui.py                  # 图形界面
├── pattern_generator.py    # 图片转图纸核心算法
├── palette.py              # 色板加载与颜色匹配
├── palettes/
│   └── perler.json         # Perler 品牌色板数据
├── requirements.txt        # Python 依赖
├── .gitignore
└── README.md
```

## 依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| [Pillow](https://python-pillow.org/) | >= 10.0.0 | 图片加载、缩放、绘制 |
| [NumPy](https://numpy.org/) | >= 1.24.0 | 数组运算、颜色距离计算 |

## 算法说明

### 颜色匹配
使用欧几里得距离在 RGB 空间中计算每个像素与色板中所有颜色的距离，选择最接近的颜色作为匹配结果。通过 NumPy 广播实现向量化计算，性能高效。

### Floyd-Steinberg 抖动
将颜色量化的误差按比例（7/16, 3/16, 5/16, 1/16）扩散到相邻未处理像素，在有限颜色数下模拟出更丰富的色彩过渡效果。

## 自定义色板

在 `palettes/` 目录中添加 JSON 文件即可添加自定义色板。格式如下：

```json
[
  {"id": 1, "name": "White", "hex": "#FFFFFF"},
  {"id": 2, "name": "Black", "hex": "#1A1A1A"}
]
```

## 许可证

本项目采用 MIT 许可证。
