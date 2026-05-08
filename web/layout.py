"""Dash 应用布局定义。"""

from dash import dcc, html
import dash_bootstrap_components as dbc

# ── 顶部工具栏 ──────────────────────────────────────────────────────────────
toolbar = dbc.Navbar(
    dbc.Container([
        dbc.Row([
            dbc.Col(html.Span("SpectraViewer", className="navbar-brand mb-0 h5 fw-bold"), width="auto"),
            dbc.Col([
                dbc.InputGroup([
                    dbc.InputGroupText("文件夹路径"),
                    dbc.Input(id="input-folder", placeholder="/path/to/data", debounce=True, style={"minWidth": "320px"}),
                    dbc.Button("加载", id="btn-load", color="primary", n_clicks=0),
                ], size="sm"),
            ], width="auto"),
            dbc.Col([
                dbc.InputGroup([
                    dbc.InputGroupText("数据类型"),
                    dbc.Select(
                        id="select-datatype",
                        options=[
                            {"label": "auto", "value": "auto"},
                            {"label": "loss", "value": "loss"},
                            {"label": "raw",  "value": "raw"},
                        ],
                        value="auto",
                    ),
                ], size="sm"),
            ], width="auto"),
            dbc.Col([
                dbc.InputGroup([
                    dbc.InputGroupText("Reference"),
                    dbc.Input(id="input-reference", placeholder="（可选）Reference CSV 路径", debounce=True, style={"minWidth": "260px"}),
                ], size="sm"),
            ], width="auto"),
        ], align="center", className="g-2 flex-wrap"),
    ], fluid=True),
    color="dark", dark=True, className="py-2 mb-0",
)

# ── 左侧：数据列表 ──────────────────────────────────────────────────────────
left_panel = dbc.Card([
    dbc.CardHeader(html.Span("数据列表", className="fw-semibold")),
    dbc.CardBody([
        dbc.Alert('请先输入文件夹路径并点击"加载"', id="alert-no-data", color="secondary",
                  className="py-2 small", dismissable=False),
        html.Div(id="div-table"),
    ], className="p-2 overflow-auto", style={"height": "calc(100vh - 160px)"}),
], className="h-100 rounded-0 border-end border-0"),

# ── 右侧分析面板 ─────────────────────────────────────────────────────────────
def _section(title, color, children, id_collapse):
    return dbc.Card([
        dbc.CardHeader(
            dbc.Button(title, id=f"btn-collapse-{id_collapse}", color="link",
                       className="fw-semibold text-decoration-none p-0",
                       style={"color": color}),
            className="py-2 px-3",
        ),
        dbc.Collapse(dbc.CardBody(children, className="pt-2 pb-3 px-3"), id=f"collapse-{id_collapse}", is_open=True),
    ], className="mb-2 border shadow-sm")


formula_section = _section("∑ 公式计算", "#7c3aed", [
    dbc.Label("公式（A0, A1, ... 代表选中行）", className="small text-muted mb-1"),
    dbc.Input(id="input-formula", placeholder="例：A0 - A1", debounce=True, size="sm"),
    dbc.Button("计算", id="btn-formula", color="secondary", size="sm", className="mt-2", n_clicks=0),
], "formula")

plot_section = _section("📈 绘图选项", "#0ea5e9", [
    dbc.Row([
        dbc.Col([dbc.Label("标题", className="small text-muted mb-1"),
                 dbc.Input(id="input-title", placeholder="图表标题", size="sm", debounce=True)], width=12),
        dbc.Col([dbc.Label("X 轴", className="small text-muted mb-1"),
                 dbc.Input(id="input-xlabel", placeholder="Wavelength (nm)", size="sm", debounce=True)], width=6),
        dbc.Col([dbc.Label("Y 轴", className="small text-muted mb-1"),
                 dbc.Input(id="input-ylabel", placeholder="Insertion Loss (dB)", size="sm", debounce=True)], width=6),
    ], className="g-2 mb-2"),
    dbc.Row([
        dbc.Col([dbc.Label("X min", className="small text-muted mb-1"),
                 dbc.Input(id="input-xmin", placeholder="自动", type="number", size="sm", debounce=True)], width=3),
        dbc.Col([dbc.Label("X max", className="small text-muted mb-1"),
                 dbc.Input(id="input-xmax", placeholder="自动", type="number", size="sm", debounce=True)], width=3),
        dbc.Col([dbc.Label("Y min", className="small text-muted mb-1"),
                 dbc.Input(id="input-ymin", placeholder="自动", type="number", size="sm", debounce=True)], width=3),
        dbc.Col([dbc.Label("Y max", className="small text-muted mb-1"),
                 dbc.Input(id="input-ymax", placeholder="自动", type="number", size="sm", debounce=True)], width=3),
    ], className="g-2"),
], "plot")

