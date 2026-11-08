import streamlit as st
from utils.translations import t

def kpi_card(title, value, context=None):
    """
    Renders a premium standardized KPI card with automatic multilingual translation.
    """
    trans_title = t(title)
    trans_context = t(context) if context else ""
    context_html = f"<div style='margin-top: 0.45rem; font-size: 0.8rem; color: #0D9488; font-weight: 500;'>{trans_context}</div>" if trans_context else ""
    html_str = f'<div class="ep-card"><div class="ep-card-title">{trans_title}</div><div class="ep-card-value">{value}</div>{context_html}</div>'
    if hasattr(st, "html"):
        st.html(html_str)
    else:
        st.markdown(html_str, unsafe_allow_html=True)

def insight_card(title, text):
    """
    Renders an intelligent insight card with multilingual support.
    """
    trans_title = t(title)
    trans_text = t(text)
    html_str = f'<div class="ep-insight"><div class="ep-insight-title">{trans_title}</div><div class="ep-insight-text">{trans_text}</div></div>'
    if hasattr(st, "html"):
        st.html(html_str)
    else:
        st.markdown(html_str, unsafe_allow_html=True)


