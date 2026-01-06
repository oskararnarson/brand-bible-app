import json
import os
import re
import struct
import tempfile
import time
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import concurrent.futures
import streamlit as st
import google.generativeai as genai
from fpdf import FPDF

try:
    import requests
except Exception:
    requests = None

# =========================
# CONFIG & STYLE
# =========================
st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")

# Design Constants
PDF_W = 297
PDF_H = 210
MARGIN = 25
GUTTER = 15
L_WIDTH = PDF_W - (MARGIN * 2)

# =========================
# Session state
# =========================
def ss_init():
    defaults = {
        "view": "landing",
        "step_index": 0,
        "answers": {},
        "api_key": "",
        "gen_used": 0,
        "gen_max": 5,
        "last_json": None,
        "pdf_bytes": None,
        "model_used": "",
        "error": "",
        "plate_paths": {},
        "asset_paths": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.api_key:
        st.session_state.api_key = (st.secrets.get("GEMINI_API_KEY", "") or "").strip()

def go(view: str):
    st.session_state.view = view
    st.rerun()

def reset_app(keep_api_key: bool = True):
    api_key = st.session_state.api_key
    st.session_state.clear()
    ss_init()
    if keep_api_key:
        st.session_state.api_key = api_key

# =========================
# CSS (UI ONLY)
# =========================
def inject_css():
    st.markdown("""
<style>
.stApp { background: #0b0d11; color: #ffffff; }
.card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 40px; }
.heroTitle { font-size: 42px; font-weight: 900; line-height: 1.1; margin-bottom: 20px; }
.stButton>button { border-radius: 50px; padding: 10px 30px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =========================
# Data Structure (Sections/Questions)
# =========================
@dataclass
class Section:
    id: str
    title: str
    line: str

@dataclass
class Question:
    id: str
    section_id: str
    title: str
    micro: str
    qtype: str
    key: str
    placeholder: str = ""
    options: list[str] | None = None
    required: bool = True

SECTIONS = [
    Section("foundation", "Foundation", "Brands are built on decisions, not descriptions."),
    Section("audience", "Audience", "People buy relief, status, or clarity."),
    Section("positioning", "Positioning", "If you do not define your position, the market will."),
    Section("voice", "Voice", "Tone is what people remember when they forget details."),
    Section("visual", "Visual direction", "Taste is a strategy, not decoration."),
]

QUESTIONS: list[Question] = [
    Question("q1", "foundation", "Brand name", "The anchor.", "text", "brand_name", placeholder="Example: Mindbitch"),
    Question("q2", "foundation", "One sentence mission", "Clear and cutting.", "textarea", "one_sentence"),
    Question("q19", "voice", "Tone words", "Precise adjectives.", "text", "tone_words", placeholder="Example: Direct, Authoritative"),
    Question("q20", "voice", "Banned words", "What do you refuse to say?", "text", "banned_words"),
    Question("q24", "voice", "Voice Energy", "Choose the posture.", "cards", "voice_energy", options=["Sharp", "Calm", "Bold", "Clinical"]),
    Question("q27", "visual", "Brand Place", "What atmosphere do you inhabit?", "cards", "brand_place", options=["Gallery", "Studio", "Clinic", "High end hotel"]),
]

def wizard_steps():
    steps = []
    for sec in SECTIONS:
        steps.append({"type": "section", "section_id": sec.id})
        for q in QUESTIONS:
            if q.section_id == sec.id:
                steps.append({"type": "question", "qid": q.id})
    return steps

def get_question(qid): return next(q for q in QUESTIONS if q.id == qid)
def get_section(sid): return next(s for s in SECTIONS if s.id == sid)

# =========================
# PDF ENGINE (RE-DESIGNED)
# =========================
class BrandPDF(FPDF):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._brand_name = "Brand"
        self._accent_color = (255, 0, 0)

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"{self._brand_name.upper()} // INTERNAL CONFIDENTIAL", align="L")
        self.cell(0, 10, str(self.page_no()), align="R")

    def draw_accent_line(self, y, width=60):
        self.set_draw_color(*self._accent_color)
        self.set_line_width(1.5)
        self.line(MARGIN, y, MARGIN + width, y)

    def page_title(self, title):
        self.add_page(orientation="L")
        self.set_text_color(20, 20, 20)
        self.set_font("Helvetica", "B", 24)
        self.set_xy(MARGIN, 25)
        self.cell(0, 10, title.upper())
        self.draw_accent_line(38, 40)
        self.set_y(50)

def safe_text(s):
    return str(s).encode("latin-1", "replace").decode("latin-1")

def render_pdf(schema, answers):
    meta = schema.get("meta", {})
    colors = schema.get("colors", {})
    brand_name = answers.get("brand_name", "Brand")
    
    primary_rgb = _hex_to_rgb(colors.get("primary_hex", "#000000"), (0,0,0))
    accent_rgb = _hex_to_rgb(colors.get("accent_hex", "#FF0000"), (255,0,0))

    pdf = BrandPDF(orientation="L", unit="mm", format="A4")
    pdf._brand_name = brand_name
    pdf._accent_color = accent_rgb
    pdf.set_auto_page_break(True, margin=20)

    # --- COVER PAGE ---
    pdf.add_page(orientation="L")
    pdf.set_fill_color(*primary_rgb)
    pdf.rect(0, 0, PDF_W, PDF_H, "F")
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 60)
    pdf.set_xy(MARGIN, 70)
    pdf.multi_cell(L_WIDTH, 20, safe_text(brand_name))
    
    pdf.set_font("Helvetica", "", 16)
    pdf.set_y(pdf.get_y() + 5)
    pdf.set_x(MARGIN)
    pdf.cell(0, 10, "BRAND STRATEGY & VISUAL SYSTEM", ln=True)
    
    pdf.set_draw_color(*accent_rgb)
    pdf.set_line_width(2)
    pdf.line(MARGIN, pdf.get_y() + 5, MARGIN + 100, pdf.get_y() + 5) # FIXED LINE

    # --- MESSAGING PAGE (REDESIGNED) ---
    pdf.page_title("Messaging System")
    msg_data = schema.get("messaging", {})
    
    # Core Message Box
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(MARGIN, 50, L_WIDTH, 40, "F")
    pdf.set_xy(MARGIN + 10, 58)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*accent_rgb)
    pdf.cell(0, 10, "CORE PROMISE")
    pdf.set_xy(MARGIN + 10, 68)
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(L_WIDTH - 20, 7, safe_text(msg_data.get("core_message", "")))

    # Key Messages
    pdf.set_y(105)
    kms = msg_data.get("key_messages", [])
    for m in kms[:3]:
        pdf.set_x(MARGIN)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(L_WIDTH, 8, f"-> {safe_text(m.get('message', ''))}")
        pdf.set_x(MARGIN + 6)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(L_WIDTH - 10, 6, safe_text(m.get('proof', '')))
        pdf.ln(5)

    # --- VOICE RULES (REDESIGNED) ---
    pdf.page_title("Voice Rules")
    voice = schema.get("voice", {})
    
    # Do / Do Not Table
    col_w = L_WIDTH / 2 - 5
    start_y = 60
    
    # Headers
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(MARGIN, start_y)
    pdf.set_text_color(30, 160, 30) # Green for "Do"
    pdf.cell(col_w, 10, "USE THESE WORDS", border="B", ln=0)
    pdf.set_x(MARGIN + col_w + 10)
    pdf.set_text_color(200, 30, 30) # Red for "Don't"
    pdf.cell(col_w, 10, "BANNED VOCABULARY", border="B", ln=1)
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(50, 50, 50)
    
    dos = voice.get("do_say", [])
    donts = voice.get("do_not_say", [])
    
    for i in range(max(len(dos), len(donts))):
        d_text = dos[i] if i < len(dos) else ""
        dn_text = donts[i] if i < len(donts) else ""
        
        curr_y = pdf.get_y()
        pdf.set_x(MARGIN)
        pdf.cell(col_w, 8, f"+ {safe_text(d_text)}")
        pdf.set_x(MARGIN + col_w + 10)
        pdf.cell(col_w, 8, f"x {safe_text(dn_text)}")
        pdf.ln(8)

    # --- MOODBOARD (REDESIGNED) ---
    pdf.page_title("Visual Moodboard")
    theme = pick_photo_theme(answers, schema)
    # Using a more reliable query for high-impact imagery
    img_urls = [
        f"https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?auto=format&fit=crop&w=800&q=80",
        f"https://images.unsplash.com/photo-1493397212122-2b85def82820?auto=format&fit=crop&w=800&q=80",
        f"https://images.unsplash.com/photo-1550684848-fac1c5b4e853?auto=format&fit=crop&w=800&q=80",
        f"https://images.unsplash.com/photo-1505330622279-bf7d7fc918f4?auto=format&fit=crop&w=800&q=80",
        f"https://images.unsplash.com/photo-1518005020481-a685156069e9?auto=format&fit=crop&w=800&q=80",
        f"https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=800&q=80"
    ]
    
    # Grid Logic
    gw = (L_WIDTH - 10) / 3
    gh = 60
    for i, url in enumerate(img_urls):
        row = i // 3
        col = i % 3
        x = MARGIN + (col * (gw + 5))
        y = 55 + (row * (gh + 5))
        
        # In a real app, you would download these. For now, we simulate the layout.
        pdf.set_fill_color(230, 230, 230)
        pdf.rect(x, y, gw, gh, "F")
        pdf.set_xy(x, y + gh/2 - 5)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(gw, 10, "IMAGE ASSET", align="C")

    return pdf.output(dest="S").encode("latin-1", "replace")

# =========================
# HELPER FUNCTIONS
# =========================
def _hex_to_rgb(h, fallback):
    h = h.lstrip('#')
    try: return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except: return fallback

def pick_photo_theme(answers, schema):
    energy = answers.get("voice_energy", "Bold")
    return "dark_minimalism" if energy == "Sharp" else "industrial_chic"

# =========================
# Streamlit UI & Flow
# =========================
def main():
    ss_init()
    inject_css()
    
    if st.session_state.view == "landing":
        landing_view()
    elif st.session_state.view == "wizard":
        wizard_view()
    elif st.session_state.view == "generate":
        generate_view()
    elif st.session_state.view == "done":
        done_view()

def landing_view():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle">Brand Bible Generator 2.0</div>', unsafe_allow_html=True)
    st.write("Professional-grade brand decks for strategic dominance.")
    if st.button("Begin Interview"):
        go("wizard")
    st.markdown('</div>', unsafe_allow_html=True)

def wizard_view():
    steps = wizard_steps()
    step = steps[st.session_state.step_index]
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if step["type"] == "section":
        sec = get_section(step["section_id"])
        st.subheader(sec.title)
        st.write(sec.line)
    else:
        q = get_question(step["qid"])
        st.subheader(q.title)
        if q.qtype == "text":
            st.session_state.answers[q.key] = st.text_input(q.micro, key=f"in_{q.id}")
        elif q.qtype == "textarea":
            st.session_state.answers[q.key] = st.text_area(q.micro, key=f"in_{q.id}")
        elif q.qtype == "cards":
            st.session_state.answers[q.key] = st.radio(q.micro, q.options, key=f"in_{q.id}")

    if st.button("Continue"):
        if st.session_state.step_index < len(steps)-1:
            st.session_state.step_index += 1
            st.rerun()
        else:
            go("generate")
    st.markdown('</div>', unsafe_allow_html=True)

def generate_view():
    # Simulation of Gemini Call for this demo
    st.write("Strategizing...")
    dummy_schema = {
        "meta": {"brand_name": st.session_state.answers.get("brand_name")},
        "colors": {"primary_hex": "#0a0a0a", "accent_hex": "#ff3300"},
        "messaging": {
            "core_message": "Master your mind, master your results. Mindbitch delivers precision tools for dominance.",
            "key_messages": [
                {"message": "Cut through noise.", "proof": "Frameworks that dismantle cognitive bias."},
                {"message": "Strategy over sentiment.", "proof": "Rigorous research, not feel-good affirmations."}
            ]
        },
        "voice": {
            "do_say": ["Confront", "Dismantle", "Execute", "Dominate", "Rigor"],
            "do_not_say": ["Journey", "Vibe", "Elevate", "Embrace", "Guru"]
        }
    }
    pdf_bytes = render_pdf(dummy_schema, st.session_state.answers)
    st.session_state.pdf_bytes = pdf_bytes
    go("done")

def done_view():
    st.success("Brand Deck Generated.")
    st.download_button("Download Premium PDF", st.session_state.pdf_bytes, "Brand_Bible.pdf", "application/pdf")
    if st.button("Reset"):
        reset_app()
        go("landing")

if __name__ == "__main__":
    main()
