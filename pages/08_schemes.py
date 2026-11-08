import html
import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from components.header import render_header
from utils.theme import apply_theme, get_colors
from utils.formatting import format_currency
from utils.sih_finance import build_quarterly_schedule, calculate_emi, financing_capacity, select_scheme
try:
    from utils.translations import t, get_current_language, translate_df
except (ImportError, AttributeError):
    import sys, importlib
    if "utils.translations" in sys.modules:
        importlib.reload(sys.modules["utils.translations"])
    try:
        from utils.translations import t, get_current_language, translate_df
    except Exception:
        from utils.translations import t, get_current_language
        def translate_df(df, lang=None):
            return df

st.set_page_config(page_title="BizMetrics - Schemes", layout="wide")
try:
    from utils.session_manager import ensure_authenticated_session
    if not ensure_authenticated_session(required_role="owner"):
        st.stop()
except Exception:
    if not st.session_state.get("owner_authenticated", False):
        st.switch_page("app.py")
apply_theme()
render_sidebar()
render_header(
    "Government Schemes & Financial Structuring",
    "Verified Central & State support schemes, loan eligibility routing, and capital calculators for micro-entrepreneurs.",
    badge_type="schemes"
)
lang = get_current_language()

colors = get_colors()

def render_html(html_str: str):
    """Render HTML safely without any markdown code-block or raw text leak."""
    cleaned = " ".join(html_str.split())
    if hasattr(st, "html"):
        st.html(cleaned)
    else:
        st.markdown(cleaned, unsafe_allow_html=True)

# Check dataset in session state if available
if "pipeline_result" not in st.session_state or "raw_data" not in st.session_state:
    try:
        from utils.data_loader import refresh_application_data
        refresh_application_data()
    except Exception:
        pass

result = st.session_state.get("pipeline_result", {})
schemes_data = result.get("schemes", {}) if isinstance(result, dict) else {}
promotions = schemes_data.get("promotions", [])

