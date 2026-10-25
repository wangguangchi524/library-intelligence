from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from web.utils.schema import fmt_date, fmt_datetime

ROOT = Path(__file__).resolve().parents[2]


def inject_theme() -> None:
    css_path = ROOT / "web" / "styles" / "theme.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def brand() -> None:
    st.markdown(
        """
        <div class="lib-brand">
          <div class="lib-brand-mark">LI</div>
          <div>
            <div class="lib-brand-title">Library Intelligence</div>
            <div class="lib-brand-sub">图书情报管理平台</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, mode: str, status: str, extra: str = "") -> None:
    mode_class = "demo" if "Demo" in mode else "mongo"
    st.markdown(
        f"""
        <div class="lib-page-head">
          <div>
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
          </div>
          <div class="lib-head-meta">
            <span class="lib-pill {mode_class}">{html.escape(mode)}</span>
            <span class="lib-pill neutral">{html.escape(status)}</span>
            <span class="lib-muted">{html.escape(extra)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, hint: str = "") -> None:
    st.markdown(
        f'<div class="lib-section"><span>{html.escape(title)}</span>'
        f'<small>{html.escape(hint)}</small></div>',
        unsafe_allow_html=True,
    )


def kpi_cards(items: list[dict[str, Any]]) -> None:
    cols = st.columns(len(items), gap="small")
    for col, item in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="lib-kpi">
                  <div class="lib-kpi-label">{html.escape(str(item.get("label", "")))}</div>
                  <div class="lib-kpi-value">{html.escape(str(item.get("value", "-")))}</div>
                  <div class="lib-kpi-hint">{html.escape(str(item.get("hint", "")))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def badge(label: str, kind: str = "info") -> str:
    return f'<span class="lib-badge {html.escape(kind)}">{html.escape(label)}</span>'


def empty_state(title: str, hint: str = "") -> None:
    st.markdown(
        f'<div class="lib-empty"><strong>{html.escape(title)}</strong>'
        f'<span>{html.escape(hint)}</span></div>',
        unsafe_allow_html=True,
    )


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "-"


def fmt_money(value: Any) -> str:
    try:
        return f"¥{float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def fmt_rating(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def to_dataframe(rows: list[dict[str, Any]], columns: dict[str, str] | None = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if columns:
        for col, label in columns.items():
            if col not in df.columns:
                df[col] = None
        df = df[list(columns)]
        df = df.rename(columns=columns)
    return df


def csv_download(df: pd.DataFrame, filename: str, label: str = "导出 CSV") -> None:
    if df.empty:
        return
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=filename, mime="text/csv", use_container_width=False)


def render_dataframe(df: pd.DataFrame, height: int = 420, key: str | None = None) -> None:
    if df.empty:
        empty_state("没有匹配的数据", "调整筛选条件后重试。")
        return
    fitted = min(height, max(120, 42 * len(df) + 48))
    st.dataframe(df, use_container_width=True, hide_index=True, height=fitted, key=key)


def format_record_date(value: Any, with_time: bool = False) -> str:
    return fmt_datetime(value) if with_time else fmt_date(value)
