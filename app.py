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
# SYSTEM CONFIG
# =========================
st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")

# Design Measurements
PDF_W = 297
PDF_H = 210
MARGIN = 25
GUTTER = 12
L_WIDTH = PDF_W - (MARGIN * 2)

# =========================
# SESSION STATE
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
# CSS (Restored & Improved)
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
  --muted2:rgba(235,240,255,0.55);
  --card:rgba(255,255,255,0.06);
  --card2:rgba(255,255,255,0.04);
  --stroke:rgba(255,255,255,0.10);
  --accent:#1c7dff;
}

html, body { background: var(--bg); color: var(--fg); }

.stApp{
  background:
    radial-gradient(1100px 700px at 20% 35%, rgba(0,120,255,0.18), rgba(0,0,0,0) 60%),
    radial-gradient(900px 600px at 80% 20%, rgba(255,255,255,0.06), rgba(0,0,0,0) 55%),
    #0b0d11;
}

.card{
  background: linear-gradient(180deg, var(--card), var(--card2));
  border: 1px solid var(--stroke);
  border-radius: 22px;
  padding: 28px;
  box-shadow: 0 30px 120px rgba(0,0,0,0.55);
  backdrop-filter: blur(14px);
}

.eyebrow{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted2);
  margin-bottom: 10px;
}

.heroTitle{
  font-size: 52px;
  line-height: 1.05;
  font-weight: 900;
  margin: 0 0 10px 0;
}

.heroSub{
  font-size: 16px;
  line-height: 1.7;
  color: var(--muted);
  margin-bottom: 18px;
  max-width: 860px;
}

hr.soft{
  border:none;
  height:1px;
  background: rgba(255,255,255,0.08);
  margin: 18px 0;
}

.pills{ display:flex; gap:10px; flex-wrap:wrap; margin-top: 12px; }
.pill{
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  color: rgba(235,240,255,0.75);
}

