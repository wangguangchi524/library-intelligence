from __future__ import annotations

from typing import Any, Sequence

import plotly.graph_objects as go

PALETTE = ["#1D3557", "#2563EB", "#14B8A6", "#D97706", "#7C3AED", "#0EA5E9", "#16A34A", "#DC2626", "#64748B"]
FONT = "Segoe UI, Microsoft YaHei, sans-serif"


def _layout(fig: go.Figure, title: str = "", height: int = 330) -> go.Figure:
    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#172033"}, "x": 0.01},
        height=height,
        margin={"l": 8, "r": 12, "t": 42, "b": 24},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT, "size": 12, "color": "#475569"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        hoverlabel={"font": {"family": FONT}},
    )
    fig.update_xaxes(showgrid=False, linecolor="#E2E8F0", tickfont={"color": "#64748B"})
    fig.update_yaxes(gridcolor="#EEF2F7", zeroline=False, tickfont={"color": "#64748B"})
    return fig


def donut(labels: Sequence[str], values: Sequence[float], title: str = "", height: int = 330) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=list(labels), values=list(values), hole=0.62,
        marker={"colors": PALETTE[:len(labels)], "line": {"color": "#FFFFFF", "width": 2}},
        textinfo="percent", hovertemplate="%{label}<br>数量 %{value}<br>占比 %{percent}<extra></extra>",
    ))
    fig.add_annotation(text=f"<b>{sum(values):,}</b><br><span style='font-size:11px'>合计</span>",
                       x=0.5, y=0.5, showarrow=False, font={"size": 18, "color": "#172033"})
    fig = _layout(fig, title, height)
    fig.update_layout(legend={"orientation": "h", "yanchor": "top", "y": -0.06, "x": 0.5, "xanchor": "center"},
                      margin={"l": 8, "r": 12, "t": 42, "b": 46})
    return fig


def bar(x: Sequence[Any], y: Sequence[Any], title: str = "", horizontal: bool = False,
        color: str = "#2563EB", height: int = 330, text: bool = True) -> go.Figure:
    if horizontal:
        fig = go.Figure(go.Bar(x=list(y), y=list(x), orientation="h",
                               marker_color=color, text=list(y) if text else None,
                               textposition="auto",
                               hovertemplate="%{y}<br>数量 %{x}<extra></extra>"))
    else:
        fig = go.Figure(go.Bar(x=list(x), y=list(y), marker_color=color,
                               text=list(y) if text else None, textposition="auto",
                               hovertemplate="%{x}<br>数量 %{y}<extra></extra>"))
    return _layout(fig, title, height)


def line(x: Sequence[Any], y: Sequence[Any], title: str = "", height: int = 330,
         color: str = "#14B8A6", fill: bool = True) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=list(x), y=list(y), mode="lines+markers",
        line={"color": color, "width": 3, "shape": "spline"},
        marker={"size": 7, "color": color},
        fill="tozeroy" if fill else None,
        fillcolor="rgba(20,184,166,.10)" if fill else None,
        hovertemplate="%{x}<br>借阅量 %{y}<extra></extra>",
    ))
    return _layout(fig, title, height)


def multi_bar(labels: Sequence[str], series: dict[str, Sequence[float]], title: str = "",
              height: int = 350) -> go.Figure:
    fig = go.Figure()
    for i, (name, values) in enumerate(series.items()):
        fig.add_trace(go.Bar(name=name, x=list(labels), y=list(values), marker_color=PALETTE[i % len(PALETTE)]))
    fig.update_layout(barmode="group")
    return _layout(fig, title, height)


def histogram(values: Sequence[float], title: str = "", x_title: str = "", nbins: int = 12,
              height: int = 330, color: str = "#2563EB") -> go.Figure:
    fig = go.Figure(go.Histogram(x=list(values), nbinsx=nbins, marker_color=color, opacity=0.88,
                                 hovertemplate=f"{x_title} %{{x}}<br>数量 %{{y}}<extra></extra>"))
    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text="数量")
    return _layout(fig, title, height)


def box_groups(groups: list[dict[str, Any]], title: str = "", y_title: str = "价格",
               height: int = 360) -> go.Figure:
    fig = go.Figure()
    for i, group in enumerate(groups):
        fig.add_trace(go.Box(y=group.get("prices", []), name=group.get("category", "-"),
                             marker_color=PALETTE[i % len(PALETTE)], boxmean=True))
    fig.update_yaxes(title_text=y_title)
    return _layout(fig, title, height)


def grouped_bar_from_pairs(pairs: list[tuple[str, float]], title: str = "", color: str = "#2563EB",
                           height: int = 330) -> go.Figure:
    labels = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    return bar(labels, values, title, color=color, height=height, text=False)
