"""Dash 回调函数。"""

import io
import sys
import json
import traceback

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, html, no_update
from dash.exceptions import PreventUpdate

from core.manager import SpectraManager
from analysis.peak import analyze_peaks, format_peak_results
from analysis.ring import Ring


# ── 工具函数 ─────────────────────────────────────────────────────────────────

def _load_manager(folder, data_type, reference):
    return SpectraManager.from_folder(
        folder,
        data_type=data_type or 'auto',
        reference_path=reference or None,
    )


def _capture_stdout(fn, *args, **kwargs):
    """执行 fn，返回 (result, stdout_text)。"""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        result = fn(*args, **kwargs)
    finally:
        sys.stdout = old
    return result, buf.getvalue()


def _make_table(df: pd.DataFrame):
    display_cols = ['index', 'device', 'device_no', 'port', 'channel',
                    'start_nm', 'end_nm', 'step', 'data_type']
    cols = [c for c in display_cols if c in df.columns]
    return dash_table.DataTable(
        id='datatable-spectra',
        columns=[{"name": c, "id": c} for c in cols],
        data=df[cols].to_dict('records'),
        row_selectable='multi',
        selected_rows=[],
        style_table={'overflowX': 'auto', 'fontSize': '12px'},
        style_cell={'padding': '4px 8px', 'textAlign': 'left', 'whiteSpace': 'normal'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f1f5f9'},
        style_data_conditional=[
            {'if': {'state': 'selected'}, 'backgroundColor': '#dbeafe', 'border': '1px solid #3b82f6'},
        ],
        page_size=200,
        sort_action='native',
        filter_action='native',
    )


def _empty_fig(msg="请先选择数据行"):
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=14, color="#94a3b8"))
    fig.update_layout(paper_bgcolor="#f8fafc", plot_bgcolor="#f8fafc",
                      xaxis=dict(visible=False), yaxis=dict(visible=False), margin=dict(t=20, b=20))
    return fig


def _spectrum_fig(traces, title="", xlabel="Wavelength (nm)", ylabel="Insertion Loss (dB)",
                  xrange=None, yrange=None):
    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)) if title else None,
        xaxis=dict(title=xlabel, range=xrange, showgrid=True, gridcolor="#e2e8f0"),
        yaxis=dict(title=ylabel, range=yrange, showgrid=True, gridcolor="#e2e8f0"),
        legend=dict(orientation="h", y=-0.15, font=dict(size=11)),
        paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(t=40 if title else 20, b=20, l=60, r=20),
        hovermode="x unified",
    )
    return fig


# ── 回调注册函数（在 app 创建后调用） ────────────────────────────────────────

