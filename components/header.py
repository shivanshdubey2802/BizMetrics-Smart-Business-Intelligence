import streamlit as st
from utils.translations import t, normalize_lang, get_current_language, set_current_language

def render_html(html_str: str):
    clean_lines = [line.strip() for line in html_str.splitlines() if line.strip()]
    cleaned = "\n".join(clean_lines)
    if hasattr(st, "html"):
        st.html(cleaned)
    else:
        st.markdown(cleaned, unsafe_allow_html=True)

def render_header(title_key, description_key, badge_type=None):
    lang = get_current_language()
    
    # Breadcrumb and Return to Dashboard navigation for all non-dashboard pages
    active_stem = st.session_state.get("active_sidebar_page", "")
    if not active_stem:
        try:
            from components.sidebar import _get_active_page_stem
            active_stem = _get_active_page_stem()
        except Exception:
            active_stem = ""

    if active_stem and "01_dashboard" not in active_stem:
        nav_top1, nav_top2 = st.columns([2.0, 3.0])
        with nav_top1:
            try:
                st.page_link("pages/01_dashboard.py", label=t("← Return to Executive Dashboard", lang), icon="🏠")
            except Exception:
                safe_stem = active_stem.replace("/", "_").replace(".", "_")
                if st.button(f"🏠 ← {t('Return to Executive Dashboard', lang)}", key=f"btn_ret_dash_top_{safe_stem}"):
                    st.switch_page("pages/01_dashboard.py")
        with nav_top2:
            st.markdown(
                f"<div style='font-size: 0.86rem; color: #64748B; margin-top: 5px; text-align: right;'>"
                f"BizMetrics &nbsp;›&nbsp; <strong style='color: #0D9488;'>{t(title_key, lang)}</strong>"
                f"</div>",
                unsafe_allow_html=True
            )
        render_html("<div style='height: 0.25rem;'></div>")

    col1, col2 = st.columns([3.0, 2.0])
    
    with col1:
        render_html(f"<h1 style='margin-bottom: 0.2rem; color: #1E293B; font-family: \"Playfair Display\", serif; font-weight: 700;'>{t(title_key, lang)}</h1>")
        render_html(f"<p style='color: #64748B; font-size: 0.98rem; margin-top: 0; line-height: 1.4;'>{t(description_key, lang)}</p>")
        
    with col2:
        # Top-right branch switcher & language dropdown
        lang_col1, lang_col2 = st.columns([1.5, 1.0])
        safe_k = "".join(c for c in str(title_key) if c.isalnum())[:12] or "hdr"

        with lang_col1:
            if st.session_state.get("owner_authenticated", False):
                try:
                    from utils.multi_shop import get_branch_selector_options
                    branch_opts = get_branch_selector_options()
                    curr_branch = st.session_state.get("shop_id", "shivansh_electronics_hardware")
                    branch_keys = list(branch_opts.keys())
                    b_idx = branch_keys.index(curr_branch) if curr_branch in branch_keys else 0
                    sel_branch = st.selectbox(
                        "Branch",
                        options=branch_keys,
                        index=b_idx,
                        format_func=lambda k: branch_opts.get(k, k),
                        key=f"header_branch_{safe_k}",
                        label_visibility="collapsed",
                        help="Switch Active Store Branch or view Consolidated Network",
                    )
                    if sel_branch != curr_branch:
                        st.session_state["shop_id"] = sel_branch
                        st.session_state["shop_name"] = branch_opts.get(sel_branch, "Consolidated")
                        st.rerun()
                except Exception:
                    pass

        with lang_col2:
            options = ["English", "हिंदी", "Hinglish"]
            current_idx = options.index(lang) if lang in options else 0
            
            def _on_global_lang_change():
                new_lang = st.session_state.get("global_language_dropdown")
                if new_lang:
                    set_current_language(new_lang)

            selected_lang = st.selectbox(
                "Language Selector",
                options=options,
                index=current_idx,
                key="global_language_dropdown",
                label_visibility="collapsed",
                help="Switch language: English | हिंदी | Hinglish",
                on_change=_on_global_lang_change
            )
            if selected_lang != lang:
                set_current_language(selected_lang)
                st.rerun()

        # Optional illustration badge matching the reference screenshots
        if badge_type == "schemes":
            render_html(
                '<div style="display:flex; align-items:center; justify-content:flex-end; gap:12px; margin-top:-0.4rem; padding-right:0.5rem;">'
                '<div style="text-align:right;">'
                f'<div style="font-size:0.75rem; font-weight:700; color:#1E3A8A; line-height:1.2;">{t("Empowering<br>Rural Entrepreneurs", lang)}</div>'
                f'<div style="font-size:0.72rem; color:#D97706; font-weight:600;">{t("for a", lang)} <span style="color:#059669; font-weight:700;">{t("Stronger India", lang)}</span></div>'
                '</div>'
                '<div style="position:relative; width:90px; height:50px; background:linear-gradient(135deg, rgba(254,243,199,0.7), rgba(219,234,254,0.7)); border-radius:10px; border:1px solid #E2E8F0; display:flex; align-items:center; justify-content:center; overflow:hidden;">'
                '<div style="position:absolute; top:0; left:0; right:0; height:4px; background:linear-gradient(90deg, #FF9933 0%, #FFFFFF 50%, #138808 100%);"></div>'
                '<span style="font-size:1.6rem;">🏛️🇮🇳</span>'
                '</div>'
                '</div>'
            )
        elif badge_type == "hyperlocal":
            render_html(
                '<div style="display:flex; align-items:center; justify-content:flex-end; gap:12px; margin-top:-0.4rem; padding-right:0.5rem;">'
                '<div style="text-align:right;">'
                f'<div style="font-size:0.78rem; font-weight:700; color:#0D9488; line-height:1.2;">{t("Local Insights", lang)}</div>'
                f'<div style="font-size:0.75rem; color:#059669; font-weight:700;">{t("Bigger Opportunities", lang)}</div>'
                '</div>'
                '<div style="width:75px; height:50px; background:linear-gradient(135deg, #ECFDF5, #EFF6FF); border-radius:10px; border:1px solid #E2E8F0; display:flex; align-items:center; justify-content:center; box-shadow:0 1px 4px rgba(0,0,0,0.04);">'
                '<span style="font-size:1.6rem;">🏪📍</span>'
                '</div>'
                '</div>'
            )
            
    render_html("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 0.5rem 0 1.25rem 0;'>")


