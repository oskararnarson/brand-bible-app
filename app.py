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

st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")

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
    plate_paths = st.session_state.plate_paths
    asset_paths = st.session_state.asset_paths
    st.session_state.clear()
    ss_init()
    st.session_state.plate_paths = plate_paths
    st.session_state.asset_paths = asset_paths
    if keep_api_key:
        st.session_state.api_key = api_key

# =========================
# CSS (Full Restore)
# =========================
def inject_css():
    st.markdown(
        """
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.block-container { max-width: 1180px; padding-top: 2.4rem; padding-bottom: 3.2rem; }
:root{
  --bg:#0b0d11;
  --fg:rgba(235,240,255,0.92);
  --muted:rgba(235,240,255,0.70);
  --card:rgba(255,255,255,0.06);
  --accent:#1c7dff;
}
html, body { background: var(--bg); color: var(--fg); }
.stApp{
  background: radial-gradient(1100px 700px at 20% 35%, rgba(0,120,255,0.18), rgba(0,0,0,0) 60%), #0b0d11;
}
.card{
  background: linear-gradient(180deg, var(--card), rgba(255,255,255,0.04));
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 22px;
  padding: 28px;
  box-shadow: 0 30px 120px rgba(0,0,0,0.55);
  backdrop-filter: blur(14px);
}
.heroTitle{ font-size: 52px; font-weight: 900; line-height: 1.05; margin: 0 0 10px 0; }
.bigBtn div.stButton > button{
  width: 290px; height: 54px; border-radius: 999px; font-size: 18px; font-weight: 900;
  background: linear-gradient(180deg, #1c7dff, #0d5fe9) !important;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.fadeIn { animation: fadeIn 220ms ease-out; }
</style>
""",
        unsafe_allow_html=True,
    )

# =========================
# THE FULL 30 QUESTIONS (RESTORED)
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
    Section("positioning", "Positioning", "Define your stand, or the market will."),
    Section("voice", "Voice", "Tone is what people remember."),
    Section("visual", "Visual direction", "Taste is a strategy, not decoration."),
]

QUESTIONS: list[Question] = [
    Question("q1", "foundation", "Brand name", "The anchor.", "text", "brand_name", placeholder="Oura / Mindbitch"),
    Question("q2", "foundation", "One sentence mission", "Avoid noise.", "textarea", "one_sentence"),
    Question("q3", "foundation", "Why deserve to exist?", "Utility, not origin.", "textarea", "why_exist"),
    Question("q4", "foundation", "Misunderstood problem", "The lazy assumption you reject.", "textarea", "misunderstood_problem"),
    Question("q5", "foundation", "What do you sell in reality?", "Outcome, not product.", "textarea", "real_outcome"),
    Question("q6", "foundation", "Hard no", "The clean boundary.", "textarea", "hard_no"),
    
    Question("q7", "audience", "Core customer profile", "One real person.", "textarea", "core_customer"),
    Question("q8", "audience", "Secret want", "What they want but won't say.", "textarea", "secret_want"),
    Question("q9", "audience", "Primary objection", "In their own words.", "textarea", "primary_objection"),
    Question("q10", "audience", "Trust trigger", "Proof they trust.", "textarea", "trust_trigger"),
    Question("q11", "audience", "Category myth", "The myth you refuse to repeat.", "textarea", "category_myth"),
    Question("q12", "audience", "Worst experience", "What must never happen.", "textarea", "worst_experience"),

    Question("q13", "positioning", "Anti-brand model", "The brand you refuse to resemble.", "textarea", "anti_brand"),
    Question("q14", "positioning", "The 'Brand That...' statement", "Finish the truth.", "textarea", "positioning_sentence"),
    Question("q15", "positioning", "Unfair advantage", "Hard to copy.", "textarea", "unfair_advantage"),
    Question("q16", "positioning", "Wrong category", "Where you are misfiled.", "text", "wrong_category"),
    Question("q17", "positioning", "Right category", "The category you own.", "text", "right_category"),
    Question("q18", "positioning", "Posture Animal", " एनर्जी पोस्टचर.", "cards", "animal", options=["Fox", "Hawk", "Panther", "Owl", "Wolf", "Stallion", "Other"]),

    Question("q19", "voice", "Tone words", "Direct, bold, precise.", "text", "tone_words"),
    Question("q20", "voice", "Banned words", "The generic vocabulary.", "text", "banned_words"),
    Question("q21", "voice", "Signature belief", "The opinion that creates gravity.", "textarea", "signature_belief"),
    Question("q22", "voice", "Close sentence", "Simplest sales truth.", "textarea", "close_sentence"),
    Question("q23", "voice", "Customer quote", "Real person talking.", "textarea", "customer_quote"),
    Question("q24", "voice", "Voice energy", "Posturing energy.", "cards", "voice_energy", options=["Calm", "Confident", "Bold", "Sharp", "Clinical"]),

    Question("q25", "visual", "Taste references", "Brand: Why.", "textarea", "taste_refs"),
    Question("q26", "visual", "Vibes to avoid", "Instant fails.", "checks", "avoid_vibes", options=["Corporate", "Startup hype", "Luxury cliche", "Lifestyle fluff"]),
    Question("q27", "visual", "Brand place", "Atmospheric setting.", "cards", "brand_place", options=["Gallery", "Workshop", "Clinic", "Studio"]),
    Question("q28", "visual", "First impression", "Feel before words.", "cards", "first_impression", options=["Controlled", "Excited", "Safe", "Powerful"]),
    Question("q29", "visual", "Visual constraints", "Hard constraints.", "textarea", "never_visuals"),
    Question("q30", "visual", "Failure mode", "Fear of failure.", "textarea", "fear"),
]

