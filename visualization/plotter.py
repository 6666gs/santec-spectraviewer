# visualization/plotter.py — 出版质量绑图
"""出版质量光谱绑图函数。"""

import platform
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


def _get_serif_font():
    """根据平台返回衬线字体名称。"""
    system = platform.system()
    if system == 'Darwin':
        return 'Times New Roman'
    elif system == 'Windows':
        return 'Times New Roman'
    else:
        return 'serif'


_SERIF = _get_serif_font()


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
    default_colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    ]
    fig, ax = plt.subplots(figsize=figsize)
    has_label = False
    for i, data in enumerate(data_list):
        x = data['x']
        y = data['y']
        label = data.get('label', None)
        color = data.get('color', default_colors[i % len(default_colors)])
        marker = data.get('marker', False)
        marker_size = data.get('marker_size', 50)
        linewidth = data.get('linewidth', 2)
        linestyle = data.get('linestyle', '-')
        if label:
            has_label = True
        ax.plot(x, y, linestyle, color=color, linewidth=linewidth, label=label, zorder=1)
        if marker:
            ax.scatter(x, y, s=marker_size, color=color, zorder=2)
    ax.set_xlabel(xlabel, fontsize=16, fontweight='bold', family=_SERIF)
    ax.set_ylabel(ylabel, fontsize=16, fontweight='bold', family=_SERIF)
    if title:
        ax.set_title(title, fontsize=18, fontweight='bold', family=_SERIF)
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)
    ax.grid(False)
    if x_major:
        ax.xaxis.set_major_locator(MultipleLocator(x_major))
    if y_major:
        ax.yaxis.set_major_locator(MultipleLocator(y_major))
    ax.tick_params(axis='both', which='major', labelsize=12, width=2, length=6,
                   direction='in', top=True, right=True, bottom=True, left=True, zorder=10)
    ax.minorticks_off()
    for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
        tick_label.set_fontweight('bold')
        tick_label.set_fontname(_SERIF)
    for spine in ax.spines.values():
        spine.set_linewidth(2)
        spine.set_zorder(10)
    if has_label:
        ax.legend(fontsize=12, frameon=False,
                  prop={'family': _SERIF, 'weight': 'bold'})
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')
        print(f"图像已保存到: {save_path}")
    return fig, ax
