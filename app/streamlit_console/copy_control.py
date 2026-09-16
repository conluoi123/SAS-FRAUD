"""Small reusable copy controls for Streamlit identifiers and JSON."""

from __future__ import annotations

from base64 import b64encode
from html import escape

import streamlit as st
import streamlit.components.v1 as components


def copy_control_html(value: str, label: str = "Copy") -> str:
    """Return isolated clipboard-button markup without exposing raw text in HTML."""

    encoded = b64encode(str(value).encode("utf-8")).decode("ascii")
    safe_label = escape(label)
    return f"""
    <button id="copy" style="border:1px solid #b8c5d3;border-radius:7px;background:#fff;
    color:#0b3558;padding:8px 14px;font:600 14px system-ui;cursor:pointer">{safe_label}</button>
    <span id="status" style="color:#4b6478;font:13px system-ui;margin-left:8px"></span>
    <script>
    const text = new TextDecoder().decode(Uint8Array.from(atob('{encoded}'), c => c.charCodeAt(0)));
    document.getElementById('copy').onclick = async () => {{
      try {{ await navigator.clipboard.writeText(text); document.getElementById('status').innerText='Copied'; }}
      catch (_) {{ document.getElementById('status').innerText='Copy is unavailable in this browser'; }}
    }};
    </script>
    """


def render_copy_control(value: str, label: str = "Copy") -> None:
    if value:
        components.html(copy_control_html(value, label), height=42)


def render_copyable_value(
    title: str,
    value: str | None,
    *,
    button_label: str = "Copy",
) -> None:
    """Render a labeled identifier with both Streamlit and explicit copy controls."""

    st.markdown(f"**{title}**")
    if value:
        st.code(str(value), language=None)
        render_copy_control(str(value), button_label)
    else:
        st.write("—")
