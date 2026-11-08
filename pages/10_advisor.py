import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from components.header import render_header
from utils.formatting import format_currency
from utils.theme import apply_theme, render_html
from utils.translations import t, get_current_language, normalize_lang, set_current_language
from ai_advisor import SUPPORTED_LANGUAGES, generate_business_advice, identify_query_language
from utils.voice_input import transcribe_audio, render_voice_input_widget, render_speech_synthesis_player

st.set_page_config(page_title="BizMetrics - AI Advisor", layout="wide")
try:
    from utils.session_manager import ensure_authenticated_session
    if not ensure_authenticated_session(required_role="owner"):
        st.stop()
except Exception:
    if not st.session_state.get("owner_authenticated", False):
        st.switch_page("app.py")
apply_theme()
render_sidebar()
render_header("AI Advisor", "Context-Aware Business Intelligence Assistant grounded in your operational ledgers.")

if "pipeline_result" not in st.session_state or "raw_data" not in st.session_state:
    try:
        from utils.data_loader import refresh_application_data
        refresh_application_data()
    except Exception:
        pass

if "pipeline_result" not in st.session_state:
    st.error("BizMetrics dataset could not be found.")
    st.stop()

result = st.session_state["pipeline_result"]
f = result.get('financial', {})
r = result.get('receivables', {})
i = result.get('inventory', {})
cust_data = result.get('customers', {})

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

current_sys_lang = get_current_language()
if "advisor_language" not in st.session_state:
    st.session_state["advisor_language"] = current_sys_lang
if "advisor_response_style" not in st.session_state:
    st.session_state["advisor_response_style"] = "Standard"

# -------------------------------------------------------------
# 1. CONTROLS: LANGUAGE & RESPONSE STYLE
# -------------------------------------------------------------
ctrl_c1, ctrl_c2, _ = st.columns([1.5, 1.5, 2])
with ctrl_c1:
    languages = ["English", "हिंदी", "Hinglish"] + [l for l in list(SUPPORTED_LANGUAGES) if l not in ["English", "Hinglish", "Hindi (हिंदी)"]]
    current_adv_lang = current_sys_lang
    idx = languages.index(current_adv_lang) if current_adv_lang in languages else 0
    selected_lang = st.selectbox(
        t("Response Language / उत्तर की भाषा", current_sys_lang),
        languages,
        index=idx,
        key="advisor_lang_select"
    )
    if selected_lang != current_sys_lang:
        set_current_language(selected_lang)
        st.rerun()

with ctrl_c2:
    st.session_state["advisor_response_style"] = st.selectbox(
        "Advisory Style / सलाह का प्रकार",
        ["Standard", "Simple", "Executive Brief"],
        index=["Standard", "Simple", "Executive Brief"].index(st.session_state["advisor_response_style"]) if st.session_state["advisor_response_style"] in ["Standard", "Simple", "Executive Brief"] else 0,
        key="advisor_style_select"
    )

# -------------------------------------------------------------
# 2. EXECUTIVE SUMMARY & LIVE DATA BANNER
# -------------------------------------------------------------
tot_rev = f.get('total_revenue', 0)
net_prof = f.get('net_profit', 0)
margin_pct = f.get('profit_margin', 0)
out_rec = r.get('total_outstanding', 0)
reorder_len = len(i.get('reorder_items', []))

briefing_title = t("Smart Business Alerts & AI Insights", current_sys_lang)
render_html(
    f"""
    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 5px solid #7C3AED; border-radius: 12px; padding: 1.15rem 1.4rem; margin-bottom: 1.25rem; box-shadow: 0 2px 6px rgba(30,41,59,0.03);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong style="color: #1E293B; font-size: 1.05rem; font-family: 'Playfair Display', serif;">🤖 {briefing_title} (Real-Time Pipeline)</strong>
            <span style="background: #F3E8FF; color: #7C3AED; font-size: 0.75rem; font-weight: 700; padding: 2px 10px; border-radius: 12px; border: 1px solid #E9D5FF;">Grounded in Live Business Records</span>
        </div>
        <p style="color: #475569; font-size: 0.88rem; line-height: 1.5; margin: 0;">
            {t('Total Revenue', current_sys_lang)}: <strong>{format_currency(tot_rev)}</strong> | 
            {t('Net Profit', current_sys_lang)}: <strong>{margin_pct:.1f}% ({format_currency(net_prof)})</strong> | 
            {t('Outstanding Payments', current_sys_lang)}: <strong>{format_currency(out_rec)}</strong> | 
            <strong>{reorder_len} SKUs</strong> {t('Low Stock Alert', current_sys_lang)}.
        </p>
    </div>
    """
)