peak_section = _section("🔍 峰值/谷值分析", "#d97706", [
    dbc.Row([
        dbc.Col([
            dbc.RadioItems(
                id="radio-peak-type",
                options=[{"label": "峰值", "value": "peak"}, {"label": "谷值", "value": "valley"}],
                value="valley", inline=True, className="small",
            ),
        ], width=12),
    ], className="mb-2"),
    dbc.Row([
        dbc.Col([dbc.Label("X min", className="small text-muted mb-1"),
                 dbc.Input(id="input-peak-xmin", placeholder="自动", type="number", size="sm", debounce=True)], width=3),
        dbc.Col([dbc.Label("X max", className="small text-muted mb-1"),
                 dbc.Input(id="input-peak-xmax", placeholder="自动", type="number", size="sm", debounce=True)], width=3),
        dbc.Col([dbc.Label("阈值 (dB)", className="small text-muted mb-1"),
                 dbc.Input(id="input-peak-threshold", placeholder="无", type="number", size="sm", debounce=True)], width=3),
        dbc.Col([dbc.Label("最小间距", className="small text-muted mb-1"),
                 dbc.Input(id="input-peak-distance", placeholder="50", type="number", value=50, size="sm", debounce=True)], width=3),
    ], className="g-2 mb-2"),
    dbc.Button("分析", id="btn-peak", color="warning", size="sm", n_clicks=0),
], "peak")

ring_section = _section("⭕ 微环谐振器分析", "#16a34a", [
    dbc.Row([
        dbc.Col([dbc.Label("FSR 高度阈值", className="small text-muted mb-1"),
                 dbc.Input(id="input-ring-height", placeholder="自动", type="number", size="sm", debounce=True)], width=6),
        dbc.Col([dbc.Label("FSR 最小间距", className="small text-muted mb-1"),
                 dbc.Input(id="input-ring-distance", placeholder="自动", type="number", size="sm", debounce=True)], width=6),
    ], className="g-2 mb-2"),
    dbc.Row([
        dbc.Col(dbc.Button("计算 FSR", id="btn-fsr", color="success", size="sm", n_clicks=0), width="auto"),
        dbc.Col(dbc.Button("计算 Q", id="btn-q", color="success", size="sm", n_clicks=0), width="auto"),
    ], className="g-2"),
], "ring")

right_panel = html.Div([
    plot_section,
    formula_section,
    peak_section,
    ring_section,
], className="overflow-auto px-2 py-2", style={"height": "calc(100vh - 160px)"})

# ── 主图表区 ─────────────────────────────────────────────────────────────────
chart_area = dbc.Card([
    dbc.CardBody([
        dcc.Graph(
            id="graph-main",
            style={"height": "calc(100vh - 320px)"},
            config={"displayModeBar": True, "scrollZoom": True},
        ),
        html.Hr(className="my-1"),
        html.Div(
            id="div-analysis-result",
            className="small font-monospace text-muted px-1",
            style={"maxHeight": "120px", "overflowY": "auto", "whiteSpace": "pre-wrap"},
        ),
    ], className="p-2"),
], className="mb-0 border-0 rounded-0")

# ── 底部日志 ─────────────────────────────────────────────────────────────────
log_bar = dbc.Card(
    dbc.CardBody(
        html.Pre(id="pre-log", className="mb-0 small text-success",
                 style={"maxHeight": "80px", "overflowY": "auto"}),
        className="py-1 px-3",
    ),
    color="dark", className="rounded-0 border-top border-secondary",
)

# ── 隐藏状态存储 ──────────────────────────────────────────────────────────────
stores = html.Div([
    dcc.Store(id="store-manager"),       # 序列化的表格数据（无法存 Python 对象，用 JSON 表）
    dcc.Store(id="store-folder"),        # 当前文件夹路径
    dcc.Store(id="store-reference"),     # reference 路径
    dcc.Store(id="store-selected-keys"), # 当前选中的 key 列表
])

# ── 总布局 ───────────────────────────────────────────────────────────────────
layout = html.Div([
    stores,
    toolbar,
    dbc.Container([
        dbc.Row([
            # 左：数据列表 (3列)
            dbc.Col(left_panel, width=3, className="px-0"),
            # 中：图表 (6列)
            dbc.Col([chart_area], width=6, className="px-0"),
            # 右：分析面板 (3列)
            dbc.Col(right_panel, width=3, className="px-0"),
        ], className="g-0"),
        dbc.Row([
            dbc.Col(log_bar, width=12, className="px-0"),
        ]),
    ], fluid=True, className="px-0"),
], style={"fontFamily": "system-ui, -apple-system, sans-serif"})