def register(app):

    # 1. 加载文件夹 → 填充表格
    @app.callback(
        Output("store-manager", "data"),
        Output("store-folder", "data"),
        Output("store-reference", "data"),
        Output("div-table", "children"),
        Output("alert-no-data", "style"),
        Output("pre-log", "children"),
        Input("btn-load", "n_clicks"),
        State("input-folder", "value"),
        State("select-datatype", "value"),
        State("input-reference", "value"),
        prevent_initial_call=True,
    )
    def load_folder(n, folder, data_type, reference):
        if not folder:
            return no_update, no_update, no_update, no_update, {}, "请输入文件夹路径"
        try:
            mgr, log = _capture_stdout(_load_manager, folder, data_type, reference)
            table_json = mgr.table.to_json(orient='split')
            return (
                table_json,
                folder,
                reference or '',
                _make_table(mgr.table),
                {"display": "none"},
                log,
            )
        except Exception as e:
            return no_update, no_update, no_update, no_update, {}, f"加载失败：{e}\n{traceback.format_exc()}"

    # 2. 展开/折叠各分析区块
    for name in ("formula", "plot", "peak", "ring"):
        @app.callback(
            Output(f"collapse-{name}", "is_open"),
            Input(f"btn-collapse-{name}", "n_clicks"),
            State(f"collapse-{name}", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_collapse(n, is_open):
            return not is_open

    # 3. 选行 → 绘制光谱图
    @app.callback(
        Output("graph-main", "figure"),
        Output("store-selected-keys", "data"),
        Input("datatable-spectra", "selected_rows"),
        State("store-manager", "data"),
        State("store-folder", "data"),
        State("select-datatype", "value"),
        State("store-reference", "data"),
        State("input-title", "value"),
        State("input-xlabel", "value"),
        State("input-ylabel", "value"),
        State("input-xmin", "value"),
        State("input-xmax", "value"),
        State("input-ymin", "value"),
        State("input-ymax", "value"),
        prevent_initial_call=True,
    )
    def plot_selected(selected_rows, table_json, folder, data_type, reference,
                      title, xlabel, ylabel, xmin, xmax, ymin, ymax):
        if not selected_rows or not table_json or not folder:
            return _empty_fig(), []

        try:
            table = pd.read_json(io.StringIO(table_json), orient='split')
            mgr = _load_manager(folder, data_type, reference or None)
            traces = []
            selected_keys = []
            for row_idx in selected_rows:
                key = mgr.keys[table.iloc[row_idx]['index']]
                x, y = mgr.get_xy(key)
                name = key.replace('_array', '').replace('_', ' ')
                traces.append(go.Scatter(x=x, y=y, mode='lines', name=name, line=dict(width=1.2)))
                selected_keys.append(key)

            xrange = [xmin, xmax] if (xmin is not None or xmax is not None) else None
            yrange = [ymin, ymax] if (ymin is not None or ymax is not None) else None
            fig = _spectrum_fig(
                traces,
                title=title or '',
                xlabel=xlabel or 'Wavelength (nm)',
                ylabel=ylabel or 'Insertion Loss (dB)',
                xrange=xrange,
                yrange=yrange,
            )
            return fig, selected_keys
        except Exception as e:
            return _empty_fig(f"绘图出错：{e}"), []

    # 4. 峰值/谷值分析
    @app.callback(
        Output("graph-main", "figure", allow_duplicate=True),
        Output("div-analysis-result", "children"),
        Output("pre-log", "children", allow_duplicate=True),
        Input("btn-peak", "n_clicks"),
        State("store-selected-keys", "data"),
        State("store-folder", "data"),
        State("select-datatype", "value"),
        State("store-reference", "data"),
        State("radio-peak-type", "value"),
        State("input-peak-xmin", "value"),
        State("input-peak-xmax", "value"),
        State("input-peak-threshold", "value"),
        State("input-peak-distance", "value"),
        State("input-title", "value"),
        State("input-xlabel", "value"),
        State("input-ylabel", "value"),
        State("input-xmin", "value"),
        State("input-xmax", "value"),
        State("input-ymin", "value"),
        State("input-ymax", "value"),
        prevent_initial_call=True,
    )
    def run_peak(n, keys, folder, data_type, reference, peak_type,
                 pxmin, pxmax, threshold, distance,
                 title, xlabel, ylabel, xmin, xmax, ymin, ymax):
        if not keys or not folder:
            raise PreventUpdate

        try:
            mgr = _load_manager(folder, data_type, reference or None)
            is_peak = (peak_type == 'peak')
            x_range = None
            if pxmin is not None or pxmax is not None:
                x_range = (pxmin, pxmax)
            dist = int(distance) if distance else 50

            traces = []
            result_lines = []
            for key in keys:
                x, y = mgr.get_xy(key)
                name = key.replace('_array', '').replace('_', ' ')
                traces.append(go.Scatter(x=x, y=y, mode='lines', name=name,
                                         line=dict(width=1.2)))
                res = analyze_peaks(x, y, is_peak=is_peak, x_range=x_range,
                                    threshold=threshold, distance=dist)
                label = "峰" if is_peak else "谷"
                symbol = 'triangle-up' if is_peak else 'triangle-down'
                color = '#ef4444' if is_peak else '#3b82f6'
                if len(res['x_peaks']) > 0:
                    traces.append(go.Scatter(
                        x=res['x_peaks'], y=res['y_peaks'],
                        mode='markers', name=f'{name} {label}位',
                        marker=dict(symbol=symbol, size=8, color=color),
                        showlegend=True,
                    ))
                lines = format_peak_results(res, is_peak=is_peak)
                result_lines.append(f"[{name}]")
                result_lines.extend(lines if lines else [f"  未检测到{label}值"])

            xrange = [xmin, xmax] if (xmin is not None or xmax is not None) else None
            yrange = [ymin, ymax] if (ymin is not None or ymax is not None) else None
            fig = _spectrum_fig(traces, title=title or '', xlabel=xlabel or 'Wavelength (nm)',
                                ylabel=ylabel or 'Insertion Loss (dB)',
                                xrange=xrange, yrange=yrange)
            return fig, "\n".join(result_lines), f"峰值分析完成，共 {len(keys)} 条曲线"
        except Exception as e:
            return no_update, f"分析出错：{e}", traceback.format_exc()

    # 5. FSR 分析
    @app.callback(
        Output("graph-main", "figure", allow_duplicate=True),
        Output("div-analysis-result", "children", allow_duplicate=True),
        Output("pre-log", "children", allow_duplicate=True),
        Input("btn-fsr", "n_clicks"),
        State("store-selected-keys", "data"),
        State("store-folder", "data"),
        State("select-datatype", "value"),
        State("store-reference", "data"),
        State("input-ring-height", "value"),
        State("input-ring-distance", "value"),
        prevent_initial_call=True,
    )
    def run_fsr(n, keys, folder, data_type, reference, height, distance):
        if not keys or not folder:
            raise PreventUpdate
        key = keys[0]
        try:
            mgr = _load_manager(folder, data_type, reference or None)
            x, y = mgr.get_xy(key)
            ring = Ring(x, y)
            ring.cal_fsr(display=False,
                         height_threshold=height,
                         min_distance=int(distance) if distance else None)

            traces = [go.Scatter(x=x, y=y, mode='lines', name='光谱',
                                 line=dict(width=1.2, color='#1e293b'))]
            if ring.lambda0 is not None and len(ring.lambda0) > 0:
                y_peaks = np.interp(ring.lambda0, x, y)
                traces.append(go.Scatter(
                    x=ring.lambda0, y=y_peaks, mode='markers', name='谐振峰',
                    marker=dict(symbol='triangle-down', size=8, color='#ef4444'),
                ))

            fsr_text = ""
            if ring.fsr_mean is not None:
                fsr_text = f"FSR 均值 = {ring.fsr_mean * 1e3:.4f} pm\n"
            if ring.lambda0 is not None:
                fsr_text += f"谐振峰数 = {len(ring.lambda0)}\n"
                if len(ring.lambda0) > 1:
                    fsrs = np.diff(ring.lambda0) * 1e3
                    fsr_text += "各 FSR (pm): " + ", ".join(f"{v:.2f}" for v in fsrs)

            fig = _spectrum_fig(traces, title='FSR 分析',
                                xlabel='Wavelength (nm)', ylabel='Insertion Loss (dB)')
            return fig, fsr_text, "FSR 分析完成"
        except Exception as e:
            return no_update, f"FSR 分析出错：{e}", traceback.format_exc()

    # 6. Q 因子分析
    @app.callback(
        Output("graph-main", "figure", allow_duplicate=True),
        Output("div-analysis-result", "children", allow_duplicate=True),
        Output("pre-log", "children", allow_duplicate=True),
        Input("btn-q", "n_clicks"),
        State("store-selected-keys", "data"),
        State("store-folder", "data"),
        State("select-datatype", "value"),
        State("store-reference", "data"),
        prevent_initial_call=True,
    )
    def run_q(n, keys, folder, data_type, reference):
        if not keys or not folder:
            raise PreventUpdate
        key = keys[0]
        try:
            mgr = _load_manager(folder, data_type, reference or None)
            x, y = mgr.get_xy(key)
            ring = Ring(x, y)
            _, log = _capture_stdout(ring.cal_Q, display=False)

            traces = [go.Scatter(x=x, y=y, mode='lines', name='光谱',
                                 line=dict(width=1.2, color='#1e293b'))]
            fig = _spectrum_fig(traces, title='Q 因子分析',
                                xlabel='Wavelength (nm)', ylabel='Insertion Loss (dB)')
            return fig, log or "Q 因子分析完成（无输出）", "Q 因子分析完成"
        except Exception as e:
            return no_update, f"Q 分析出错：{e}", traceback.format_exc()

    # 7. 公式计算
    @app.callback(
        Output("graph-main", "figure", allow_duplicate=True),
        Output("div-analysis-result", "children", allow_duplicate=True),
        Output("pre-log", "children", allow_duplicate=True),
        Input("btn-formula", "n_clicks"),
        State("input-formula", "value"),
        State("store-selected-keys", "data"),
        State("store-folder", "data"),
        State("select-datatype", "value"),
        State("store-reference", "data"),
        State("input-title", "value"),
        State("input-xlabel", "value"),
        State("input-ylabel", "value"),
        prevent_initial_call=True,
    )
    def run_formula(n, formula, keys, folder, data_type, reference,
                    title, xlabel, ylabel):
        if not formula or not keys or not folder:
            raise PreventUpdate
        try:
            from core.grid import interp_on_grid, create_uniform_grid
            mgr = _load_manager(folder, data_type, reference or None)
            arrays = {}
            x_ref = None
            for i, key in enumerate(keys):
                x, y = mgr.get_xy(key)
                if x_ref is None:
                    x_ref = x
                elif len(x) != len(x_ref):
                    y = interp_on_grid(x, y, x_ref, mode='edge')
                arrays[f'A{i}'] = y

            if x_ref is None:
                raise ValueError("无数据")

            result = eval(formula, {"__builtins__": {}}, {**arrays, 'np': np})
            trace = go.Scatter(x=x_ref, y=result, mode='lines',
                               name=formula, line=dict(width=1.5, color='#7c3aed'))
            fig = _spectrum_fig([trace], title=title or formula,
                                xlabel=xlabel or 'Wavelength (nm)',
                                ylabel=ylabel or 'Value')
            return fig, f"公式 [{formula}] 计算完成", "公式计算完成"
        except Exception as e:
            return no_update, f"公式计算出错：{e}", traceback.format_exc()