# -------------------------------------------------------------
# 3. INTERACTIVE CHAT & SUGGESTED PROMPTS
# -------------------------------------------------------------
col1, col2 = st.columns([2.1, 1.0])

with col1:
    st.markdown(f"### 💬 {t('Ask AI Advisor', current_sys_lang)}")
    st.caption("Click a common business question or type your question below in English, हिंदी, or Hinglish:")

    # 6 Quick Prompts localized to current language
    q_col1, q_col2, q_col3 = st.columns(3)
    if current_sys_lang == "हिंदी":
        btn1_lbl = "📉 लाभ क्यों बदला?"
        btn2_lbl = "📦 कौन सा स्टॉक मंगाएं?"
        btn3_lbl = "👥 कौन से ग्राहक जा सकते हैं?"
        btn4_lbl = "💸 सबसे बड़े खर्चे क्या हैं?"
        btn5_lbl = "🏆 सबसे ज्यादा मुनाफा किसमें?"
        btn6_lbl = "💧 नकदी प्रवाह कैसे सुधारें?"
    elif current_sys_lang == "Hinglish":
        btn1_lbl = "📉 Sales / Munafa kyu kam hua?"
        btn2_lbl = "📦 Kaunsa stock dobara mangwana hai?"
        btn3_lbl = "👥 Kaunse customers churn ho sakte hain?"
        btn4_lbl = "💸 Dukaan ke sabse bade kharche?"
        btn5_lbl = "🏆 Most profitable products kaunse hain?"
        btn6_lbl = "💧 Cash flow aur baaki payment?"
    else:
        btn1_lbl = "📉 Why did profit change?"
        btn2_lbl = "📦 Which products to reorder?"
        btn3_lbl = "👥 Which customers at churn risk?"
        btn4_lbl = "💸 What are top expenses?"
        btn5_lbl = "🏆 Most profitable products?"
        btn6_lbl = "💧 How to improve cash flow?"

    p1 = q_col1.button(btn1_lbl, use_container_width=True, key="adv_quick_btn_1")
    p2 = q_col2.button(btn2_lbl, use_container_width=True, key="adv_quick_btn_2")
    p3 = q_col3.button(btn3_lbl, use_container_width=True, key="adv_quick_btn_3")

    q_col4, q_col5, q_col6 = st.columns(3)
    p4 = q_col4.button(btn4_lbl, use_container_width=True, key="adv_quick_btn_4")
    p5 = q_col5.button(btn5_lbl, use_container_width=True, key="adv_quick_btn_5")
    p6 = q_col6.button(btn6_lbl, use_container_width=True, key="adv_quick_btn_6")

    default_prompt = ""
    if p1:
        default_prompt = "Why did my business profit change and how can I improve margins?" if current_sys_lang == "English" else ("मेरा व्यावसायिक लाभ क्यों बदला और मैं मार्जिन कैसे सुधार सकता हूँ?" if current_sys_lang == "हिंदी" else "Meri dukaan ka profit pichle mahine se kam kyu hua aur munafa kaise badhayein?")
    elif p2:
        default_prompt = "Which products should I reorder immediately and what are the reorder quantities?" if current_sys_lang == "English" else ("मुझे कौन से उत्पाद तुरंत पुनः ऑर्डर करने चाहिए?" if current_sys_lang == "हिंदी" else "Kaunsa stock dobara mangwana chahiye taaki dukaan par shortage na ho?")
    elif p3:
        default_prompt = "Which customers are at risk of churning or stopping purchases?" if current_sys_lang == "English" else ("कौन से ग्राहक खरीदारी बंद करने के जोखिम में हैं?" if current_sys_lang == "हिंदी" else "Kaunse customers dukaan par aana band kar sakte hain aur unhe kaise rokein?")
    elif p4:
        default_prompt = "What are my highest business operating expenses and where can I reduce costs?" if current_sys_lang == "English" else ("मेरे सबसे बड़े परिचालन खर्च क्या हैं?" if current_sys_lang == "हिंदी" else "Dukaan ke sabse bade kharche kya hain aur unhe kaise kam karein?")
    elif p5:
        default_prompt = "Which products generate the most gross profit and highest margins?" if current_sys_lang == "English" else ("कौन से उत्पाद सबसे अधिक लाभ और मार्जिन उत्पन्न करते हैं?" if current_sys_lang == "हिंदी" else "Sabse jyada gross profit aur margin dene wale products kaunse hain?")
    elif p6:
        default_prompt = "How can I improve cash flow over the next 30 days?" if current_sys_lang == "English" else ("अगले 30 दिनों में नकदी प्रवाह कैसे सुधारें?" if current_sys_lang == "हिंदी" else "Mere kitne payment pending hain aur agle 30 din me cash flow kaise behtar karein?")

    render_voice_input_widget(language=current_sys_lang, key="advisor_voice_mic")

    with st.form(key="advisor_form"):
        ph_text = "e.g. Which customers have overdue invoices?" if current_sys_lang == "English" else ("उदा. किन ग्राहकों का बकाया भुगतान लंबित है?" if current_sys_lang == "हिंदी" else "e.g. Mere kitne payment pending hain ya kaunsa stock mangwana hai?")
        user_input = st.text_input(
            t("Ask a business question...", current_sys_lang),
            value=default_prompt or st.session_state.get("voice_transcription", ""),
            placeholder=ph_text
        )
        submit_button = st.form_submit_button(label=t("Ask Advisor", current_sys_lang), type="primary")

    if submit_button and user_input:
        with st.spinner("Analyzing operational ledgers and generating grounded business advice..."):
            # Auto-detect language of query if user didn't explicitly override
            detected_q_lang = identify_query_language(user_input, default=st.session_state["advisor_language"])
            query_lang = st.session_state["advisor_language"] if st.session_state.get("advisor_lang_select") else detected_q_lang
            response = generate_business_advice(
                user_query=user_input,
                pipeline_result=result,
                chat_history=st.session_state["chat_history"],
                language=query_lang,
                response_style=st.session_state["advisor_response_style"],
            )
            if response:
                st.session_state["chat_history"].append({
                    "user": user_input,
                    "ai": response
                })

    # Render Chat History
    for chat in reversed(st.session_state["chat_history"]):
        user_msg = chat["user"]
        ai_resp = chat["ai"]
        
        st.markdown(f"**👤 You:** {user_msg}")
        
        if isinstance(ai_resp, dict):
            recs = ai_resp.get("recommendations", [])
            for idx, rec in enumerate(recs, 1):
                pri = rec.get("priority", "MEDIUM").upper()
                pri_col = "#DC2626" if pri in ["HIGH", "CRITICAL"] else ("#EA580C" if pri == "MEDIUM" else "#059669")
                render_html(
                    f"""
                    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 4px solid {pri_col}; border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <strong style="color: #1E293B; font-size: 0.95rem;">{rec.get('title', 'Actionable Insight')}</strong>
                            <span style="background: {pri_col}14; color: {pri_col}; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 10px;">{pri}</span>
                        </div>
                        <div style="font-size: 0.84rem; color: #475569; margin: 4px 0;"><strong>Findings:</strong> {rec.get('finding', '')}</div>
                        <div style="font-size: 0.84rem; color: #0D9488;"><strong>Recommendation:</strong> {rec.get('action', '')}</div>
                    </div>
                    """
                )
                spoken_script = f"{rec.get('title', '')}. Finding: {rec.get('finding', '')}. Action: {rec.get('action', '')}"
                render_speech_synthesis_player(spoken_script, language=current_sys_lang, key=f"tts_rec_{idx}")
        else:
            st.info(str(ai_resp))
            render_speech_synthesis_player(str(ai_resp), language=current_sys_lang, key="tts_direct_resp")