# ==============================================================================
# OFFICIAL VERIFIED SCHEMES DIRECTORY (Consistent Category-Based Color System)
# Category Accents:
# - Credit & Finance → Blue (#2563EB)
# - Subsidies & Capital → Orange (#EA580C)
# - Digital & Market → Teal (#0D9488)
# - Insurance & Social → Green (#059669)
# - Training & Skilling → Purple (#9333EA)
# ==============================================================================
OFFICIAL_SCHEMES = [
    {
        "category": "Credit & Finance",
        "color": "#2563EB",
        "schemes": [
            {
                "name": "PM SVANidhi (PM Street Vendor's AtmaNirbhar Nidhi)",
                "ministry": "Ministry of Housing & Urban Affairs",
                "tag": "Micro Credit",
                "color": "#2563EB",
                "brief": "Working capital loan for street vendors to restart and strengthen their business, with digital payments incentives.",
                "eligibility": "Street vendors with valid CoV or Letter of Recommendation",
                "loan_amount": "Up to ₹50,000 (in tranches: ₹10k, ₹20k, ₹50k)",
                "application": "Online via PM SVANidhi portal or nearest CSC centre",
                "badge_icon": "🛒",
                "badge_title": "Support Street Vendors",
                "badge_sub": "Build Better Livelihoods",
                "link": "https://pmsvanidhi.mohua.gov.in/",
            },
            {
                "name": "Pradhan Mantri MUDRA Yojana (PMMY) – Shishu / Kishore / Tarun",
                "ministry": "Ministry of Finance",
                "tag": "Enterprise Loan",
                "color": "#2563EB",
                "brief": "Collateral-free loans to micro and small enterprises for business development and income generation.",
                "eligibility": "Non-corporate, non-farm small/micro enterprises & shops",
                "loan_amount": "Shishu (≤₹50k), Kishore (≤₹5L), Tarun (≤₹10L)",
                "application": "Through commercial banks, RRBs, MFIs, NBFCs",
                "badge_icon": "🌱",
                "badge_title": "Small Loans",
                "badge_sub": "Big Dreams",
                "link": "https://www.mudra.org.in/",
            },
            {
                "name": "CGTMSE – Credit Guarantee Fund Trust for Micro & Small Enterprises",
                "ministry": "Ministry of MSME & SIDBI",
                "tag": "Credit Guarantee",
                "color": "#2563EB",
                "brief": "Collateral-free credit facility up to ₹5 crore with guarantee coverage of 75% to 85% of the sanctioned loan.",
                "eligibility": "New & existing MSEs in retail trade, manufacturing, or services",
                "loan_amount": "Credit guarantee up to ₹5.00 Crore (75%–85% cover)",
                "application": "Apply directly through Member Lending Institutions (MLIs)",
                "badge_icon": "🛡️",
                "badge_title": "Credit Guarantee",
                "badge_sub": "No Collateral Hassles",
                "link": "https://www.cgtmse.in/",
            },
            {
                "name": "Stand-Up India Scheme",
                "ministry": "Ministry of Finance (SIDBI)",
                "tag": "Composite Term Loan",
                "color": "#2563EB",
                "brief": "Bank composite loans (term loan + working capital) between ₹10 lakh and ₹1 crore for setting up greenfield enterprises.",
                "eligibility": "SC/ST and women entrepreneurs establishing a greenfield business",
                "loan_amount": "₹10 Lakh to ₹1.00 Crore (Term + Working Capital)",
                "application": "Through Stand-Up Mitra portal or scheduled commercial banks",
                "badge_icon": "🚀",
                "badge_title": "Stand-Up India",
                "badge_sub": "Inclusive Entrepreneurship",
                "link": "https://www.standupmitra.in/",
            },
        ],
    },
    {
        "category": "Subsidies & Capital",
        "color": "#EA580C",
        "schemes": [
            {
                "name": "PM Vishwakarma Yojana",
                "ministry": "Ministry of MSME",
                "tag": "Skill + Credit",
                "color": "#EA580C",
                "brief": "Collateral-free credit up to ₹3 lakh at 5% interest with ₹15,000 toolkit incentive and ₹500/day training stipend.",
                "eligibility": "Artisans & craftspeople across 18 designated traditional trades",
                "loan_amount": "Tranche 1: ₹1 Lakh, Tranche 2: ₹2 Lakh at 5% concessional rate",
                "application": "Online via PM Vishwakarma portal / CSC verification",
                "badge_icon": "🔨",
                "badge_title": "Artisan Empowerment",
                "badge_sub": "Modern Toolkits & Credit",
                "link": "https://pmvishwakarma.gov.in/",
            },
            {
                "name": "PMEGP – Prime Minister's Employment Generation Programme",
                "ministry": "Ministry of MSME (KVIC)",
                "tag": "Margin Subsidy",
                "color": "#EA580C",
                "brief": "Capital subsidy of 15% to 35% of project cost for micro-enterprise establishment in rural and urban areas.",
                "eligibility": "Individuals aged 18+; min. 8th pass for projects > ₹10L (mfg) / ₹5L (srv)",
                "loan_amount": "Up to ₹50 Lakh (Manufacturing) / ₹20 Lakh (Service/Retail)",
                "application": "Online application via KVIC e-portal",
                "badge_icon": "🏭",
                "badge_title": "Employment Creation",
                "badge_sub": "15%–35% Government Subsidy",
                "link": "https://www.kviconline.gov.in/pmegpeportal/",
            },
            {
                "name": "CLCSS – Credit Linked Capital Subsidy Scheme",
                "ministry": "Ministry of MSME",
                "tag": "Tech Upgrade",
                "color": "#EA580C",
                "brief": "Upfront 15% capital subsidy for induction of well-established and improved technology in approved sub-sectors.",
                "eligibility": "Micro and Small Enterprises with institutional term loans",
                "loan_amount": "15% capital subsidy on term loan up to ₹1.00 Crore",
                "application": "Through designated lending institutions / nodal banks",
                "badge_icon": "⚙️",
                "badge_title": "Tech Upgrade",
                "badge_sub": "15% Upfront Subsidy",
                "link": "https://www.msme.gov.in/",
            },
        ],
    },
    {
        "category": "Digital & Market",
        "color": "#0D9488",
        "schemes": [
            {
                "name": "ONDC Onboarding – Open Network for Digital Commerce",
                "ministry": "DPIIT (Ministry of Commerce & Industry)",
                "tag": "E-Commerce",
                "color": "#0D9488",
                "brief": "Democratized digital commerce platform connecting local kirana and retailers directly to national buyer applications.",
                "eligibility": "Any registered retailer, local shopkeeper, or seller entity",
                "loan_amount": "Zero fee network access with subsidized cataloging incentives",
                "application": "Directly through registered ONDC seller network participants",
                "badge_icon": "🌐",
                "badge_title": "ONDC Digital Reach",
                "badge_sub": "Sell to All India",
                "link": "https://ondc.org/",
            },
            {
                "name": "GeM – Government e-Marketplace (Sahay Portal)",
                "ministry": "Ministry of Commerce & Industry",
                "tag": "Govt Procurement",
                "color": "#0D9488",
                "brief": "Direct procurement access for micro-retailers and sellers to supply goods and services directly to Government departments.",
                "eligibility": "All micro and small enterprises holding valid Udyam registration",
                "loan_amount": "Direct purchase access (no tender up to ₹25,000) & cashflow financing",
                "application": "Online vendor onboarding at gem.gov.in",
                "badge_icon": "📑",
                "badge_title": "Government Buyer",
                "badge_sub": "Direct Public Procurement",
                "link": "https://gem.gov.in/",
            },
        ],
    },
    {
        "category": "Insurance & Social",
        "color": "#059669",
        "schemes": [
            {
                "name": "PMSBY – Pradhan Mantri Suraksha Bima Yojana",
                "ministry": "Ministry of Finance (DFS)",
                "tag": "Accident Cover",
                "color": "#059669",
                "brief": "Extremely affordable annual accidental death and disability cover of ₹2 lakh for all micro-business owners.",
                "eligibility": "Bank / Post Office account holders aged 18 to 70 years",
                "loan_amount": "₹2 Lakh accident death/disability cover at just ₹20/year premium",
                "application": "Auto-debit mandate through any commercial/Gramin bank",
                "badge_icon": "🛡️",
                "badge_title": "Accident Protection",
                "badge_sub": "₹2 Lakh Cover @ ₹20/yr",
                "link": "https://www.jansuraksha.gov.in/",
            },
            {
                "name": "PMJJBY – Pradhan Mantri Jeevan Jyoti Bima Yojana",
                "ministry": "Ministry of Finance (DFS)",
                "tag": "Life Insurance",
                "color": "#059669",
                "brief": "Comprehensive life insurance coverage of ₹2 lakh in case of death due to any reason for breadwinners.",
                "eligibility": "Individuals aged 18 to 50 having an active savings bank account",
                "loan_amount": "₹2 Lakh life risk cover at premium of ₹436/year",
                "application": "Enrollment through bank branch or netbanking portal",
                "badge_icon": "❤️",
                "badge_title": "Life Security",
                "badge_sub": "₹2 Lakh Cover @ ₹436/yr",
                "link": "https://www.jansuraksha.gov.in/",
            },
            {
                "name": "PM-SYM – Pradhan Mantri Shram Yogi Maan-dhan",
                "ministry": "Ministry of Labour & Employment",
                "tag": "Pension Scheme",
                "color": "#059669",
                "brief": "Guaranteed monthly pension of ₹3,000 after age 60 with 50% matching monthly contribution by Central Government.",
                "eligibility": "Unorganized retail workers, shop assistants, street vendors aged 18-40",
                "loan_amount": "Assured ₹3,000/month lifelong pension post 60 years",
                "application": "Online via maandhan.in or nearest CSC centre",
                "badge_icon": "👴",
                "badge_title": "Old Age Pension",
                "badge_sub": "₹3,000 Monthly Pension",
                "link": "https://maandhan.in/",
            },
        ],
    },
    {
        "category": "Training & Skilling",
        "color": "#9333EA",
        "schemes": [
            {
                "name": "PMKVY – Pradhan Mantri Kaushal Vikas Yojana 4.0",
                "ministry": "Ministry of Skill Development & Entrepreneurship",
                "tag": "Skilling",
                "color": "#9333EA",
                "brief": "Free industry-aligned skill development courses, assessment, NSQF certification, and retail apprenticeship linkages.",
                "eligibility": "Any Indian youth or micro-business owner looking to upgrade skills",
                "loan_amount": "100% government-sponsored certification & wage support",
                "application": "Online via pmkvyofficial.org or nearest PMKK center",
                "badge_icon": "🎓",
                "badge_title": "Skill Certification",
                "badge_sub": "NSQF Aligned Training",
                "link": "https://www.pmkvyofficial.org/",
            },
            {
                "name": "SAMARTH Scheme",
                "ministry": "Ministry of Textiles",
                "tag": "Sector Skilling",
                "color": "#9333EA",
                "brief": "Accredited entry-level skill training and upskilling in handloom, apparel manufacturing, weaving, and textile retail crafts.",
                "eligibility": "Prospective or existing workers and micro-entrepreneurs in textiles",
                "loan_amount": "Fully subsidized training with stipend and certified placement",
                "application": "Through designated training partners or samarth-textiles.gov.in",
                "badge_icon": "🧵",
                "badge_title": "Textile Crafts",
                "badge_sub": "Accredited Training",
                "link": "https://samarth-textiles.gov.in/",
            },
            {
                "name": "EDP – Entrepreneurship Development Programmes",
                "ministry": "Ministry of MSME / NIESBUD",
                "tag": "Business Training",
                "color": "#9333EA",
                "brief": "Comprehensive hands-on training in business plan preparation, financial management, accounting, statutory compliance, and marketing.",
                "eligibility": "Aspiring entrepreneurs and existing micro-retailers",
                "loan_amount": "Subsidized training fee structure with expert mentorship",
                "application": "Through NIESBUD / MSME development institutes",
                "badge_icon": "📊",
                "badge_title": "Business Acumen",
                "badge_sub": "Management Training",
                "link": "https://www.niesbud.nic.in/",
            },
        ],
    },
]