.bigBtn div.stButton > button{
  width: 290px;
  height: 54px;
  border-radius: 999px;
  font-size: 18px;
  font-weight: 900;
  background: linear-gradient(180deg, #1c7dff, #0d5fe9) !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  box-shadow: 0 18px 50px rgba(0,110,255,0.35);
}

.smallNote{ font-size: 12px; color: rgba(235,240,255,0.58); }

label{
  font-size: 11px !important;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(235,240,255,0.55) !important;
  font-weight: 800 !important;
}

.stTextInput input, .stTextArea textarea{
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  border-radius: 14px !important;
  color: rgba(235,240,255,0.92) !important;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.fadeIn { animation: fadeIn 220ms ease-out; }
</style>
""",
        unsafe_allow_html=True,
    )

# =========================
# THE FULL 30 QUESTIONS
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
    qtype: str  # text, textarea, cards, checks
    key: str
    placeholder: str = ""
    options: list[str] | None = None
    required: bool = True

SECTIONS = [
    Section("foundation", "Foundation", "Brands are built on decisions, not descriptions."),
    Section("audience", "Audience", "People buy relief, status, or clarity. Choose which one you deliver."),
    Section("positioning", "Positioning", "If you do not define your position, the market will do it for you."),
    Section("voice", "Voice", "Tone is what people remember when they forget details."),
    Section("visual", "Visual direction", "Taste is a strategy, not decoration."),
]

QUESTIONS: list[Question] = [
    Question("q1", "foundation", "Brand name", "The anchor. Everything else follows.", "text", "brand_name", placeholder="Example: Oura"),
    Question("q2", "foundation", "Define the brand in one sentence", "If this is vague, the rest becomes noise.", "textarea", "one_sentence", placeholder="We help ... by ..."),
    Question("q3", "foundation", "Why does this deserve to exist", "Not an origin story. The reason this matters.", "textarea", "why_exist", placeholder="Because ..."),
    Question("q4", "foundation", "What is the misunderstood problem you fix", "The lazy assumption you reject.", "textarea", "misunderstood_problem", placeholder="Most people think ... but ..."),
    Question("q5", "foundation", "What do you sell in reality", "Not the product. The outcome people pay for.", "textarea", "real_outcome", placeholder="We sell ..."),
    Question("q6", "foundation", "Your hard no", "The boundary that keeps the brand clean.", "textarea", "hard_no", placeholder="We will never ..."),

    Question("q7", "audience", "Describe one core customer you would recognize instantly", "Write one real person, not a segment.", "textarea", "core_customer", placeholder="They are ... They care about ..."),
    Question("q8", "audience", "What do they want but rarely say out loud", "This lever is where competitors usually fail.", "textarea", "secret_want", placeholder="Secretly they want ..."),
    Question("q9", "audience", "What stops them from buying", "Write the objection in their words.", "textarea", "primary_objection", placeholder="I am not sure because ..."),
    Question("q10", "audience", "What convinces them", "Proof they trust, not claims you like.", "textarea", "trust_trigger", placeholder="They trust ..."),
    Question("q11", "audience", "What misconception about your category must be broken", "The myth you refuse to repeat.", "textarea", "category_myth", placeholder="People assume ..."),
    Question("q12", "audience", "Worst experience they could have with you", "Define what must never happen.", "textarea", "worst_experience", placeholder="They must never feel ..."),

    Question("q13", "positioning", "What brand do you refuse to resemble", "Your anti model clarifies you fast.", "textarea", "anti_brand", placeholder="We refuse to feel like ..."),
    Question("q14", "positioning", "Finish: They are the brand that ...", "Write the truth, not a slogan.", "textarea", "positioning_sentence", placeholder="They are the brand that ..."),
    Question("q15", "positioning", "Your unfair advantage", "Hard to copy, even with money.", "textarea", "unfair_advantage", placeholder="We have ... that others cannot ..."),
    Question("q16", "positioning", "Wrong category people put you in", "Where people misfile you.", "text", "wrong_category", placeholder="Example: productivity app"),
    Question("q17", "positioning", "Category you actually own", "The simplest category that makes you understood.", "text", "right_category", placeholder="Example: recovery tech"),
    Question("q18", "positioning", "Pick an animal for your posture and energy", "Useful shorthand. Not cute.", "cards", "animal", options=["Fox", "Hawk", "Panther", "Owl", "Dolphin", "Wolf", "Bear", "Raven", "Falcon", "Stallion", "Other"]),

    Question("q19", "voice", "Three words you must sound like", "If you choose friendly, you have chosen nothing.", "text", "tone_words", placeholder="Example: precise, calm, bold"),
    Question("q20", "voice", "Three banned words", "If you use these, the brand becomes generic.", "text", "banned_words", placeholder="Example: innovative, seamless, disruptive"),
    Question("q21", "voice", "Your signature belief", "The opinion that creates gravity.", "textarea", "signature_belief", placeholder="We believe ..."),
    Question("q22", "voice", "One close sentence sales can use", "If this is unclear, the brand is unclear.", "textarea", "close_sentence", placeholder="The simplest truth is ..."),
    Question("q23", "voice", "What a satisfied customer would say", "Write it like a real person talking.", "textarea", "customer_quote", placeholder="Honestly, I ..."),
    Question("q24", "voice", "Choose your voice energy", "Choose energy, not adjectives.", "cards", "voice_energy", options=["Calm", "Confident", "Bold", "Sharp", "Warm", "Clinical"]),

    Question("q25", "visual", "Taste references and why", "Name them fast. One word why is enough.", "textarea", "taste_refs", placeholder="Brand: why\nBrand: why"),
    Question("q26", "visual", "Select vibes to avoid", "What would instantly make you look wrong.", "checks", "avoid_vibes", options=["Corporate", "Startup hype", "Luxury cliche", "Playful cartoon", "Sterile tech", "Lifestyle fluff", "Trend chasing"]),
    Question("q27", "visual", "If the brand were a place, what place is it", "Sets layout and atmosphere.", "cards", "brand_place", options=["Gallery", "High end hotel", "Workshop", "Library", "Clinic", "Studio", "Other"]),
    Question("q28", "visual", "What should people feel before they understand", "First impression matters more than features.", "cards", "first_impression", options=["Calm", "Controlled", "Excited", "Safe", "Powerful", "Curious"]),
    Question("q29", "visual", "What must never appear in your visuals", "Hard constraints save time later.", "textarea", "never_visuals", placeholder="Never use ..."),
    Question("q30", "visual", "What are you afraid this becomes if done wrong", "Name the failure mode.", "textarea", "fear", placeholder="If we get this wrong, it becomes ..."),
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
# THE PROMPT SYSTEM
# =========================
def build_prompt(answers: dict, version_str: str) -> str:
    brand = answers.get("brand_name", "Brand")
    answers_json = json.dumps(answers, ensure_ascii=False, indent=2)

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

    prompt = (
        "You are a senior brand strategist and design director.\n"
        "You do not describe. You decide. Be opinionated, concise, and practical.\n"
        "Avoid cliches and startup hype. Do not write essays.\n\n"
        "Return ONLY valid JSON that matches the schema exactly.\n"
        f"JSON SCHEMA:\n{json.dumps(schema, indent=2)}\n\n"
        f"INPUT ANSWERS:\n{answers_json}\n\n"
        "COLOR RULES: Return high-contrast, premium hex codes.\n"
        "HERO RULES: Headline 6-12 words. Subhead 1 sentence.\n"
    )
    return prompt

def generate_schema(prompt: str):
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(prompt)
    raw = resp.text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    return json.loads(raw), "gemini-1.5-flash"

# =========================
# ASSET HANDLING
# =========================
PHOTO_QUERIES = {
    "precision": ["industrial minimalism", "architecture shadows", "steel grid", "technical detail", "clean lab aesthetic"],
    "bold": ["high contrast concrete", "dramatic lighting", "panther aesthetic", "modern sculpture", "aggressive architecture"],
    "calm": ["soft shadows on stone", "minimalist museum", "quiet workspace", "natural fiber texture", "beige architecture"],
    "warm": ["golden hour interior", "natural wood grain", "warm leather", "sunlit studio", "tactile material"]
}

def pick_photo_theme(answers: dict, schema: dict) -> str:
    energy = str(answers.get("voice_energy", "")).lower()
    intent = str(schema.get("visual_direction", {}).get("intent", "")).lower()
    if any(k in energy or k in intent for k in ["sharp", "clinical", "precision"]): return "precision"
    if any(k in energy or k in intent for k in ["bold", "power", "panther"]): return "bold"
    if "warm" in energy or "warm" in intent: return "warm"
    return "calm"

def get_curated_images(theme: str, count: int = 6) -> list[str]:
    # In a production environment, you would use a real API. 
    # Here we mock the collection of images for the PDF grid.
    return [f"[https://images.unsplash.com/photo-](https://images.unsplash.com/photo-){i}?w=800" for i in range(count)]

# =========================
# PDF ENGINE (THE REDESIGN)
# =========================
class BrandPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(160, 160, 160)
        self.cell(0, 10, f"{str(st.session_state.answers.get('brand_name', '')).upper()} // CONFIDENTIAL", align="L")
        self.set_x(-25)
        self.cell(10, 10, str(self.page_no()), align="R")

def safe_text(s): return str(s).encode("latin-1", "replace").decode("latin-1")

def _hex_to_rgb(h, fallback):
    h = str(h).lstrip('#')
    try: return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except: return fallback

def render_pdf(schema, answers):
    brand = answers.get("brand_name", "Brand")
    colors = schema.get("colors", {})
    primary = _hex_to_rgb(colors.get("primary_hex", "#000000"), (0,0,0))
    accent = _hex_to_rgb(colors.get("accent_hex", "#FF0000"), (255,0,0))
    
    pdf = BrandPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=20)

    # --- COVER ---
    pdf.add_page()
    pdf.set_fill_color(*primary)
    pdf.rect(0,0,297,210,"F")
    
    pdf.set_text_color(255,255,255)
    pdf.set_font("Helvetica", "B", 56)
    pdf.set_xy(MARGIN, 65)
    pdf.multi_cell(L_WIDTH, 20, safe_text(brand))
    
    hero = schema.get("hero", {})
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_y(pdf.get_y() + 8)
    pdf.set_x(MARGIN)
    pdf.multi_cell(L_WIDTH, 12, safe_text(hero.get("headline", "")))
    
    pdf.set_font("Helvetica", "", 14)
    pdf.set_y(pdf.get_y() + 6)
    pdf.set_x(MARGIN)
    pdf.multi_cell(L_WIDTH * 0.7, 8, safe_text(hero.get("subhead", "")))
    
    # THE LINE FIX: Intentional fixed width
    pdf.set_draw_color(*accent)
    pdf.set_line_width(2.5)
    pdf.line(MARGIN, pdf.get_y() + 12, MARGIN + 120, pdf.get_y() + 12)

    # --- MESSAGING (REDESIGN) ---
    pdf.add_page()
    pdf.set_text_color(20,20,20)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_xy(MARGIN, 22)
    pdf.cell(0, 10, "Messaging System")
    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.5)
    pdf.line(MARGIN, 34, MARGIN + 60, 34)

    msg = schema.get("messaging", {})
    # Hero Messaging Box
    pdf.set_fill_color(248, 248, 248)
    pdf.rect(MARGIN, 48, L_WIDTH, 42, "F")
    pdf.set_xy(MARGIN + 8, 55)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*accent)
    pdf.cell(0, 5, "CORE BRAND MESSAGE")
    pdf.set_xy(MARGIN + 8, 64)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "", 14)
    pdf.multi_cell(L_WIDTH - 16, 8, safe_text(msg.get("core_message", "")))

    # Key Messages
    pdf.set_y(105)
    for m in msg.get("key_messages", [])[:3]:
        pdf.set_x(MARGIN)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(0,0,0)
        pdf.multi_cell(L_WIDTH, 8, safe_text(m.get("message", "")))
        pdf.set_x(MARGIN)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(L_WIDTH, 6, safe_text(m.get("proof", "")))
        pdf.ln(8)

    # --- VOICE RULES (REDESIGN) ---
    pdf.add_page()
    pdf.set_text_color(20,20,20)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_xy(MARGIN, 22)
    pdf.cell(0, 10, "Voice Rules")
    pdf.line(MARGIN, 34, MARGIN + 40, 34)

    voice = schema.get("voice", {})
    col_w = (L_WIDTH / 2) - 10
    
    # Headers
    pdf.set_y(55)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_x(MARGIN)
    pdf.set_text_color(46, 125, 50) # Strategic Green
    pdf.cell(col_w, 10, "USE THESE WORDS", border="B")
    pdf.set_x(MARGIN + col_w + 20)
    pdf.set_text_color(198, 40, 40) # Aggressive Red
    pdf.cell(col_w, 10, "FORBIDDEN VOCABULARY", border="B", ln=1)

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    dos = voice.get("do_say", [])
    donts = voice.get("do_not_say", [])
    for i in range(max(len(dos), len(donts))):
        d = dos[i] if i < len(dos) else ""
        dn = donts[i] if i < len(donts) else ""
        pdf.set_x(MARGIN)
        pdf.cell(col_w, 10, f"+ {safe_text(d)}")
        pdf.set_x(MARGIN + col_w + 20)
        pdf.cell(col_w, 10, f"x {safe_text(dn)}")
        pdf.ln(10)

    # --- MOODBOARD (REDESIGN) ---
    pdf.add_page()
    pdf.set_text_color(20,20,20)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_xy(MARGIN, 22)
    pdf.cell(0, 10, "Visual Moodboard")
    pdf.line(MARGIN, 34, MARGIN + 55, 34)

    # Grid logic
    cols, rows = 3, 2
    gw = (L_WIDTH - (GUTTER * (cols - 1))) / cols
    gh = 65
    for i in range(6):
        r, c = i // cols, i % cols
        x = MARGIN + (c * (gw + GUTTER))
        y = 52 + (r * (gh + GUTTER))
        pdf.set_fill_color(240, 240, 240)
        pdf.rect(x, y, gw, gh, "F")
        pdf.set_xy(x, y + gh/2)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(180, 180, 180)
        pdf.cell(gw, 10, f"BRAND VISUAL {i+1}", align="C")

    return pdf.output(dest="S").encode("latin-1", "replace")

# =========================
# UI VIEWS
# =========================
def landing_view():
    inject_css()
    st.markdown('<div class="card fadeIn">', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Brand Strategic Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle">Unapologetic Branding for Intellectual Dominance</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroSub">An intensive 30-question brand interview that generates a premium, decision-ready PDF manual.</div>', unsafe_allow_html=True)
    if st.button("Start Interview"): go("wizard")
    st.markdown('</div>', unsafe_allow_html=True)

def wizard_view():
    inject_css()
    steps = wizard_steps()
    step = steps[st.session_state.step_index]
    
    st.markdown('<div class="card fadeIn">', unsafe_allow_html=True)
    if step["type"] == "section":
        sec = get_section(step["section_id"])
        st.subheader(sec.title)
        st.write(sec.line)
    else:
        q = get_question(step["qid"])
        st.subheader(q.title)
        st.caption(q.micro)
        if q.qtype == "text": st.session_state.answers[q.key] = st.text_input("Answer", key=f"q_{q.id}")
        elif q.qtype == "textarea": st.session_state.answers[q.key] = st.text_area("Answer", key=f"q_{q.id}")
        elif q.qtype == "cards": st.session_state.answers[q.key] = st.radio("Select", q.options, key=f"q_{q.id}")
        elif q.qtype == "checks":
            for opt in q.options:
                if st.checkbox(opt, key=f"c_{q.id}_{opt}"):
                    if q.key not in st.session_state.answers: st.session_state.answers[q.key] = []
                    if opt not in st.session_state.answers[q.key]: st.session_state.answers[q.key].append(opt)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            if st.session_state.step_index > 0: st.session_state.step_index -= 1
            else: go("landing")
            st.rerun()
    with col2:
        if st.button("Continue"):
            if st.session_state.step_index < len(steps)-1: 
                st.session_state.step_index += 1
                st.rerun()
            else: go("generate")
    st.markdown('</div>', unsafe_allow_html=True)

def generate_view():
    inject_css()
    st.write("Consulting Strategist Engine...")
    genai.configure(api_key=st.session_state.api_key)
    prompt = build_prompt(st.session_state.answers, "1.0")
    schema, model = generate_schema(prompt)
    pdf_bytes = render_pdf(schema, st.session_state.answers)
    st.session_state.pdf_bytes = pdf_bytes
    go("done")

def done_view():
    inject_css()
    st.success("Brand Bible Fully Executed.")
    st.download_button("Download Premium PDF", st.session_state.pdf_bytes, "Mindbitch_Brand_Manual.pdf", "application/pdf")
    if st.button("Restart New Brand"): go("landing")

def main():
    ss_init()
    if st.session_state.view == "landing": landing_view()
    elif st.session_state.view == "wizard": wizard_view()
    elif st.session_state.view == "generate": generate_view()
    elif st.session_state.view == "done": done_view()

if __name__ == "__main__":
    main()
