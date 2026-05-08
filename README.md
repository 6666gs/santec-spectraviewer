# SpectraViewer

SANTEC 光谱仪数据可视化与分析工具。

本项目提供两个版本：

| 版本 | 分支 | 入口 | 适用场景 |
|------|------|------|---------|
| **桌面版** | `main` | `python main.py` | 本地直接运行，支持服务器文件夹路径，PyQt5 GUI |
| **Web 版** | `web端` | `python web_app.py` | SSH 远程访问，数据从**客户端浏览器上传**，无需安装额外软件 |

> **数据加载说明**：
> - 桌面版：直接填写服务器上的文件夹路径（如 `/data/sweep/`）
> - Web 版：通过浏览器上传客户端本地 CSV 文件（如 `E:\OneDrive\测试\...`），文件临时保存在服务器，关闭服务后自动删除

## 功能

- CSV 光谱数据加载与可视化
- 峰值/谷值检测与 3dB 带宽计算
- 微环谐振器 FSR / Q 因子分析
- 公式计算（多数据叠加运算）
- 出版质量图像导出

---

## Web 版快速开始（推荐用于 SSH 远程）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 本地启动

```bash
python web_app.py
# 浏览器访问 http://localhost:8050
```

### SSH 远程使用（VSCode / 任意终端）

1. 在服务器端启动：
   ```bash
   python web_app.py --host 0.0.0.0 --port 8050
   ```
2. **VSCode**：连接服务器后会自动弹出端口转发提示，点击"在浏览器中打开"即可
3. **其他终端**：本地执行 SSH 隧道后访问浏览器
   ```bash
   ssh -L 8050:localhost:8050 user@服务器IP
   # 然后访问 http://localhost:8050
   ```

### 使用流程

1. 点击顶栏 **"📂 上传 CSV 文件"**，选择本地数据文件夹中的所有 CSV（进入文件夹后 `Ctrl+A` 全选）
2. （可选）点击 **"📎 Reference"** 上传参考文件
3. 左侧表格出现数据列表，点击选中行即可绘图
4. 右侧面板进行峰值、FSR、Q 因子、公式等分析

### 命令行参数

```bash
python web_app.py --host 127.0.0.1  # 仅本地访问（默认）
python web_app.py --host 0.0.0.0    # 允许局域网/SSH 访问
python web_app.py --port 8888        # 自定义端口
python web_app.py --debug            # 调试模式（代码改动自动重载）
```

---

## 桌面版快速开始

### Windows

```bash
pip install -r requirements.txt
python main.py
```

### Linux / WSL

```bash
# 一键配置（安装 Qt 依赖 + Python 包 + 中文字体）
bash setup_linux.sh

# 启动
python main.py
```

WSL 的 `DISPLAY` / `XDG_RUNTIME_DIR` 等显示变量由程序自动设置，无需手动配置。

### macOS

```bash
pip install -r requirements.txt
python main.py
```

---

## 依赖

```
# 通用
numpy / scipy / pandas / matplotlib

# 桌面版
PyQt5

# Web 版
dash / dash-bootstrap-components / plotly
```

## 目录结构

```
SpectrumViewer/
├── main.py                 # 桌面版入口 (PyQt5)
├── web_app.py              # Web 版入口 (Dash)
├── setup_linux.sh          # Linux/WSL 环境配置脚本
├── requirements.txt
├── core/                   # 数据层
│   ├── io.py               # CSV 读取
│   ├── manager.py          # SpectraManager
│   ├── grid.py             # 网格/插值工具
│   └── utils.py
├── analysis/               # 分析层
│   ├── ring.py             # 微环谐振器分析
│   ├── peak.py             # 峰值/谷值检测
│   └── fitting.py          # 洛伦兹拟合
├── gui/                    # 桌面 GUI (PyQt5)
│   ├── main_window.py
│   ├── styles.py
│   └── widgets.py
├── web/                    # Web GUI (Dash)
│   ├── app.py
│   ├── layout.py
│   └── callbacks.py
└── visualization/
    └── plotter.py
```