# Create 3 main tabs exactly matching Reference
tab_schemes, tab_calculator, tab_promotions = st.tabs([
    t("🏛️ Government Schemes Directory", lang),
    t("🧮 SIH Scheme & Loan Calculator", lang),
    t("📢 Store Promotional Schemes", lang)
])

# ==============================================================================
# TAB 1: GOVERNMENT SCHEMES DIRECTORY
# ==============================================================================
with tab_schemes:
    # Official Government Schemes Catalogue Banner Card
    cat_banner = (
        '<div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:12px; padding:1.2rem 1.6rem; margin-bottom:1.25rem; display:flex; align-items:center; justify-content:space-between; gap:20px; box-shadow:0 2px 6px rgba(37,99,235,0.05);">'
        '<div style="display:flex; align-items:center; gap:18px;">'
        '<div style="font-size:2.8rem; color:#1E3A8A; line-height:1;">🏛️</div>'
        '<div>'
        '<h3 style="margin:0 0 4px 0; color:#1E3A8A !important; font-size:1.25rem; font-weight:700; font-family:\'Playfair Display\', serif;">Official Government Schemes Catalogue</h3>'
        '<p style="margin:0; font-size:0.88rem; color:#2563EB; line-height:1.45;">'
        'Explore verified Central and State Government schemes supporting rural and semi-urban micro-entrepreneurs.<br>'
        'Direct application links trace to official government portals (.gov.in / .org.in).'
        '</p>'
        '</div>'
        '</div>'
        '<div style="text-align:right; border-left:1px dashed #93C5FD; padding-left:18px; min-width:140px;">'
        '<div style="font-size:1.8rem; line-height:1;">🇮🇳</div>'
        '<div style="font-size:0.75rem; font-weight:700; color:#1E40AF; margin-top:4px;">Sarkari Yojana<br>Se Samriddh Bharat</div>'
        '</div>'
        '</div>'
    )
    render_html(cat_banner)

    # 5 KPI Summary Cards in a row matching Reference Screenshot
    kpi_strip = (
        '<div style="display:grid; grid-template-columns:repeat(5, 1fr); gap:12px; margin-bottom:1.5rem;">'
        '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; overflow:hidden; display:flex; align-items:stretch; box-shadow:0 2px 6px rgba(0,0,0,0.03);">'
        '<div style="background:#2563EB; width:52px; display:flex; align-items:center; justify-content:center; color:white; font-size:1.45rem; flex-shrink:0;">🪙</div>'
        '<div style="padding:0.6rem 0.8rem; flex:1; display:flex; flex-direction:column; justify-content:center;">'
        '<div style="font-size:1.5rem; font-weight:800; color:#2563EB; line-height:1;">4</div>'
        '<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.04em; color:#1E293B; margin-top:3px; text-transform:uppercase;">CREDIT & FINANCE &rarr;</div>'
        '</div>'
        '</div>'
        '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; overflow:hidden; display:flex; align-items:stretch; box-shadow:0 2px 6px rgba(0,0,0,0.03);">'
        '<div style="background:#EA580C; width:52px; display:flex; align-items:center; justify-content:center; color:white; font-size:1.45rem; flex-shrink:0;">🤝</div>'
        '<div style="padding:0.6rem 0.8rem; flex:1; display:flex; flex-direction:column; justify-content:center;">'
        '<div style="font-size:1.5rem; font-weight:800; color:#EA580C; line-height:1;">3</div>'
        '<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.04em; color:#1E293B; margin-top:3px; text-transform:uppercase;">SUBSIDIES & CAPITAL &rarr;</div>'
        '</div>'
        '</div>'
        '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; overflow:hidden; display:flex; align-items:stretch; box-shadow:0 2px 6px rgba(0,0,0,0.03);">'
        '<div style="background:#0D9488; width:52px; display:flex; align-items:center; justify-content:center; color:white; font-size:1.45rem; flex-shrink:0;">📊</div>'
        '<div style="padding:0.6rem 0.8rem; flex:1; display:flex; flex-direction:column; justify-content:center;">'
        '<div style="font-size:1.5rem; font-weight:800; color:#0D9488; line-height:1;">2</div>'
        '<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.04em; color:#1E293B; margin-top:3px; text-transform:uppercase;">DIGITAL & MARKET &rarr;</div>'
        '</div>'
        '</div>'
        '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; overflow:hidden; display:flex; align-items:stretch; box-shadow:0 2px 6px rgba(0,0,0,0.03);">'
        '<div style="background:#059669; width:52px; display:flex; align-items:center; justify-content:center; color:white; font-size:1.45rem; flex-shrink:0;">🛡️</div>'
        '<div style="padding:0.6rem 0.8rem; flex:1; display:flex; flex-direction:column; justify-content:center;">'
        '<div style="font-size:1.5rem; font-weight:800; color:#059669; line-height:1;">3</div>'
        '<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.04em; color:#1E293B; margin-top:3px; text-transform:uppercase;">INSURANCE & SOCIAL &rarr;</div>'
        '</div>'
        '</div>'
        '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; overflow:hidden; display:flex; align-items:stretch; box-shadow:0 2px 6px rgba(0,0,0,0.03);">'
        '<div style="background:#9333EA; width:52px; display:flex; align-items:center; justify-content:center; color:white; font-size:1.45rem; flex-shrink:0;">👥</div>'
        '<div style="padding:0.6rem 0.8rem; flex:1; display:flex; flex-direction:column; justify-content:center;">'
        '<div style="font-size:1.5rem; font-weight:800; color:#9333EA; line-height:1;">3</div>'
        '<div style="font-size:0.68rem; font-weight:700; letter-spacing:0.04em; color:#1E293B; margin-top:3px; text-transform:uppercase;">TRAINING & SKILLING &rarr;</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    render_html(kpi_strip)

    # Search and Category filter row
    col_search, col_filter = st.columns([2.4, 1.2])
    with col_search:
        search_kw = st.text_input(
            t("🔍 Search schemes by name, keyword, ministry, or benefit", lang),
            placeholder=t("e.g. MUDRA, subsidy, collateral, training...", lang),
            key="schemes_search_input"
        ).strip().lower()
    with col_filter:
        cat_choices = ["All Categories"] + [c["category"] for c in OFFICIAL_SCHEMES]
        selected_cat = st.selectbox(
            t("🔰 Filter by Category", lang),
            cat_choices,
            format_func=lambda x: t(x, lang),
            key="schemes_cat_filter"
        )

    def filter_scheme(s, kw):
        if not kw:
            return True
        check_text = " ".join([
            s.get("name", ""), s.get("ministry", ""), s.get("tag", ""),
            s.get("brief", ""), s.get("eligibility", ""), s.get("loan_amount", ""), s.get("application", "")
        ]).lower()
        return kw in check_text

    # Render Schemes Categories and Cards matching Reference Style
    total_rendered = 0
    for cat_obj in OFFICIAL_SCHEMES:
        category_name = cat_obj["category"]
        category_accent = cat_obj.get("color", "#2563EB")
        if selected_cat != "All Categories" and category_name != selected_cat:
            continue

        matched_items = [s for s in cat_obj["schemes"] if filter_scheme(s, search_kw)]
        if not matched_items:
            continue

        # Section header row with count badge
        sec_header = (
            f'<div style="display:flex; align-items:center; justify-content:space-between; margin:1.6rem 0 0.85rem 0;">'
            f'<div style="display:flex; align-items:center; gap:10px;">'
            f'<h3 style="margin:0; font-size:1.25rem; font-weight:700; color:#1E293B; font-family:\'Playfair Display\', serif;">{category_name}</h3>'
            f'<span style="background:#FAF5EE; color:#64748B; font-size:0.75rem; font-weight:700; padding:2px 10px; border-radius:12px; border:1px solid #E2E8F0;">'
            f'{len(matched_items)} scheme{"s" if len(matched_items) != 1 else ""}'
            f'</span>'
            f'</div>'
            f'<div style="font-size:0.82rem; font-weight:700; color:{category_accent}; cursor:pointer;">View All &rarr;</div>'
            f'</div>'
        )
        render_html(sec_header)

        cols = st.columns(2)
        for idx, scheme in enumerate(matched_items):
            with cols[idx % 2]:
                s_name = html.escape(scheme.get("name", ""))
                s_min = html.escape(scheme.get("ministry", ""))
                s_tag = html.escape(scheme.get("tag", ""))
                s_brief = html.escape(scheme.get("brief", ""))
                s_elig = html.escape(scheme.get("eligibility", ""))
                s_loan = html.escape(scheme.get("loan_amount", ""))
                s_app = html.escape(scheme.get("application", ""))
                s_link = html.escape(scheme.get("link", "#"))
                s_color = scheme.get("color", category_accent)
                b_icon = scheme.get("badge_icon", "🏛️")
                b_title = html.escape(scheme.get("badge_title", ""))
                b_sub = html.escape(scheme.get("badge_sub", ""))

                # Clean professional card with subtle category accent (NO dominant vertical bar)
                card_html = (
                    f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3.5px solid {s_color}; border-radius:12px; padding:1.3rem 1.4rem; margin-bottom:1.15rem; box-shadow:0 2px 8px rgba(30,41,59,0.04); display:flex; flex-direction:column; justify-content:space-between; min-height:285px;">'
                    f'<div>'
                    f'<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:0.35rem;">'
                    f'<div style="font-size:1.02rem; font-weight:700; color:#1E293B; line-height:1.35; font-family:\'Playfair Display\', serif;">{s_name}</div>'
                    f'<span style="background:{s_color}14; color:{s_color}; font-size:0.72rem; font-weight:700; padding:2px 10px; border-radius:14px; white-space:nowrap; border:1px solid {s_color}30;">{s_tag}</span>'
                    f'</div>'
                    f'<div style="font-size:0.78rem; color:#0D9488; font-weight:600; margin-bottom:0.7rem;">🏛️ {s_min}</div>'
                    f'<p style="font-size:0.84rem; color:#475569; margin:0 0 0.85rem 0; line-height:1.45;">{s_brief}</p>'
                    f'<div style="display:flex; gap:14px; align-items:center; justify-content:space-between; margin-bottom:1rem;">'
                    f'<div style="flex:1;">'
                    f'<div style="font-size:0.8rem; color:#334155; margin-bottom:4px; line-height:1.4;"><strong>👥 Eligibility:</strong> {s_elig}</div>'
                    f'<div style="font-size:0.8rem; color:#334155; margin-bottom:4px; line-height:1.4;"><strong>₹ Loan Amount:</strong> {s_loan}</div>'
                    f'<div style="font-size:0.8rem; color:#334155; line-height:1.4;"><strong>📄 Application:</strong> {s_app}</div>'
                    f'</div>'
                    f'<div style="width:110px; background:#FAF5EE; border:1px solid #E2E8F0; border-radius:10px; padding:0.6rem 0.4rem; text-align:center; flex-shrink:0;">'
                    f'<div style="font-size:1.6rem; line-height:1.1;">{b_icon}</div>'
                    f'<div style="font-size:0.68rem; font-weight:700; color:#1E293B; margin-top:3px; line-height:1.2;">{b_title}</div>'
                    f'<div style="font-size:0.62rem; color:{s_color}; font-weight:600; margin-top:1px;">{b_sub}</div>'
                    f'</div>'
                    f'</div>'
                    f'</div>'
                    f'<div>'
                    f'<a href="{s_link}" target="_blank" style="display:inline-block; background-color:{s_color}; color:#FFFFFF; font-size:0.82rem; font-weight:700; padding:8px 18px; border-radius:8px; text-decoration:none; box-shadow:0 2px 4px rgba(0,0,0,0.08); transition:opacity 0.15s ease;">'
                    f'Apply on Official Portal &nearr;'
                    f'</a>'
                    f'</div>'
                    f'</div>'
                )
                render_html(card_html)
                total_rendered += 1

    if total_rendered == 0:
        st.info("No government schemes matched your search criteria. Please try another keyword or choose 'All Categories'.")

    # Bottom guidance notice
    guide_notice = (
        '<div style="background:#FAF5EE; border:1px solid #E2E8F0; border-radius:10px; padding:0.85rem 1.25rem; margin-top:1.5rem; display:flex; gap:12px; align-items:center;">'
        '<span style="font-size:1.3rem;">ℹ️</span>'
        '<div style="font-size:0.8rem; color:#64748B; line-height:1.5;">'
        '<strong>Official Scheme Sourcing:</strong> All scheme parameters, credit ceilings, and interest subsidies correspond directly to official Gazetted guidelines published by the Ministry of MSME, Ministry of Finance, and SIDBI.'
        '</div>'
        '</div>'
    )
    render_html(guide_notice)


# ==============================================================================
# TAB 2: SIH SCHEME & LOAN CALCULATOR
# ==============================================================================
with tab_calculator:
    calc_intro = (
        '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:1.25rem 1.5rem; margin-bottom:1.5rem; box-shadow:0 2px 8px rgba(30, 41, 59, 0.04);">'
        '<h3 style="margin:0 0 4px 0; color:#1E293B !important; font-size:1.2rem; font-weight:700; font-family:\'Playfair Display\', serif;">SIH 26091 Scheme Auto-Selector & Loan Calculator</h3>'
        '<p style="font-size:0.86rem; color:#64748B; margin:0; line-height:1.5;">'
        'Under the SIH 26091 Master Plan Pipeline, available margin capital serves as 10% equity, with 90% financed through institutional loan schemes. '
        'The system deterministically routes to the applicable scheme based on total project cost.'
        '</p>'
        '</div>'
    )
    render_html(calc_intro)

    col_inp, _ = st.columns([1, 1])
    with col_inp:
        available_margin = st.number_input(
            "Enter Available Margin Capital (₹)",
            min_value=1000.0,
            max_value=2000000.0,
            value=50000.0,
            step=5000.0,
            help="Your own capital contribution. Represents 10% of total project cost under the SIH framework."
        )

    # Calculate financial parameters using sih_finance rules
    capacity = financing_capacity(available_margin)
    proj_cost = capacity["maximum_project_cost"]
    max_loan = capacity["maximum_loan"]
    scheme_info = select_scheme(proj_cost)

    # Metric Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_html(f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:1rem; text-align:center;"><div style="font-size:0.75rem; color:#0D9488; font-weight:700; text-transform:uppercase;">Margin Capital (10%)</div><div style="font-size:1.4rem; font-weight:700; color:#1E293B; margin-top:4px;">{format_currency(available_margin)}</div></div>')
    with m2:
        render_html(f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:1rem; text-align:center;"><div style="font-size:0.75rem; color:#0D9488; font-weight:700; text-transform:uppercase;">Total Project Cost</div><div style="font-size:1.4rem; font-weight:700; color:#2563EB; margin-top:4px;">{format_currency(proj_cost)}</div></div>')
    with m3:
        render_html(f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:1rem; text-align:center;"><div style="font-size:0.75rem; color:#0D9488; font-weight:700; text-transform:uppercase;">Eligible Loan (90%)</div><div style="font-size:1.4rem; font-weight:700; color:#1E293B; margin-top:4px;">{format_currency(max_loan)}</div></div>')
    with m4:
        render_html(f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:1rem; text-align:center;"><div style="font-size:0.75rem; color:#0D9488; font-weight:700; text-transform:uppercase;">Selected Scheme</div><div style="font-size:1.2rem; font-weight:700; color:#059669; margin-top:6px;">{scheme_info.get("name", "N/A")}</div></div>')

    render_html("<div style='height:16px'></div>")

    if not scheme_info.get("supported", False):
        st.error(f"⚠️ {scheme_info.get('reason', 'Selected project cost exceeds standard scheme parameters.')}")
    else:
        scheme_name = scheme_info["name"]
        interest_rate = scheme_info["interest_rate"]
        tenure_years = scheme_info["tenure_years"]
        tenure_months = tenure_years * 12
        moratorium_months = scheme_info["moratorium_months"]

        repayment_months = tenure_months - moratorium_months
        monthly_emi = calculate_emi(max_loan, interest_rate, repayment_months)
        schedule_res = build_quarterly_schedule(max_loan, interest_rate, tenure_months, moratorium_months)
        total_interest = schedule_res["total_interest"]
        total_repayment = schedule_res["total_repayment"]
        moratorium_monthly_interest = (max_loan * (interest_rate / 100.0)) / 12.0

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            desc_text = 'Low-interest scheme tailored for rural micro-retailers and startups (Project Cost ≤ ₹1.40 Lakh).' if scheme_name == 'Micro Finance' else 'Structured long-tenure institutional financing for expanding rural businesses (₹1.40 Lakh < Project Cost ≤ ₹50.00 Lakh).'
            render_html(
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3.5px solid #2563EB; border-radius:10px; padding:1.2rem; height:100%; box-shadow:0 2px 6px rgba(0,0,0,0.03);">'
                f'<div style="font-size:0.75rem; font-weight:700; color:#0D9488; text-transform:uppercase;">Policy Routing Details</div>'
                f'<h3 style="color:#1E293B !important; margin:0.3rem 0; font-size:1.35rem; font-family:\'Playfair Display\', serif;">{scheme_name}</h3>'
                f'<p style="font-size:0.85rem; color:#475569; margin-bottom:0.75rem;">{desc_text}</p>'
                f'<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.85rem; color:#1E293B;">'
                f'<div><strong>Annual Interest:</strong> {interest_rate}% p.a.</div>'
                f'<div><strong>Tenure:</strong> {tenure_years} Years ({tenure_months} Mo.)</div>'
                f'<div><strong>Moratorium:</strong> {moratorium_months} Months</div>'
                f'<div><strong>Repayment Phase:</strong> {repayment_months} Months</div>'
                f'</div>'
                f'</div>'
            )

        with col_s2:
            render_html(
                f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3.5px solid #059669; border-radius:10px; padding:1.2rem; height:100%; box-shadow:0 2px 6px rgba(0,0,0,0.03);">'
                f'<div style="font-size:0.75rem; font-weight:700; color:#0D9488; text-transform:uppercase;">Repayment Obligations</div>'
                f'<div style="display:flex; justify-content:space-between; margin-top:0.5rem; border-bottom:1px solid #F1F5F9; padding-bottom:6px;">'
                f'<span style="color:#64748B; font-size:0.86rem;">Monthly EMI (Post-Moratorium):</span>'
                f'<strong style="color:#1E293B; font-size:0.98rem;">{format_currency(monthly_emi)}</strong>'
                f'</div>'
                f'<div style="display:flex; justify-content:space-between; margin-top:0.5rem; border-bottom:1px solid #F1F5F9; padding-bottom:6px;">'
                f'<span style="color:#64748B; font-size:0.86rem;">Moratorium Interest (Monthly):</span>'
                f'<strong style="color:#EA580C; font-size:0.95rem;">{format_currency(moratorium_monthly_interest)}</strong>'
                f'</div>'
                f'<div style="display:flex; justify-content:space-between; margin-top:0.5rem; border-bottom:1px solid #F1F5F9; padding-bottom:6px;">'
                f'<span style="color:#64748B; font-size:0.86rem;">Total Interest Payable:</span>'
                f'<strong style="color:#2563EB; font-size:0.95rem;">{format_currency(total_interest)}</strong>'
                f'</div>'
                f'<div style="display:flex; justify-content:space-between; margin-top:0.5rem; padding-top:4px;">'
                f'<span style="color:#1E293B; font-size:0.86rem; font-weight:700;">Total Repayment Obligation:</span>'
                f'<strong style="color:#059669; font-size:1.02rem;">{format_currency(total_repayment)}</strong>'
                f'</div>'
                f'</div>'
            )

        render_html("<div style='height:20px'></div>")
        st.markdown("#### 📅 Quarterly Amortization Schedule")
        schedule_df = schedule_res.get("schedule", pd.DataFrame())

        if not schedule_df.empty:
            display_df = schedule_df.copy()
            curr_cols = ["Opening Principal", "Interest", "Principal Repaid", "Total Payment", "Closing Principal"]
            for col in curr_cols:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: format_currency(x))
            
            st.dataframe(display_df, width="stretch", hide_index=True)
            csv_bytes = schedule_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Amortization Schedule (CSV)",
                data=csv_bytes,
                file_name=f"SIH_Amortization_Schedule_{scheme_name.replace(' ', '_')}.csv",
                mime="text/csv",
            )


# ==============================================================================
# TAB 3: STORE PROMOTIONAL SCHEMES
# ==============================================================================
with tab_promotions:
    promo_intro = (
        '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:1.25rem 1.5rem; margin-bottom:1.5rem; box-shadow:0 2px 8px rgba(30, 41, 59, 0.04);">'
        '<h3 style="margin:0 0 4px 0; color:#1E293B !important; font-size:1.2rem; font-weight:700; font-family:\'Playfair Display\', serif;">Store-Specific Promotional Campaigns</h3>'
        '<p style="font-size:0.86rem; color:#64748B; margin:0; line-height:1.5;">'
        'Internal promotional recommendations generated from your store sales records, transaction frequency, and regional customer purchasing patterns.'
        '</p>'
        '</div>'
    )
    render_html(promo_intro)

    if not promotions:
        st.info("No store promotional schemes currently generated. Ensure dataset is active.")
    else:
        data_driven = [p for p in promotions if p.get('Type') == 'DATA-DRIVEN']
        market_based = [p for p in promotions if p.get('Type') == 'MARKET-BASED']

        cp1, cp2 = st.columns(2)
        with cp1:
            render_html("<h4 style='color:#0D9488; margin:0 0 10px 0;'>Data-Driven Recommendations</h4>")
            if not data_driven:
                st.info("No data-driven recommendations available.")
            for p in data_driven:
                card_p = (
                    f'<div style="background:#FFFFFF; padding:15px; border-radius:10px; border:1px solid #E2E8F0; border-top:3px solid #0D9488; margin-bottom:12px; box-shadow:0 2px 4px rgba(0,0,0,0.03);">'
                    f'<h5 style="margin-top:0; color:#1E293B; font-size:1rem; font-weight:700;">{html.escape(p.get("Scheme Name", ""))}</h5>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Target Customers:</strong> {html.escape(str(p.get("Target Customers", "")))}</p>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Target Products:</strong> {html.escape(str(p.get("Target Products", "")))}</p>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Reason:</strong> {html.escape(str(p.get("Reason", "")))}</p>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Period:</strong> {html.escape(str(p.get("Recommended Period", "")))}</p>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Objective:</strong> {html.escape(str(p.get("Expected Objective", "")))}</p>'
                    f'<span style="background:#FAF5EE; color:#0D9488; border:1px solid #E2E8F0; padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">Priority: {html.escape(str(p.get("Priority", "")))}</span>'
                    f'</div>'
                )
                render_html(card_p)

        with cp2:
            render_html("<h4 style='color:#2563EB; margin:0 0 10px 0;'>Market-Based Recommendations</h4>")
            if not market_based:
                st.info("No market-based recommendations available.")
            for p in market_based:
                card_m = (
                    f'<div style="background:#FFFFFF; padding:15px; border-radius:10px; border:1px solid #E2E8F0; border-top:3px solid #2563EB; margin-bottom:12px; box-shadow:0 2px 4px rgba(0,0,0,0.03);">'
                    f'<h5 style="margin-top:0; color:#1E293B; font-size:1rem; font-weight:700;">{html.escape(p.get("Scheme Name", ""))}</h5>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Target Customers:</strong> {html.escape(str(p.get("Target Customers", "")))}</p>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Target Products:</strong> {html.escape(str(p.get("Target Products", "")))}</p>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Reason:</strong> {html.escape(str(p.get("Reason", "")))}</p>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Period:</strong> {html.escape(str(p.get("Recommended Period", "")))}</p>'
                    f'<p style="margin:4px 0; font-size:0.84rem; color:#475569;"><strong>Objective:</strong> {html.escape(str(p.get("Expected Objective", "")))}</p>'
                    f'<span style="background:#FAF5EE; color:#2563EB; border:1px solid #E2E8F0; padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">Priority: {html.escape(str(p.get("Priority", "")))}</span>'
                    f'</div>'
                )
                render_html(card_m)