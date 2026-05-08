#!/bin/bash
# setup_linux.sh — Linux / WSL 环境自动配置脚本（conda 版）
# 用法: bash setup_linux.sh [conda_env_name]
# 默认使用名为 "python" 的 conda 环境

set -e

CONDA_ENV="${1:-python}"

echo "=== SpectraViewer Linux/WSL 环境配置 ==="

# 检测 WSL
IS_WSL=false
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
    echo "[检测] 运行在 WSL 环境中"
else
    echo "[检测] 运行在 Linux 环境中"
fi

# ---- 1. 系统依赖（跳过耗时的 apt update） ----
echo ""
echo "[步骤 1] 安装 Qt/XCB 系统依赖..."

sudo apt-get install -y \
    -o Acquire::ForceIPv4=true \
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
    libglib2.0-0 2>/dev/null && echo "[步骤 1] 完成" || echo "[步骤 1] 跳过（apt 安装失败，系统库可能已存在）"

# ---- 2. Python 依赖（conda） ----
echo ""
echo "[步骤 2] 在 conda 环境 '$CONDA_ENV' 中安装 Python 依赖..."

if command -v conda &>/dev/null; then
    conda run -n "$CONDA_ENV" pip install -r requirements.txt
    echo "[步骤 2] 完成"
elif command -v pip &>/dev/null; then
    pip install -r requirements.txt
    echo "[步骤 2] 完成"
else
    echo "[警告] 未找到 conda 或 pip，请手动安装: pip install -r requirements.txt"
fi

# ---- 3. 中文字体 (可选，WSL 下可直接共用 Windows 字体) ----
echo ""
echo "[步骤 3] 检查中文字体..."

if fc-list :lang=zh 2>/dev/null | grep -qi .; then
    echo "[步骤 3] 中文字体已安装"
else
    echo "[步骤 3] 未检测到中文字体，尝试安装..."
    sudo apt-get install -y -o Acquire::ForceIPv4=true fonts-noto-cjk 2>/dev/null && \
        fc-cache -fv 2>/dev/null && echo "[步骤 3] 完成" || \
        echo "[警告] 中文字体安装失败，图表中文可能显示为方框"
fi

# ---- 4. WSL 额外提示 ----
if [ "$IS_WSL" = true ]; then
    echo ""
    echo "[WSL 提示] WSLg 显示变量将由程序自动设置，无需手动配置 DISPLAY"
    echo "[WSL 提示] 如遇黑屏，请在 PowerShell 执行: wsl --shutdown 后重启 WSL"
fi

# ---- 5. 验证 ----
echo ""
echo "[验证] 检查 Python 环境 (conda env: $CONDA_ENV)..."

python_ok=true
for pkg in numpy scipy pandas matplotlib PyQt5; do
    if conda run -n "$CONDA_ENV" python -c "import $pkg" 2>/dev/null; then
        echo "  $pkg: OK"
    else
        echo "  $pkg: 缺失!"
        python_ok=false
    fi
done

echo ""
if [ "$python_ok" = true ]; then
    echo "=== 配置完成! 运行以下命令启动: ==="
    echo "  conda run -n $CONDA_ENV python main.py"
    echo "  或激活环境后: python main.py"
else
    echo "=== 部分依赖缺失，请检查上方输出 ==="
fi