with col2:
    st.markdown(f"### 🎙️ {t('Voice & Audio Query', current_sys_lang)}")
    voice_file = st.file_uploader(t("Upload audio recording", current_sys_lang), type=["wav", "aiff", "flac"], key="advisor_voice_audio")
    if voice_file:
        voice_result = transcribe_audio(voice_file.getvalue(), SUPPORTED_LANGUAGES.get(st.session_state["advisor_language"]))
        if voice_result.get("text"):
            st.session_state["voice_transcription"] = voice_result["text"]
            st.success(f"Transcribed: {voice_result['text']}")
        else:
            st.info(t("Voice transcription completed or unavailable.", current_sys_lang))

    render_html("<div style='height: 1rem;'></div>")
    st.markdown(f"### 📊 {t('Operational Context Snapshot', current_sys_lang)}")
    render_html(
        f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.1rem; box-shadow: 0 2px 6px rgba(30,41,59,0.03); font-size: 0.85rem; color: #475569; line-height: 1.7;">
            <div><strong>Active Ledger:</strong> {format_currency(tot_rev)}</div>
            <div><strong>Operating Expenses:</strong> {format_currency(f.get('total_expenses', 0))}</div>
            <div><strong>Net Operating Margin:</strong> {margin_pct:.1f}%</div>
            <div><strong>Total Receivables:</strong> {format_currency(out_rec)}</div>
            <div><strong>Tracked Customers:</strong> {len(cust_data.get('customers', []))} accounts</div>
            <div><strong>Reorder Items:</strong> {reorder_len} SKUs</div>
        </div>
        """
    )
