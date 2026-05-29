# visualization/plotter.py — 出版质量绑图
"""出版质量光谱绑图函数。"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


# Nature 风格无衬线字体栈
# 不含 Helvetica：Windows 无此字体会触发大量 findfont 警告；Arial 优先，DejaVu 兜底
_SANS = ['Arial', 'DejaVu Sans', 'sans-serif']

# Nature 风格默认配色（蓝/红/绿/青/紫… 低饱和、彼此区分度高）
_NATURE_COLORS = [
    '#0F4D92',   # blue_main
    '#B64342',   # red_strong
    '#2E9E44',   # green
    '#42949E',   # teal
    '#9A4D8E',   # violet
    '#E28E2C',   # orange
    '#767676',   # neutral_mid
    '#3775BA',   # blue_secondary
]


def plot_publication(
    data_list,
    xlabel='X',
    ylabel='Y',
    x_major=None,
    y_major=None,
    xlim=None,
    ylim=None,
    figsize=(8, 6),
    save_path=None,
    dpi=300,
    title=None,
    fontsize=16,
):
    """生成出版质量的图像。

    Args:
        data_list: 数据列表，每个元素为 {'x': array, 'y': array, 'label': str, ...}
        xlabel: X 轴标签
        ylabel: Y 轴标签
        x_major: X 轴主刻度间隔
        y_major: Y 轴主刻度间隔
        xlim: X 轴范围 (min, max)
        ylim: Y 轴范围 (min, max)
        figsize: 图像大小
        save_path: 保存路径，None 则不保存
        dpi: 保存分辨率
        title: 图像标题

    Returns:
        (fig, ax) matplotlib 对象
    """
    fig, ax = plt.subplots(figsize=figsize)
    has_label = False
    for i, data in enumerate(data_list):
        x = data['x']
        y = data['y']
        label = data.get('label', None)
        color = data.get('color', _NATURE_COLORS[i % len(_NATURE_COLORS)])
        marker = data.get('marker', False)
        marker_size = data.get('marker_size', 36)
        linewidth = data.get('linewidth', 1.8)
        linestyle = data.get('linestyle', '-')
        if label:
            has_label = True
        ax.plot(x, y, linestyle, color=color, linewidth=linewidth, label=label, zorder=2)
        if marker:
            ax.scatter(x, y, s=marker_size, color=color, edgecolors='white',
                       linewidth=0.5, zorder=3)
    ax.set_xlabel(xlabel, fontsize=fontsize, family=_SANS)
    ax.set_ylabel(ylabel, fontsize=fontsize, family=_SANS)
    if title:
        ax.set_title(title, fontsize=fontsize + 2, fontweight='bold', family=_SANS, pad=10)
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)
    ax.grid(False)
    if x_major:
        ax.xaxis.set_major_locator(MultipleLocator(x_major))
    if y_major:
        ax.yaxis.set_major_locator(MultipleLocator(y_major))
    # Nature 标志性的开放坐标轴：移除上/右边框
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='both', which='major', labelsize=max(8, fontsize - 4),
                   width=1.0, length=4, direction='out', top=False, right=False)
    ax.minorticks_off()
    for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
        tick_label.set_fontname(_SANS[0])
    for spine in ax.spines.values():
        spine.set_linewidth(1.2)
    if has_label:
        ax.legend(fontsize=max(8, fontsize - 4), frameon=False,
                  prop={'family': _SANS, 'size': max(8, fontsize - 4)})
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')
        print(f"图像已保存到: {save_path}")
    return fig, ax
