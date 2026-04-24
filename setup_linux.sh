#!/bin/bash
# setup_linux.sh — Linux / WSL 环境自动配置脚本
# 用法: bash setup_linux.sh

set -e

echo "=== SpectraViewer Linux/WSL 环境配置 ==="

# 检测 WSL
IS_WSL=false
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
    echo "[检测] 运行在 WSL 环境中"
else
    echo "[检测] 运行在 Linux 环境中"
fi

# ---- 1. 系统依赖 ----
echo ""
echo "[步骤 1] 安装 Qt/XCB 系统依赖..."

sudo apt update

# Qt5 XCB 和图形库
sudo apt install -y \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libegl1 \
    libgl1 \
    libxrandr2 \
    libxss1 \
    libglib2.0-0

echo "[步骤 1] 完成"

# ---- 2. Python 依赖 ----
echo ""
echo "[步骤 2] 安装 Python 依赖..."

if command -v pip &>/dev/null; then
    pip install -r requirements.txt
elif command -v pip3 &>/dev/null; then
    pip3 install -r requirements.txt
else
    echo "[警告] 未找到 pip，请手动安装: pip install -r requirements.txt"
fi

echo "[步骤 2] 完成"

# ---- 3. 中文字体 (可选) ----
echo ""
echo "[步骤 3] 检查中文字体..."

if fc-list :lang=zh 2>/dev/null | grep -qi .; then
    echo "[步骤 3] 中文字体已安装"
else
    echo "[步骤 3] 未检测到中文字体，安装 Noto Sans CJK..."
    sudo apt install -y fonts-noto-cjk-extra 2>/dev/null || \
    sudo apt install -y fonts-noto-cjk 2>/dev/null || \
    echo "[警告] 中文字体安装失败，图表中文可能显示为方框。可手动安装: sudo apt install fonts-noto-cjk"
    # 刷新字体缓存
    fc-cache -fv 2>/dev/null
fi

# ---- 4. WSL 额外提示 ----
if [ "$IS_WSL" = true ]; then
    echo ""
    echo "[WSL 提示] 应用将使用 Windows 原生文件选择器"
    echo "[WSL 提示] 数据路径自动转换: F:\\path -> /mnt/f/path"
fi

# ---- 5. 验证 ----
echo ""
echo "[验证] 检查 Python 环境..."

python_ok=true
for pkg in numpy scipy pandas matplotlib PyQt5; do
    if python -c "import $pkg" 2>/dev/null || python3 -c "import $pkg" 2>/dev/null; then
        echo "  $pkg: OK"
    else
        echo "  $pkg: 缺失!"
        python_ok=false
    fi
done

echo ""
if [ "$python_ok" = true ]; then
    echo "=== 配置完成! 运行以下命令启动: ==="
    echo "  python main.py"
else
    echo "=== 部分依赖缺失，请检查上方输出 ==="
fi
