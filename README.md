# SpectraViewer

SANTEC 光谱仪数据可视化与分析工具。

本项目提供两个版本：

| 版本 | 入口 | 适用场景 |
|------|------|---------|
| **桌面版**（main 分支） | `python main.py` | 本地直接运行，PyQt5 GUI |
| **Web 版**（web端 分支） | `python web_app.py` | SSH 远程、无需安装额外软件，浏览器访问 |

## 功能

- CSV 光谱数据加载与可视化
- 峰值/谷值检测与 3dB 带宽计算
- 微环谐振器 FSR / Q 因子分析
- 公式计算（多数据叠加运算）
- 出版质量图像导出

## 快速开始

### Web 版（推荐用于 SSH 远程）

```bash
pip install -r requirements.txt
python web_app.py
```

启动后在浏览器访问 `http://localhost:8050`。

**SSH 远程使用（VSCode / 任意终端）**：
1. 在服务器端启动：
   ```bash
   python web_app.py --host 0.0.0.0 --port 8050
   ```
2. VSCode 会自动弹出端口转发提示，点击"在浏览器中打开"即可。  
   或手动在本地浏览器访问 `http://localhost:8050`（VSCode 已转发）。
3. 也可用 SSH 隧道手动转发：
   ```bash
   ssh -L 8050:localhost:8050 user@服务器IP
   ```

**命令行参数**：
```bash
python web_app.py --host 127.0.0.1  # 仅本地访问（默认）
python web_app.py --host 0.0.0.0    # 允许局域网访问
python web_app.py --port 8888        # 自定义端口
python web_app.py --debug            # 开启调试模式（代码改动自动重载）
```

---

### 桌面版快速开始

### Windows（桌面版）

```bash
pip install -r requirements.txt
python main.py
```

### Linux / WSL（桌面版）

```bash
# 一键配置（安装 Qt 依赖 + Python 包 + 中文字体）
bash setup_linux.sh

# 启动
python main.py
```

WSL 环境下会自动使用 Windows 原生文件选择器，数据路径自动转换（如 `F:\data` → `/mnt/f/data`）。  
WSL 的 `DISPLAY` / `XDG_RUNTIME_DIR` 等显示变量由程序自动设置，无需手动配置。

### macOS（桌面版）

```bash
pip install -r requirements.txt
python main.py
```

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
