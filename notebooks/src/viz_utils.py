"""
viz_utils.py — Reusable visualization utilities for HPT Data Analytics.

This module provides a consistent design system, chart helpers, KPI card
renderers, and formatting functions. Import this at the top of any notebook:

    import sys; sys.path.insert(0, '../src')
    from viz_utils import *
    setup()  # Apply style globally
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.gridspec as gridspec
import seaborn as sns
from IPython.display import display, HTML

# ──────────────────────────────────────────────────────────────────────
# 1. PROJECT PATHS
# ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parents[1]
FIG_DIR = BASE_DIR / 'figures'
FIG_DIR.mkdir(exist_ok=True, parents=True)

# ──────────────────────────────────────────────────────────────────────
# 2. DESIGN TOKENS
# ──────────────────────────────────────────────────────────────────────

PALETTE = {
    # Core
    'primary':   '#2D6A4F',
    'secondary': '#52B788',
    'accent':    '#F4A261',
    'danger':    '#E76F51',
    'neutral':   '#6C757D',
    'light':     '#F8F9FA',
    'dark':      '#212529',
    # Extended
    'blue':      '#457B9D',
    'purple':    '#9B5DE5',
    'stockout':  '#E63946',
    'overstock': '#F4A261',
    'stable':    '#2A9D8F',
    'warning':   '#E9C46A',
}

# Ordered list for multi-category charts
COLORS_SEQ = [
    PALETTE['primary'], PALETTE['blue'], PALETTE['accent'],
    PALETTE['secondary'], PALETTE['purple'], PALETTE['stable'],
    PALETTE['danger'], PALETTE['warning'], PALETTE['neutral'],
]

# Text colors
TEXT_DARK  = '#2B3A42'
TEXT_MUTED = '#7f8c8d'
TEXT_TICK  = '#5B6D74'

# ──────────────────────────────────────────────────────────────────────
# 3. GLOBAL STYLE SETUP
# ──────────────────────────────────────────────────────────────────────

def setup() -> None:
    """Apply the HPT design system globally. Call once at notebook start."""
    sns.set_style('whitegrid')
    plt.rcParams.update({
        'figure.facecolor':  'white',
        'axes.facecolor':    'white',
        'axes.edgecolor':    '#DDDDDD',
        'axes.titleweight':  'bold',
        'axes.titlecolor':   TEXT_DARK,
        'axes.labelcolor':   TEXT_DARK,
        'xtick.color':       TEXT_TICK,
        'ytick.color':       TEXT_TICK,
        'font.size':         11,
        'axes.titlesize':    14,
        'axes.labelsize':    12,
        'xtick.labelsize':   10,
        'ytick.labelsize':   10,
        'legend.fontsize':   10,
        'figure.titlesize':  16,
        'grid.color':        '#E5E5E5',
        'grid.linestyle':    '--',
        'grid.linewidth':    0.6,
        'legend.frameon':    False,
        'figure.dpi':        120,
    })


# ──────────────────────────────────────────────────────────────────────
# 4. FORMATTING HELPERS
# ──────────────────────────────────────────────────────────────────────

def fmt_pct(val: float) -> str:
    """Format as percentage. val<1 → *100; val>=1 → as-is."""
    return f"{val * 100:.1f}%" if abs(val) < 1 else f"{val:.1f}%"


def fmt_currency(val: float, decimals: int = 0) -> str:
    """Format as Vietnamese currency (Tỷ / Tr / raw)."""
    if abs(val) >= 1e9:
        return f"{val / 1e9:.{decimals}f} Tỷ"
    if abs(val) >= 1e6:
        return f"{val / 1e6:.1f} Tr"
    return f"{val:,.0f}"


def fmt_num(val: float, decimals: int = 0) -> str:
    """Format number with thousands separator."""
    return f"{val:,.{decimals}f}"


# ──────────────────────────────────────────────────────────────────────
# 5. AXIS FORMATTING
# ──────────────────────────────────────────────────────────────────────

def clean_spines(ax: plt.Axes, right: bool = False) -> None:
    """Remove top spine, optionally keep right (for twinx)."""
    ax.spines['top'].set_visible(False)
    if not right:
        ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#CCCCCC')
    ax.spines['bottom'].set_color('#CCCCCC')
    ax.tick_params(colors=TEXT_TICK, which='both')
    ax.yaxis.label.set_color(TEXT_DARK)
    ax.xaxis.label.set_color(TEXT_DARK)
    ax.title.set_color(TEXT_DARK)


def clean_ax(
    ax: plt.Axes,
    title: str,
    xlabel: str = '',
    ylabel: str = '',
    subtitle: Optional[str] = None,
    right: bool = False,
) -> None:
    """Full axis cleanup: title, labels, subtitle, spines."""
    ax.set_title(title, fontsize=13, fontweight='bold', loc='left', pad=20)
    if subtitle:
        ax.text(0, 1.04, subtitle, transform=ax.transAxes,
                fontsize=10, color=TEXT_MUTED, style='italic')
    if xlabel:
        ax.set_xlabel(xlabel, fontweight='bold')
    if ylabel:
        ax.set_ylabel(ylabel, fontweight='bold')
    clean_spines(ax, right=right)


# ──────────────────────────────────────────────────────────────────────
# 6. BAR LABEL HELPERS
# ──────────────────────────────────────────────────────────────────────

def label_bars_v(
    ax: plt.Axes,
    fmt: Callable = None,
    offset: float = 0.02,
) -> None:
    """Attach value labels above vertical bars.

    Parameters
    ----------
    ax : Axes
    fmt : callable, optional – format function (default: 1 decimal)
    offset : float – relative gap above bar top
    """
    if fmt is None:
        fmt = lambda v: f"{v:.1f}"
    for bar in ax.patches:
        y = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y + abs(y) * offset,
            fmt(y),
            ha='center', va='bottom',
            fontsize=10, fontweight='bold', color=TEXT_DARK,
        )


def label_bars_h(
    ax: plt.Axes,
    fmt: Callable = None,
    offset: float = 0.01,
) -> None:
    """Attach value labels to the right of horizontal bars."""
    if fmt is None:
        fmt = lambda v: f"{v:.1f}"
    max_x = ax.get_xlim()[1]
    for bar in ax.patches:
        x = bar.get_width()
        ax.text(
            x + max_x * offset,
            bar.get_y() + bar.get_height() / 2,
            fmt(x),
            ha='left', va='center',
            fontsize=10, fontweight='bold', color=TEXT_DARK,
        )


# ──────────────────────────────────────────────────────────────────────
# 7. KPI CARDS (HTML — for notebooks)
# ──────────────────────────────────────────────────────────────────────

def kpi_cards(cards: List[Dict[str, str]]) -> None:
    """Render a flex-row of KPI cards in the notebook.

    Parameters
    ----------
    cards : list of dict
        Each dict: {'label': str, 'value': str, 'color': str (hex)}

    Example
    -------
    >>> kpi_cards([
    ...     {'label': 'Tổng Doanh Thu', 'value': '15.68 Tỷ', 'color': PALETTE['primary']},
    ...     {'label': 'Gross Margin',   'value': '9.7%',      'color': PALETTE['secondary']},
    ...     {'label': 'Tỷ lệ hủy đơn', 'value': '9.2%',      'color': PALETTE['danger']},
    ... ])
    """
    html = '<div style="display:flex; gap:15px; flex-wrap:wrap; margin:15px 0;">'
    for c in cards:
        color = c.get('color', PALETTE['primary'])
        html += f"""
        <div style="flex:1; min-width:180px; background:white;
                    border-left:5px solid {color}; padding:15px;
                    border-radius:5px; box-shadow:0 2px 4px rgba(0,0,0,0.08);">
            <p style="margin:0; font-size:12px; color:{TEXT_MUTED};
                      text-transform:uppercase; letter-spacing:0.04em;">
                {c['label']}</p>
            <p style="margin:8px 0 0 0; font-size:24px; font-weight:700;
                      color:{TEXT_DARK};">{c['value']}</p>
        </div>"""
    html += '</div>'
    display(HTML(html))


def kpi_card_mpl(
    ax: plt.Axes,
    title: str,
    value: str,
    subtitle: str = '',
    color: str = None,
) -> None:
    """Draw a single KPI card on a matplotlib Axes (for figure-based dashboards).

    Parameters
    ----------
    ax : Axes – will be turned off (no chart frame)
    title : str – small uppercase label
    value : str – large bold metric
    subtitle : str – small grey annotation
    color : str – left-border color (hex)
    """
    if color is None:
        color = PALETTE['primary']
    ax.axis('off')
    ax.plot([0.05, 0.05], [0.1, 0.9], color=color, lw=4,
            transform=ax.transAxes)
    ax.text(0.1, 0.70, title.upper(), fontsize=10, color=TEXT_MUTED,
            fontweight='bold', transform=ax.transAxes)
    ax.text(0.1, 0.35, value, fontsize=24, color=TEXT_DARK,
            fontweight='bold', transform=ax.transAxes)
    if subtitle:
        ax.text(0.1, 0.10, subtitle, fontsize=10, color=TEXT_MUTED,
                transform=ax.transAxes)


# ──────────────────────────────────────────────────────────────────────
# 8. SECTION HEADER (HTML — for notebooks)
# ──────────────────────────────────────────────────────────────────────

def section(title: str, subtitle: str = '') -> None:
    """Display a gradient section header in the notebook.

    Example
    -------
    >>> section('KPI tổng quan doanh nghiệp',
    ...         'Các chỉ số chiến lược quản lý hiệu suất kinh doanh')
    """
    sub_html = (
        f'<p style="color:rgba(255,255,255,0.7); margin:5px 0 0 0; '
        f'font-size:13px;">{subtitle}</p>' if subtitle else ''
    )
    html = f"""
    <div style="background:linear-gradient(135deg, #1B4332, #2D6A4F);
                padding:18px 25px; border-radius:8px; margin:25px 0 15px 0;">
        <h3 style="color:white; margin:0; font-size:16px; font-weight:700;">
            {title}</h3>
        {sub_html}
    </div>
    """
    display(HTML(html))


# ──────────────────────────────────────────────────────────────────────
# 9. QUICK CHART BUILDERS
# ──────────────────────────────────────────────────────────────────────

def bar_chart(
    x, y,
    title: str,
    ylabel: str = '',
    xlabel: str = '',
    color: str = None,
    horizontal: bool = False,
    figsize: tuple = (12, 6),
    fmt: Callable = None,
    highlight_top: int = 0,
    save_as: str = None,
) -> tuple:
    """Quick vertical or horizontal bar chart with labels.

    Parameters
    ----------
    x : array-like – categories
    y : array-like – values
    title : str
    horizontal : bool – if True, draw barh
    highlight_top : int – highlight top N bars in danger color
    save_as : str – filename (saved to FIG_DIR)

    Returns
    -------
    (fig, ax)
    """
    if color is None:
        color = PALETTE['primary']
    fig, ax = plt.subplots(figsize=figsize)

    if highlight_top > 0:
        sorted_idx = np.argsort(y)[::-1]
        colors = [PALETTE['danger'] if i in sorted_idx[:highlight_top]
                  else PALETTE['secondary'] for i in range(len(y))]
    else:
        colors = color

    if horizontal:
        ax.barh(x, y, color=colors, alpha=0.9, edgecolor='white')
        label_bars_h(ax, fmt=fmt)
    else:
        ax.bar(x, y, color=colors, alpha=0.9, edgecolor='white')
        label_bars_v(ax, fmt=fmt)

    ax.set_title(title, fontsize=14)
    if ylabel:
        ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    clean_spines(ax)
    plt.tight_layout()

    if save_as:
        fig.savefig(FIG_DIR / save_as, dpi=150, bbox_inches='tight')
    plt.show()
    return fig, ax


def line_chart(
    x, datasets: List[Dict],
    title: str,
    ylabel: str = '',
    xlabel: str = '',
    fill: bool = True,
    figsize: tuple = (14, 6),
    save_as: str = None,
) -> tuple:
    """Quick line chart with optional area fill.

    Parameters
    ----------
    x : array-like – x-axis values
    datasets : list of dict
        Each: {'y': array, 'label': str, 'color': str (optional)}
    fill : bool – fill area under first dataset

    Returns
    -------
    (fig, ax)
    """
    fig, ax = plt.subplots(figsize=figsize)
    for i, ds in enumerate(datasets):
        c = ds.get('color', COLORS_SEQ[i % len(COLORS_SEQ)])
        ax.plot(x, ds['y'], label=ds['label'], color=c, lw=2)
        if fill and i == 0:
            ax.fill_between(x, ds['y'], alpha=0.12, color=c)
    ax.set_title(title, fontsize=14)
    if ylabel:
        ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.legend()
    clean_spines(ax)
    plt.tight_layout()

    if save_as:
        fig.savefig(FIG_DIR / save_as, dpi=150, bbox_inches='tight')
    plt.show()
    return fig, ax


def pareto_chart(
    labels, values,
    title: str,
    ylabel: str = '',
    figsize: tuple = (12, 6),
    top_n_highlight: int = 2,
    save_as: str = None,
) -> tuple:
    """Pareto chart: bars (desc) + cumulative % line.

    Parameters
    ----------
    labels : array-like
    values : array-like (will be sorted descending)
    top_n_highlight : int – highlight top N bars in danger color

    Returns
    -------
    (fig, ax, ax2)
    """
    # Sort descending
    order = np.argsort(values)[::-1]
    labels = np.array(labels)[order]
    values = np.array(values, dtype=float)[order]
    cum_pct = values.cumsum() / values.sum() * 100

    fig, ax = plt.subplots(figsize=figsize)
    ax2 = ax.twinx()

    colors = [PALETTE['danger'] if i < top_n_highlight else PALETTE['accent']
              for i in range(len(values))]
    ax.bar(range(len(values)), values, color=colors, alpha=0.85)
    ax2.plot(range(len(values)), cum_pct, color=PALETTE['blue'],
             lw=2.5, marker='o', markersize=6)
    ax2.axhline(80, color='gray', ls='--', lw=1.2, alpha=0.7)
    ax2.text(len(values) - 1, 82, '80%', fontsize=9, color='gray',
             fontweight='bold')

    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, rotation=30, ha='right')
    ax.set_title(title, fontsize=14)
    if ylabel:
        ax.set_ylabel(ylabel, color=PALETTE['danger'], fontweight='bold')
    ax2.set_ylabel('Cumulative %', color=PALETTE['blue'], fontweight='bold')
    clean_spines(ax, right=True)
    plt.tight_layout()

    if save_as:
        fig.savefig(FIG_DIR / save_as, dpi=150, bbox_inches='tight')
    plt.show()
    return fig, ax, ax2


# ──────────────────────────────────────────────────────────────────────
# 10. DATA HELPERS
# ──────────────────────────────────────────────────────────────────────

def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Auto-convert columns with 'date' in name to datetime."""
    for col in df.columns:
        if 'date' in col.lower():
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def quick_profile(df: pd.DataFrame) -> None:
    """Print a quick data profile: shape, dtypes, missing, duplicates."""
    section('Data Profile', f'{df.shape[0]:,} rows × {df.shape[1]} columns')
    stats = pd.DataFrame({
        'dtype': df.dtypes,
        'non_null': df.notnull().sum(),
        'null': df.isnull().sum(),
        'null_%': (df.isnull().mean() * 100).round(1),
        'unique': df.nunique(),
        'sample': df.iloc[0] if len(df) else None,
    })
    display(stats)

    dup = df.duplicated().sum()
    cards = [
        {'label': 'Rows', 'value': fmt_num(df.shape[0]), 'color': PALETTE['primary']},
        {'label': 'Columns', 'value': str(df.shape[1]), 'color': PALETTE['blue']},
        {'label': 'Duplicates', 'value': fmt_num(dup),
         'color': PALETTE['danger'] if dup > 0 else PALETTE['stable']},
        {'label': 'Total Missing', 'value': fmt_num(df.isnull().sum().sum()),
         'color': PALETTE['accent'] if df.isnull().sum().sum() > 0 else PALETTE['stable']},
    ]
    kpi_cards(cards)


# ──────────────────────────────────────────────────────────────────────
# 11. EXPORT TO DASHBOARD
# ──────────────────────────────────────────────────────────────────────

def export_dashboard_json(
    data: Dict[str, Any],
    output_path: Union[str, Path] = None,
) -> None:
    """Export a dict as a JS variable for the web dashboard.

    Parameters
    ----------
    data : dict – must be JSON-serializable
    output_path : path – defaults to dashboard/js/data.js

    The output file will contain:
        const DASHBOARD_DATA = { ... };
    """
    import json
    if output_path is None:
        output_path = BASE_DIR / 'dashboard' / 'js' / 'data.js'
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    js = f'const DASHBOARD_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};'
    output_path.write_text(js, encoding='utf-8')
    print(f"✅ Exported dashboard data → {output_path}")


def save_fig(fig: plt.Figure, name: str, dpi: int = 150) -> None:
    """Save figure to FIG_DIR with standard settings."""
    fig.savefig(FIG_DIR / name, dpi=dpi, bbox_inches='tight')
    print(f"💾 Saved → {FIG_DIR / name}")