def wizard_steps():
    steps = []
    for sec in SECTIONS:
        steps.append({"type": "section", "section_id": sec.id})
        for q in QUESTIONS:
            if q.section_id == sec.id:
                steps.append({"type": "question", "qid": q.id})
    return steps

# =========================
# AI PROMPT (FULL RESTORE)
# =========================
def build_prompt(answers: dict, version_str: str) -> str:
    schema = {
        "meta": { "brand_name": "", "version": "", "date_utc": "" },
        "colors": { "primary_hex": "", "accent_hex": "", "neutral_hex": "", "background_hex": "" },
        "typography": { "primary_font": "", "secondary_font": "", "notes": "" },
        "hero": { "headline": "", "subhead": "" },
        "executive_summary": { "decisions": [""] },
        "positioning": { "positioning_statement": "", "category": "", "anti_position": "" },
        "audience": { "core_customer": "", "core_tension": "", "primary_objection": "", "trust_trigger": "" },
        "messaging": { "core_message": "", "key_messages": [ { "message": "", "proof": "" } ] },
        "voice": { "principles": [""], "do_say": [""], "do_not_say": [""], "examples": { "before": "", "after": "" } },
        "visual_direction": { "intent": "", "feels_like": [""], "never_feels_like": [""], "imagery_keywords": [""] },
        "guardrails": { "failure_modes": [""] },
        "usage": { "how_to_use": [""] }
    }
    return (
        "You are a senior brand strategist. Do not describe. Decide.\n"
        "Return ONLY valid JSON matching this schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        f"DATA:\n{json.dumps(answers, indent=2)}"
    )

def generate_schema(prompt: str):
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(prompt)
    raw = resp.text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    return json.loads(raw), "gemini-1.5-flash"

# =========================
# THE PDF ENGINE (REPAIRED DESIGN)
# =========================
class BrandPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(160, 160, 160)
        self.cell(0, 10, f"{str(st.session_state.answers.get('brand_name', '')).upper()}", align="L")
        self.set_x(-25)
        self.cell(10, 10, str(self.page_no()), align="R")

def safe_text(s): return str(s).encode("latin-1", "replace").decode("latin-1")

def _hex_to_rgb(h, fallback):
    h = str(h).lstrip('#')
    try: return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except: return fallback

