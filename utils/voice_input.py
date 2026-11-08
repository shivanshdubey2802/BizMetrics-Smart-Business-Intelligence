"""
BizMetrics Voice-Based Multilingual AI Advisor Audio Engine
Provides HTML5 browser-native speech recognition for Hindi, English, and Hinglish,
Text-To-Speech (TTS) audio playback, and audio transcription helpers.
"""
from __future__ import annotations

import html
import json
from io import BytesIO
from typing import Optional
import streamlit as st
from utils.translations import normalize_lang


def get_speech_language_code(language: Optional[str]) -> str:
    """Map BizMetrics language to BCP 47 speech recognition language code."""
    norm = normalize_lang(language)
    if norm == "हिंदी":
        return "hi-IN"
    elif norm == "Hinglish":
        return "hi-IN"
    return "en-IN"


def render_voice_input_widget(language: str = "English", key: str = "voice_input_widget") -> None:
    """
    Renders an HTML5 Web Speech API microphone widget in Streamlit.
    Works natively in Chrome, Edge, Safari, and modern mobile browsers.
    """
    lang_code = get_speech_language_code(language)
    widget_html = f"""
    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 0.85rem 1rem; margin-bottom: 0.75rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <button id="{key}_btn" onclick="startBizMetricsVoiceRecording('{key}', '{lang_code}')" 
                    style="background: #0D9488; color: #FFFFFF; border: none; border-radius: 50px; padding: 7px 18px; font-weight: 600; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 6px; box-shadow: 0 2px 4px rgba(13,148,136,0.2);">
                    <span id="{key}_icon">🎙️</span> <span id="{key}_label">Speak Question ({language})</span>
                </button>
                <span id="{key}_status" style="font-size: 0.8rem; color: #64748B;">Click to speak</span>
            </div>
            <span style="font-size: 0.72rem; color: #94A3B8; font-style: italic;">HTML5 Web Speech Recognition</span>
        </div>
        <div id="{key}_transcript_box" style="margin-top: 8px; font-size: 0.85rem; color: #1E293B; background: #FFFFFF; border: 1px dashed #CBD5E1; border-radius: 6px; padding: 6px 10px; display: none;">
            <strong style="color: #0D9488;">Transcribed:</strong> <span id="{key}_text"></span>
        </div>
    </div>

    <script>
    function startBizMetricsVoiceRecording(widgetId, langCode) {{
        const btn = document.getElementById(widgetId + '_btn');
        const icon = document.getElementById(widgetId + '_icon');
        const label = document.getElementById(widgetId + '_label');
        const status = document.getElementById(widgetId + '_status');
        const box = document.getElementById(widgetId + '_transcript_box');
        const textBox = document.getElementById(widgetId + '_text');

        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {{
            status.innerText = '⚠️ Speech Recognition not supported in this browser. Please type.';
            status.style.color = '#DC2626';
            return;
        }}

        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRec();
        recognition.lang = langCode;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = function() {{
            btn.style.background = '#DC2626';
            icon.innerText = '🔴';
            label.innerText = 'Listening... Speak now';
            status.innerText = 'Listening to microphone...';
            status.style.color = '#DC2626';
        }};

        recognition.onresult = function(event) {{
            const transcript = event.results[0][0].transcript;
            box.style.display = 'block';
            textBox.innerText = transcript;
            status.innerText = '✅ Recognized! (Copying to input)';
            status.style.color = '#059669';

            // Find streamlit textarea or input box and fill
            const inputs = window.parent.document.querySelectorAll('input[type="text"], textarea');
            inputs.forEach(el => {{
                if (el.getAttribute('aria-label') && el.getAttribute('aria-label').toLowerCase().includes('advisor') || 
                    el.getAttribute('placeholder') && el.getAttribute('placeholder').toLowerCase().includes('ask')) {{
                    el.value = transcript;
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }});
        }};

        recognition.onerror = function(event) {{
            status.innerText = 'Speech recognition error: ' + event.error;
            status.style.color = '#DC2626';
            btn.style.background = '#0D9488';
            icon.innerText = '🎙️';
            label.innerText = 'Speak Question';
        }};

        recognition.onend = function() {{
            btn.style.background = '#0D9488';
            icon.innerText = '🎙️';
            label.innerText = 'Speak Question';
        }};

        recognition.start();
    }}
    </script>
    """
    st.components.v1.html(widget_html, height=85)


def render_speech_synthesis_player(text_to_speak: str, language: str = "English", key: str = "tts_player") -> None:
    """
    Renders a '🔊 Listen to Answer' button using HTML5 browser SpeechSynthesis.
    Reads the answer aloud in natural Hindi or English.
    """
    if not text_to_speak:
        return

    # Clean text of markdown asterisks, hashes, and code blocks for spoken audio
    clean_text = text_to_speak.replace("*", "").replace("#", "").replace("`", "").replace("₹", "Rupees ").strip()
    safe_text_json = json.dumps(clean_text)
    lang_code = get_speech_language_code(language)

    tts_html = f"""
    <div style="margin: 0.5rem 0 1rem 0;">
        <button id="{key}_btn" onclick="playBizMetricsTTS('{key}', {safe_text_json}, '{lang_code}')"
            style="background: #F1F5F9; color: #0F766E; border: 1px solid #0D9488; border-radius: 20px; padding: 4px 14px; font-size: 0.8rem; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 5px;">
            <span id="{key}_icon">🔊</span> <span id="{key}_label">Listen to Answer ({language})</span>
        </button>
        <span id="{key}_status" style="font-size: 0.75rem; color: #64748B; margin-left: 8px;"></span>
    </div>

    <script>
    function playBizMetricsTTS(btnId, speechText, langCode) {{
        const btn = document.getElementById(btnId + '_btn');
        const icon = document.getElementById(btnId + '_icon');
        const label = document.getElementById(btnId + '_label');
        const status = document.getElementById(btnId + '_status');

        if (!('speechSynthesis' in window)) {{
            status.innerText = 'Speech synthesis not supported in this browser.';
            return;
        }}

        if (window.speechSynthesis.speaking) {{
            window.speechSynthesis.cancel();
            icon.innerText = '🔊';
            label.innerText = 'Listen to Answer';
            status.innerText = '';
            return;
        }}

        const utterance = new SpeechSynthesisUtterance(speechText);
        utterance.lang = langCode;
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onstart = function() {{
            icon.innerText = '⏹️';
            label.innerText = 'Stop Audio';
            status.innerText = 'Speaking...';
        }};

        utterance.onend = function() {{
            icon.innerText = '🔊';
            label.innerText = 'Listen to Answer';
            status.innerText = '';
        }};

        utterance.onerror = function() {{
            icon.innerText = '🔊';
            label.innerText = 'Listen to Answer';
            status.innerText = '';
        }};

        window.speechSynthesis.speak(utterance);
    }}
    </script>
    """
    st.components.v1.html(tts_html, height=45)


def transcribe_audio(audio_bytes: bytes, language: str | None = None) -> dict[str, str | None]:
    """Preserved backend audio file transcriber for test compatibility."""
    if not audio_bytes:
        return {"text": None, "status": "empty", "message": "No audio was provided."}
    try:
        import speech_recognition as sr
    except ImportError:
        return {"text": None, "status": "unavailable", "message": "Voice input is currently unavailable in this environment. Please type your question instead."}
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language=language or "en-IN")
        return {"text": text, "status": "success", "message": None}
    except Exception:
        return {"text": None, "status": "failed", "message": "Voice transcription failed. Please edit or type your question instead."}
