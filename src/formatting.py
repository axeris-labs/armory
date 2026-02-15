"""Standard number formatters (Sentora convention)."""

import math

import pandas as pd


def fmt_pct(value: float, decimals: int = 2) -> str:
    """Format a percentage value. Expects value already in % (e.g. 5.25 -> '5.25%')."""
    return f"{value:.{decimals}f}%"


def fmt_tokens(value: float, symbol: str = "") -> str:
    """Format token amounts with human-readable suffixes (K/M/B)."""
    suffix = f" {symbol}" if symbol else ""
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f}B{suffix}"
    if abs_val >= 1_000_000:
        return f"{value / 1_000_000:,.2f}M{suffix}"
    if abs_val >= 1_000:
        return f"{value / 1_000:,.2f}K{suffix}"
    return f"{value:,.2f}{suffix}"


def fmt_val(val) -> str:
    """Format numeric values with K/M suffixes. Handles NaN/null as 0."""
    val = float(val) if pd.notnull(val) else 0
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    elif val >= 1_000:
        return f"{val / 1_000:.2f}K"
    else:
        return f"{val:,.2f}"
