import streamlit as st

def apply_theme():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');
            
            /* Global Background & Typography with Devanagari Script Support */
            .stApp {
                background-color: #FAF5EE !important;
            }

            * {
                font-family: 'Inter', 'Noto Sans Devanagari', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }

            /* Dark navy / dark headings across every page */
            h1, h2, h3, h4, h5, h6 {
                color: #1E293B !important;
                font-family: 'Playfair Display', 'Noto Sans Devanagari', Georgia, serif !important;
                font-weight: 700 !important;
                letter-spacing: -0.01em;
            }
            
            h1 { font-size: 2.1rem !important; }
            h2 { font-size: 1.5rem !important; }
            h3 { font-size: 1.25rem !important; }
            h4 { font-size: 1.05rem !important; }

            /* Paragraphs, labels, and secondary texts */
            p, span, label, li {
                color: #334155;
            }

            .stCaption, caption, .secondary-text {
                color: #64748B !important;
            }

            /* Sidebar */
            [data-testid="stSidebar"] {
                background-color: #EDE5D0 !important;
                border-right: 1px solid rgba(41, 38, 34, 0.12) !important;
            }

            [data-testid="stSidebarContent"] {
                background-color: #EDE5D0 !important;
            }

            /* Hide native unstyled sidebar navigation */
            [data-testid="stSidebarNav"] {
                display: none !important;
            }

            /* Keep native collapse button visible at top-right */
            header[data-testid="stHeader"] {
                background: transparent !important;
            }

            [data-testid="stSidebarCollapseButton"],
            [data-testid="collapsedControl"] {
                visibility: visible !important;
                display: flex !important;
                color: #78805B !important;
            }

            /* Standardized Card Containers */
            .ep-card, .stCard, [data-testid="stMetric"], [data-testid="stVerticalBlockBorderWrapper"] {
                background-color: #FFFFFF !important;
                border: 1px solid #E2E8F0 !important;
                border-radius: 12px !important;
                padding: 1.25rem 1.4rem !important;
                box-shadow: 0 2px 8px rgba(30, 41, 59, 0.04) !important;
                margin-bottom: 0.85rem !important;
            }

            .ep-card-title, [data-testid="stMetricLabel"] p {
                color: #0D9488 !important;
                font-size: 0.78rem !important;
                font-weight: 700 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.05em !important;
                margin-bottom: 0.35rem !important;
                font-family: 'Inter', sans-serif !important;
            }

            .ep-card-value, [data-testid="stMetricValue"] {
                font-size: 1.65rem !important;
                font-weight: 700 !important;
                color: #1E293B !important;
                font-family: 'Inter', sans-serif !important;
            }

            /* Insight Cards */
            .ep-insight {
                background-color: #FFFFFF !important;
                border: 1px solid #E2E8F0 !important;
                border-left: 4px solid #0D9488 !important;
                border-radius: 12px !important;
                padding: 1.1rem 1.3rem !important;
                box-shadow: 0 2px 6px rgba(30, 41, 59, 0.04) !important;
                margin-bottom: 0.85rem !important;
            }

            .ep-insight-title {
                color: #1E293B !important;
                font-size: 0.95rem !important;
                font-weight: 700 !important;
                margin-bottom: 0.25rem !important;
                font-family: 'Playfair Display', Georgia, serif !important;
            }

            .ep-insight-text {
                color: #475569 !important;
                font-size: 0.86rem !important;
                line-height: 1.5 !important;
            }

            /* Standardized Tabs styling */
            [data-baseweb="tab-list"] {
                gap: 1.25rem !important;
                border-bottom: 2px solid #E2E8F0 !important;
                background-color: transparent !important;
                padding-bottom: 2px !important;
                margin-bottom: 1.25rem !important;
            }

            [data-baseweb="tab"] {
                background-color: transparent !important;
                color: #64748B !important;
                font-weight: 600 !important;
                font-size: 0.94rem !important;
                padding: 0.5rem 0.25rem !important;
                border-bottom: 3px solid transparent !important;
            }

            [data-baseweb="tab"]:hover {
                color: #1E293B !important;
            }

            [data-baseweb="tab"][aria-selected="true"] {
                color: #2563EB !important;
                border-bottom: 3px solid #2563EB !important;
                font-weight: 700 !important;
            }

            /* Consistent Inputs, Selectboxes, and Sliders */
            [data-baseweb="select"] > div,
            [data-testid="stTextInput"] input,
            [data-testid="stNumberInput"] input,
            [data-testid="stDateInput"] input,
            [data-testid="stMultiSelect"] input {
                background-color: #FFFFFF !important;
                color: #1E293B !important;
                border: 1px solid #E2E8F0 !important;
                border-radius: 8px !important;
                font-size: 0.92rem !important;
            }

            [data-baseweb="select"] span,
            [data-baseweb="select"] div,
            [data-testid="stTextInput"] label,
            [data-testid="stNumberInput"] label,
            [data-testid="stDateInput"] label,
            [data-testid="stMultiSelect"] label,
            [data-testid="stSlider"] label {
                color: #1E293B !important;
                font-weight: 600 !important;
                font-size: 0.88rem !important;
            }

            [data-baseweb="select"] > div:focus-within,
            [data-testid="stTextInput"] input:focus,
            [data-testid="stNumberInput"] input:focus,
            [data-testid="stDateInput"] input:focus {
                border-color: #2563EB !important;
                box-shadow: 0 0 0 1px #2563EB !important;
            }

            /* Slider Warm Theme */
            [data-testid="stSlider"] div[role="slider"] {
                background-color: #EA580C !important;
                border-color: #EA580C !important;
            }
            [data-testid="stSlider"] div[data-testid="stThumbValue"] {
                color: #1E293B !important;
                font-weight: 700 !important;
            }

            /* Primary Global Buttons (Blue Action style) */
            .stButton > button,
            .stDownloadButton > button,
            [data-testid="stFormSubmitButton"] > button {
                color: #FFFFFF !important;
                background-color: #2563EB !important;
                border: 1px solid #2563EB !important;
                border-radius: 8px !important;
                font-weight: 700 !important;
                font-size: 0.9rem !important;
                padding: 0.5rem 1.25rem !important;
                box-shadow: 0 2px 4px rgba(37, 99, 235, 0.15) !important;
                transition: all 0.15s ease-in-out !important;
            }

            .stButton > button:hover,
            .stDownloadButton > button:hover,
            [data-testid="stFormSubmitButton"] > button:hover {
                background-color: #1D4ED8 !important;
                border-color: #1D4ED8 !important;
                box-shadow: 0 4px 8px rgba(37, 99, 235, 0.22) !important;
            }

            /* Dataframes & Tables */
            [data-testid="stDataFrame"], [data-testid="stTable"] {
                border-radius: 10px !important;
                overflow: hidden !important;
                border: 1px solid #E2E8F0 !important;
                background-color: #FFFFFF !important;
            }

            /* Alerts & Info callouts */
            .stAlert {
                border-radius: 10px !important;
                border: 1px solid #E2E8F0 !important;
            }

            /* Responsive Mobile Optimization (@media <= 768px) */
            @media (max-width: 768px) {
                h1 { font-size: 1.65rem !important; }
                h2 { font-size: 1.35rem !important; }
                h3 { font-size: 1.15rem !important; }
                .stApp {
                    padding: 0.5rem 0.5rem !important;
                }
                [data-testid="stMetric"], .ep-card, .stCard {
                    padding: 0.9rem 1rem !important;
                    margin-bottom: 0.5rem !important;
                }
                /* Ensure touch targets meet 44px mobile accessibility standard */
                .stButton > button,
                .stDownloadButton > button,
                [data-testid="stFormSubmitButton"] > button {
                    min-height: 44px !important;
                    padding: 0.5rem 1rem !important;
                    font-size: 0.9rem !important;
                }
                /* Scrollable responsive tables & chart containers */
                [data-testid="stDataFrame"], [data-testid="stTable"], .js-plotly-plot {
                    max-width: 100vw !important;
                    overflow-x: auto !important;
                }
            }
        </style>
    """, unsafe_allow_html=True)

def get_colors():
    return {
        # Core Unified Palette
        "background": "#FAF5EE",
        "bg": "#FAF5EE",
        "page_bg": "#FAF5EE",
        "primary": "#1E293B",
        "navy": "#1E293B",
        "text": "#1E293B",
        "secondary": "#0D9488",
        "muted_teal": "#0D9488",
        "teal": "#0D9488",
        "card": "#FFFFFF",
        "card_bg": "#FFFFFF",
        "white": "#FFFFFF",
        "border": "#E2E8F0",
        "light_grey": "#E2E8F0",
        "sidebar_bg": "#EDE5D0",
        "limestone": "#EDE5D0",
        "slate": "#64748B",
        "blue": "#2563EB",
        "primary_action": "#2563EB",
        "orange": "#EA580C",
        "warning": "#EA580C",
        "green": "#059669",
        "success": "#059669",
        "purple": "#7C3AED",
        "ai": "#7C3AED",
        # Scheme Category Accents
        "credit_finance": "#2563EB",
        "subsidies_capital": "#EA580C",
        "digital_market": "#0D9488",
        "insurance_social": "#059669",
        "training_skilling": "#9333EA",
        # Backward-compatibility aliases for older page references
        "terracotta": "#EA580C",
        "olive": "#0D9488",
        "deep_rust": "#9D4330",
        "forest": "#059669",
        "gold": "#D97706",
    }

def render_html(html_str: str):
    """
    Safely renders HTML without risk of CommonMark 4-space indented code block parsing.
    Collapses all whitespace so no line starts with leading whitespace.
    """
    cleaned = " ".join(html_str.split())
    if hasattr(st, "html"):
        st.html(cleaned)
    else:
        st.markdown(cleaned, unsafe_allow_html=True)