def render_pdf(schema, answers):
    pdf = BrandPDF(orientation="L", unit="mm", format="A4")
    brand = answers.get("brand_name", "Brand")
    colors = schema.get("colors", {})
    primary = _hex_to_rgb(colors.get("primary_hex", "#0b0d11"), (11, 13, 17))
    accent = _hex_to_rgb(colors.get("accent_hex", "#ff0000"), (255, 0, 0))
    
    # --- PAGE 1: COVER ---
    pdf.add_page()
    pdf.set_fill_color(*primary)
    pdf.rect(0, 0, 297, 210, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 58)
    pdf.set_xy(25, 65)
    pdf.multi_cell(247, 20, safe_text(brand))
    
    hero = schema.get("hero", {})
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_y(pdf.get_y() + 10)
    pdf.set_x(25)
    pdf.multi_cell(247, 12, safe_text(hero.get("headline", "")))
    
    # FIX: INTENTIONAL LINE WIDTH
    pdf.set_draw_color(*accent)
    pdf.set_line_width(2.5)
    pdf.line(25, pdf.get_y() + 15, 25 + 100, pdf.get_y() + 15)

    # --- PAGE 2: MESSAGING (REPAIRED) ---
    pdf.add_page()
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_xy(25, 25)
    pdf.cell(0, 10, "Messaging System")
    pdf.line(25, 34, 75, 34)
    
    msg = schema.get("messaging", {})
    # Core Callout
    pdf.set_fill_color(248, 248, 248)
    pdf.rect(25, 48, 247, 35, "F")
    pdf.set_xy(30, 52)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*accent)
    pdf.cell(0, 5, "CORE STRATEGY")
    pdf.set_xy(30, 60)
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "", 14)
    pdf.multi_cell(237, 8, safe_text(msg.get("core_message", "")))
    
    # Key Messages Grid
    pdf.set_y(95)
    for m in msg.get("key_messages", [])[:3]:
        pdf.set_x(25)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(247, 8, f"-> {safe_text(m.get('message', ''))}")
        pdf.set_x(30)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(242, 6, safe_text(m.get("proof", "")))
        pdf.ln(5)

    # --- PAGE 3: VOICE RULES (REPAIRED) ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_xy(25, 25)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 10, "Voice rules")
    pdf.line(25, 34, 65, 34)
    
    voice = schema.get("voice", {})
    col_w = (247 / 2) - 10
    pdf.set_y(55)
    
    # Headers
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_x(25)
    pdf.set_text_color(46, 125, 50)
    pdf.cell(col_w, 10, "USE THESE", border="B")
    pdf.set_x(25 + col_w + 20)
    pdf.set_text_color(198, 40, 40)
    pdf.cell(col_w, 10, "BAN THESE", border="B", ln=True)
    
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    dos, donts = voice.get("do_say", []), voice.get("do_not_say", [])
    for i in range(max(len(dos), len(donts))):
        pdf.set_x(25)
        pdf.cell(col_w, 10, f"+ {safe_text(dos[i] if i < len(dos) else '')}")
        pdf.set_x(25 + col_w + 20)
        pdf.cell(col_w, 10, f"x {safe_text(donts[i] if i < len(donts) else '')}")
        pdf.ln(10)

    # --- PAGE 4: MOODBOARD ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_xy(25, 25)
    pdf.cell(0, 10, "Moodboard")
    pdf.line(25, 34, 75, 34)
    
    gw, gh, gutter = 80, 65, 5
    for i in range(6):
        r, c = i // 3, i % 3
        x, y = 25 + (c * (gw + gutter)), 50 + (r * (gh + gutter))
        pdf.set_fill_color(240, 240, 240)
        pdf.rect(x, y, gw, gh, "F")
        pdf.set_xy(x, y + gh/2)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(180, 180, 180)
        pdf.cell(gw, 10, f"ASSET {i+1}", align="C")

    return pdf.output(dest="S").encode("latin-1", "replace")

# =========================
# UI (RESTORED FLOW)
# =========================
def main():
    ss_init()
    inject_css()
    if st.session_state.view == "landing":
        st.markdown('<div class="card fadeIn">', unsafe_allow_html=True)
        st.markdown('<div class="heroTitle">Brand Bible Generator</div>', unsafe_allow_html=True)
        if st.button("Start Interview"): go("wizard")
        st.markdown('</div>', unsafe_allow_html=True)
    elif st.session_state.view == "wizard":
        steps = wizard_steps()
        step = steps[st.session_state.step_index]
        st.markdown('<div class="card fadeIn">', unsafe_allow_html=True)
        if step["type"] == "section":
            sec = get_section(step["section_id"])
            st.header(sec.title)
            st.info(sec.line)
        else:
            q = next(qu for qu in QUESTIONS if qu.id == step["qid"])
            st.subheader(q.title)
            if q.qtype == "text": st.session_state.answers[q.key] = st.text_input(q.micro, key=f"q_{q.id}")
            elif q.qtype == "textarea": st.session_state.answers[q.key] = st.text_area(q.micro, key=f"q_{q.id}")
            elif q.qtype == "cards": st.session_state.answers[q.key] = st.radio(q.micro, q.options, key=f"q_{q.id}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Back"): 
                if st.session_state.step_index > 0: st.session_state.step_index -= 1
                else: go("landing")
                st.rerun()
        with col2:
            if st.button("Next"):
                if st.session_state.step_index < len(steps)-1: 
                    st.session_state.step_index += 1
                    st.rerun()
                else: go("generate")
        st.markdown('</div>', unsafe_allow_html=True)
    elif st.session_state.view == "generate":
        genai.configure(api_key=st.session_state.api_key)
        prompt = build_prompt(st.session_state.answers, "1.0")
        schema, model = generate_schema(prompt)
        st.session_state.pdf_bytes = render_pdf(schema, st.session_state.answers)
        go("done")
    elif st.session_state.view == "done":
        st.download_button("Download PDF", st.session_state.pdf_bytes, "Brand_Bible.pdf")
        if st.button("Restart"): reset_app(); go("landing")

if __name__ == "__main__":
    main()
