# app.py
import time
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF


# =============================================================================
# CONFIG
# =============================================================================
st.set_page_config(
    page_title="Brand Bible Generator",
    page_icon="◻",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PRICE_USD = 99

UNSPLASH = {
    0: "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?q=80&w=1800&auto=format&fit=crop",
    1: "https://images.unsplash.com/photo-1523958203904-cdcb402031fd?q=80&w=1800&auto=format&fit=crop",
    2: "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?q=80&w=1800&auto=format&fit=crop",
    3: "https://images.unsplash.com/photo-1512290923902-8a9f81dc236c?q=80&w=1800&auto=format&fit=crop",
    4: "https://images.unsplash.com/photo-1526498460520-4c246339dccb?q=80&w=1800&auto=format&fit=crop",
    5: "https://images.unsplash.com/photo-1557682260-96773eb01377?q=80&w=1800&auto=format&fit=crop",
    6: "https://images.unsplash.com/photo-1496307653780-42ee777d4833?q=80&w=1800&auto=format&fit=crop",
}

# =============================================================================
# LUXE CSS
# =============================================================================
CSS = """
<style>
  :root{
    --bg0:#070A12;
    --bg1:#0B1220;
    --panel:rgba(255,255,255,0.06);
    --panel2:rgba(255,255,255,0.08);
    --stroke:rgba(255,255,255,0.10);
    --stroke2:rgba(255,255,255,0.14);
    --text:rgba(255,255,255,0.92);
    --muted:rgba(255,255,255,0.62);
    --muted2:rgba(255,255,255,0.46);
    --accent:#2D7DFF;
    --accent2:#0B5CFF;
    --shadow: 0 30px 80px rgba(0,0,0,0.55);
    --radius:28px;
    --radius2:22px;
    --rSmall:16px;
  }

  html, body, [class*="css"]{
    background: radial-gradient(1200px 800px at 20% 20%, rgba(35,125,255,0.22), transparent 60%),
                radial-gradient(1000px 700px at 80% 15%, rgba(255,255,255,0.06), transparent 55%),
                radial-gradient(1000px 900px at 60% 90%, rgba(35,125,255,0.18), transparent 60%),
                linear-gradient(180deg, var(--bg0) 0%, var(--bg1) 100%);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif;
  }

  header, footer{ visibility:hidden !important; }
  section[data-testid="stSidebar"]{ display:none !important; }

  .block-container{
    max-width: 1180px !important;
    padding-top: 36px !important;
    padding-bottom: 64px !important;
  }

  /* Shared */
  .enter{
    animation: enter 650ms cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  @keyframes enter{
    from{ opacity:0; transform: translateY(10px) scale(0.985); }
    to{ opacity:1; transform: translateY(0) scale(1); }
  }

  .fadeOut{
    animation: fadeOut 320ms cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  @keyframes fadeOut{
    from{ opacity:1; transform: translateY(0); }
    to{ opacity:0; transform: translateY(8px); }
  }

  .glass{
    border-radius: var(--radius);
    background: linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.05) 100%);
    border: 1px solid var(--stroke);
    box-shadow: var(--shadow);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
  }

  .heroWrap{
    padding: 44px 44px 38px 44px;
    position: relative;
    overflow: hidden;
  }

  .heroBg{
    position:absolute;
    inset:0;
    background-size:cover;
    background-position:center;
    filter: saturate(1.05) contrast(1.05);
    opacity:0.38;
    transform: scale(1.02);
  }
  .heroShade{
    position:absolute;
    inset:0;
    background: radial-gradient(900px 520px at 30% 20%, rgba(35,125,255,0.36), transparent 60%),
                radial-gradient(900px 600px at 85% 15%, rgba(255,255,255,0.08), transparent 62%),
                linear-gradient(180deg, rgba(0,0,0,0.40) 0%, rgba(0,0,0,0.65) 100%);
  }

  .heroInner{ position:relative; z-index:2; }

  .eyebrow{
    font-size: 11px;
    letter-spacing: 2.2px;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 700;
    margin-bottom: 10px;
  }

  .heroTitle{
    font-size: 54px;
    line-height: 1.05;
    letter-spacing: -1.2px;
    font-weight: 780;
    margin: 0 0 14px 0;
  }

  .heroSub{
    max-width: 860px;
    font-size: 16px;
    line-height: 1.7;
    color: var(--muted);
    margin-bottom: 20px;
  }

  .pillRow{
    display:flex;
    flex-wrap:wrap;
    gap: 10px;
    margin: 18px 0 22px 0;
  }
  .pill{
    padding: 9px 12px;
    border-radius: 999px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.10);
    color: rgba(255,255,255,0.72);
    font-size: 12px;
    font-weight: 600;
  }

  .heroGrid{
    display:grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 18px;
    align-items: stretch;
    margin-top: 14px;
  }

  .cards3{
    display:grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
  }
  .card{
    border-radius: var(--radius2);
    background: rgba(0,0,0,0.28);
    border: 1px solid rgba(255,255,255,0.10);
    padding: 16px 16px 14px 16px;
  }
  .cardT{
    font-size: 13px;
    font-weight: 720;
    color: rgba(255,255,255,0.88);
    margin-bottom: 6px;
  }
  .cardB{
    font-size: 13px;
    line-height: 1.55;
    color: rgba(255,255,255,0.62);
    margin: 0;
  }

  .heroImageFrame{
    border-radius: var(--radius2);
    overflow:hidden;
    border: 1px solid rgba(255,255,255,0.12);
    background: rgba(0,0,0,0.35);
    min-height: 186px;
  }
  .heroImg{
    width:100%;
    height: 186px;
    object-fit: cover;
    opacity:0.86;
    display:block;
    transform: scale(1.02);
  }
  .heroImgShade{
    position:relative;
  }
  .heroImgShade:after{
    content:"";
    position:absolute;
    inset:0;
    background: linear-gradient(180deg, rgba(0,0,0,0.10) 0%, rgba(0,0,0,0.62) 100%);
  }

  .ctaWrap{
    display:flex;
    justify-content:center;
    margin-top: 18px;
  }

  /* Streamlit buttons */
  div.stButton > button{
    background: linear-gradient(180deg, var(--accent) 0%, var(--accent2) 100%) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    border-radius: 999px !important;
    padding: 16px 28px !important;
    font-weight: 760 !important;
    font-size: 16px !important;
    letter-spacing: 0.2px !important;
    box-shadow: 0 16px 36px rgba(35,125,255,0.24) !important;
    transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease !important;
  }
  div.stButton > button:hover{
    transform: translateY(-1px) !important;
    box-shadow: 0 18px 44px rgba(35,125,255,0.32) !important;
    filter: brightness(1.02) !important;
  }

  .btnSecondary div.stButton > button{
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    box-shadow: none !important;
    font-weight: 700 !important;
  }

  .btnGhost div.stButton > button{
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    box-shadow: none !important;
    color: rgba(255,255,255,0.85) !important;
  }

  /* Inputs */
  .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]{
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 18px !important;
    color: rgba(255,255,255,0.92) !important;
    padding: 14px 16px !important;
    font-size: 15px !important;
    transition: box-shadow 160ms ease, border-color 160ms ease !important;
  }
  .stTextArea textarea{ min-height: 110px !important; }

  .stTextInput input:focus, .stTextArea textarea:focus{
    border-color: rgba(35,125,255,0.70) !important;
    box-shadow: 0 0 0 6px rgba(35,125,255,0.18) !important;
  }
  label{
    color: rgba(255,255,255,0.64) !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
  }

  /* Wizard shell */
  .shell{
    padding: 22px 22px 24px 22px;
  }
  .topBar{
    display:flex;
    align-items:center;
    justify-content:space-between;
    margin-bottom: 12px;
  }
  .brandMark{
    display:flex;
    align-items:center;
    gap: 10px;
    color: rgba(255,255,255,0.86);
    font-weight: 760;
    font-size: 13px;
    letter-spacing: 0.2px;
  }
  .markDot{
    width: 12px;
    height: 12px;
    border-radius: 4px;
    background: rgba(255,255,255,0.86);
    box-shadow: 0 10px 18px rgba(0,0,0,0.4);
  }
  .topHint{
    color: rgba(255,255,255,0.46);
    font-size: 12px;
  }

  .dotRow{ display:flex; gap:8px; align-items:center; }
  .dot{
    width: 7px; height: 7px;
    border-radius: 99px;
    background: rgba(255,255,255,0.20);
  }
  .dot.on{
    background: rgba(35,125,255,0.92);
    box-shadow: 0 10px 18px rgba(35,125,255,0.30);
  }

  .rail{
    border-radius: var(--radius2);
    background: rgba(0,0,0,0.32);
    border: 1px solid rgba(255,255,255,0.10);
    padding: 18px 18px 16px 18px;
    min-height: 260px;
  }
  .secTag{
    display:inline-flex;
    padding: 7px 10px;
    border-radius: 999px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.10);
    color: rgba(255,255,255,0.64);
    font-size: 11px;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    font-weight: 800;
  }
  .bigNum{
    font-size: 46px;
    line-height: 1;
    margin: 14px 0 8px 0;
    font-weight: 850;
    letter-spacing: -0.8px;
    color: rgba(255,255,255,0.90);
  }
  .railTitle{
    font-size: 18px;
    font-weight: 820;
    margin-bottom: 10px;
  }
  .railCopy{
    font-size: 13px;
    line-height: 1.55;
    color: rgba(255,255,255,0.62);
    margin: 0 0 14px 0;
  }
  .railMini{
    margin-top: 6px;
    padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,0.08);
    font-size: 12px;
    color: rgba(255,255,255,0.50);
    line-height: 1.5;
  }

  .surface{
    border-radius: var(--radius2);
    background: rgba(0,0,0,0.26);
    border: 1px solid rgba(255,255,255,0.10);
    padding: 18px;
    min-height: 260px;
  }
  .surfaceTitle{
    font-size: 18px;
    font-weight: 840;
    margin-bottom: 6px;
  }
  .surfaceDesc{
    font-size: 13px;
    color: rgba(255,255,255,0.60);
    line-height: 1.6;
    margin-bottom: 12px;
  }
  .surfaceDivider{
    height: 1px;
    background: rgba(255,255,255,0.08);
    margin: 14px 0 0 0;
  }

  .whisper{
    position: relative;
    border-radius: var(--radius2);
    overflow:hidden;
    border: 1px solid rgba(255,255,255,0.10);
    min-height: 260px;
    background: rgba(0,0,0,0.30);
  }
  .whisperBg{
    position:absolute;
    inset:0;
    background-size:cover;
    background-position:center;
    opacity:0.34;
    transform: scale(1.02);
    filter: saturate(1.05) contrast(1.05);
  }
  .whisperShade{
    position:absolute;
    inset:0;
    background: linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.72) 100%);
  }
  .whisperInner{
    position: relative;
    z-index: 2;
    padding: 16px 16px 14px 16px;
  }
  .whisperTag{
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.56);
    font-weight: 850;
    margin-bottom: 8px;
  }
  .whisperTitle{
    font-size: 14px;
    font-weight: 820;
    color: rgba(255,255,255,0.88);
    margin-bottom: 8px;
  }
  .whisperBody{
    font-size: 12px;
    line-height: 1.55;
    color: rgba(255,255,255,0.58);
    margin: 0 0 10px 0;
  }
  .chipRow{ display:flex; flex-wrap:wrap; gap: 8px; margin-bottom: 10px; }
  .chip{
    padding: 7px 10px;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(255,255,255,0.06);
    font-size: 11px;
    color: rgba(255,255,255,0.68);
    font-weight: 720;
  }
  .exampleBox{
    padding: 10px 12px;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(0,0,0,0.26);
    font-size: 12px;
    color: rgba(255,255,255,0.70);
    line-height: 1.5;
  }

  .formBlock{
    margin-top: 14px;
    padding: 16px 16px 14px 16px;
    border-radius: var(--radius2);
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(0,0,0,0.22);
  }

  .footerRow{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap: 12px;
    margin-top: 14px;
  }
  .tinyNote{
    font-size: 12px;
    color: rgba(255,255,255,0.50);
    line-height: 1.45;
  }

  .priceCard{
    border-radius: var(--radius2);
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(0,0,0,0.22);
    padding: 16px;
  }
  .priceT{
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.58);
    font-weight: 850;
  }
  .priceV{
    margin-top: 8px;
    font-size: 44px;
    line-height: 1;
    font-weight: 900;
    letter-spacing: -1px;
    color: rgba(255,255,255,0.92);
  }
  .priceB{
    margin-top: 10px;
    font-size: 13px;
    color: rgba(255,255,255,0.58);
    line-height: 1.55;
  }

  /* Keep the app clean */
  [data-testid="stDecoration"]{ display:none !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# =============================================================================
# STATE
# =============================================================================
DEFAULTS = {
    "view": "landing",          # landing | wizard | result
    "step": 1,                  # 1..6
    "transition": False,
    "payment_ok": False,
    "generated_md": "",
    "site_signals": "",

    # inputs
    "api_key": "",
    "brand_name": "",
    "industry": "",
    "website": "",

    "audience": "",
    "use_context": "",
    "desired_outcome": "",

    "offer": "",
    "differentiators": "",
    "proof": "",

    "voice_traits": [],
    "voice_refs": "",
    "words_to_use": "",
    "words_to_avoid": "",

    "visual_style": "",
    "color_mood": "",
    "typography_mood": "",
    "imagery_mood": "",
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# =============================================================================
# HELPERS
# =============================================================================
def set_transition(next_view: Optional[str] = None, next_step: Optional[int] = None):
    st.session_state.transition = True
    st.session_state._next_view = next_view
    st.session_state._next_step = next_step


def run_transition_if_needed():
    if st.session_state.get("transition", False):
        st.markdown('<div class="fadeOut">', unsafe_allow_html=True)
        st.markdown(" ", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        time.sleep(0.20)
        st.session_state.transition = False
        nv = st.session_state.pop("_next_view", None)
        ns = st.session_state.pop("_next_step", None)
        if nv is not None:
            st.session_state.view = nv
        if ns is not None:
            st.session_state.step = ns
        st.rerun()


def sanitize_no_fancy_dashes(text: str) -> str:
    # Avoid en dash and em dash. Keep simple ASCII output.
    return (
        text.replace("\u2013", " ")
            .replace("\u2014", " ")
            .replace("–", " ")
            .replace("—", " ")
    )


def sanitize_pdf_text(text: str) -> str:
    # Replace common unicode quotes and ellipsis and dashes for latin1.
    m = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2026": "...",
        "\u2013": " ", "\u2014": " ",
        "–": " ", "—": " ",
    }
    for a, b in m.items():
        text = text.replace(a, b)
    text = sanitize_no_fancy_dashes(text)
    return text.encode("latin-1", "replace").decode("latin-1")


def fetch_site_signals(url: str, limit_chars: int = 2600) -> str:
    if not url or not url.strip():
        return ""
    u = url.strip()
    if not re.match(r"^https?://", u):
        u = "https://" + u

    try:
        r = requests.get(u, timeout=7, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        title = (soup.title.string.strip() if soup.title and soup.title.string else "").strip()
        desc_tag = soup.find("meta", attrs={"name": "description"})
        desc = (desc_tag.get("content", "").strip() if desc_tag else "").strip()

        h1 = soup.find("h1")
        h1t = h1.get_text(" ", strip=True) if h1 else ""

        # Light text extraction
        text = soup.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        text = text[:limit_chars]

        bits = []
        if title:
            bits.append(f"Title: {title}")
        if desc:
            bits.append(f"Description: {desc}")
        if h1t:
            bits.append(f"H1: {h1t}")
        if text:
            bits.append(f"Body sample: {text}")

        out = "\n".join(bits).strip()
        out = sanitize_no_fancy_dashes(out)
        return out
    except Exception:
        return ""


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(30, 30, 30)
        self.cell(0, 10, self.header_title, 0, 1, "C")


def create_pdf_from_markdown(md: str, brand_name: str) -> bytes:
    md = sanitize_no_fancy_dashes(md)

    pdf = PDF()
    pdf.header_title = sanitize_pdf_text(f"{brand_name.upper()}  BRAND SYSTEM")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.set_text_color(18, 18, 18)
    pdf.set_font("Helvetica", "", 11)

    for raw_line in md.split("\n"):
        line = raw_line.rstrip()
        s = sanitize_pdf_text(line)

        if line.startswith("# "):
            pdf.ln(6)
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(0, 10, sanitize_pdf_text(line[2:]))
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 11)
        elif line.startswith("## "):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(0, 8, sanitize_pdf_text(line[3:]))
            pdf.ln(1)
            pdf.set_font("Helvetica", "", 11)
        elif line.startswith("### "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 7, sanitize_pdf_text(line[4:]))
            pdf.ln(1)
            pdf.set_font("Helvetica", "", 11)
        else:
            if s.strip() == "":
                pdf.ln(2)
            else:
                pdf.multi_cell(0, 5.5, s)

    return pdf.output(dest="S").encode("latin-1")


def validate_step(step: int) -> Tuple[bool, str]:
    if step == 1:
        if not st.session_state.brand_name.strip():
            return False, "Add a brand name."
        if not st.session_state.industry.strip():
            return False, "Add an industry."
        if not st.session_state.api_key.strip():
            return False, "Add your Gemini API key."
        return True, ""
    if step == 2:
        if not st.session_state.audience.strip():
            return False, "Describe the audience."
        if not st.session_state.desired_outcome.strip():
            return False, "Describe the desired outcome."
        return True, ""
    if step == 3:
        if not st.session_state.offer.strip():
            return False, "Describe the offer."
        if not st.session_state.differentiators.strip():
            return False, "Add differentiators."
        if not st.session_state.proof.strip():
            return False, "Add proof."
        return True, ""
    if step == 4:
        if not st.session_state.voice_traits:
            return False, "Pick at least one voice trait."
        return True, ""
    if step == 5:
        if not st.session_state.visual_style.strip():
            return False, "Choose a visual style direction."
        return True, ""
    return True, ""


def fill_demo():
    st.session_state.brand_name = "Oura"
    st.session_state.industry = "Health tech"
    st.session_state.website = "ouraring.com"
    st.session_state.audience = "Founders and high performers who care about recovery, sleep, and consistency."
    st.session_state.use_context = "They check progress in the morning and adjust habits across the day."
    st.session_state.desired_outcome = "They want clarity without clinical overload, and momentum they can feel."
    st.session_state.offer = "A ring and app that turns sleep and recovery signals into simple daily guidance."
    st.session_state.differentiators = "Comfort first, insight that feels human, exceptional sleep accuracy, habit building cadence."
    st.session_state.proof = "Published validation, strong retention, trusted by athletes, clear product design language."
    st.session_state.voice_traits = ["Calm", "Precise", "Human"]
    st.session_state.voice_refs = "Jony Ive and a warm coach who respects your time."
    st.session_state.words_to_use = "clear, steady, measured, recovery, signal, guide, calm, focus"
    st.session_state.words_to_avoid = "revolutionary, disruptive, insane, crushing, hacks"
    st.session_state.visual_style = "Modern minimal"
    st.session_state.color_mood = "Deep dark base, cool blue accent, soft neutrals"
    st.session_state.typography_mood = "Clean sans, strong hierarchy, generous spacing"
    st.session_state.imagery_mood = "Close detail, materials, low noise lifestyle, calm light"


def render_shell_header():
    total_steps = 6
    dots = []
    for i in range(1, total_steps + 1):
        dots.append(f'<div class="dot {"on" if i == st.session_state.step else ""}"></div>')
    dots_html = "".join(dots)

    st.markdown('<div class="shell glass enter">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="topBar">
          <div class="brandMark"><div class="markDot"></div> Brand Bible Generator</div>
          <div class="dotRow">{dots_html}</div>
        </div>
        <div class="topHint">A guided brand interview that outputs a client ready document.</div>
        """,
        unsafe_allow_html=True,
    )


def close_shell():
    st.markdown("</div>", unsafe_allow_html=True)


def render_three_panels(
    section_no: int,
    rail_title: str,
    rail_copy: str,
    surface_title: str,
    surface_desc: str,
    guide_title: str,
    guide_body: str,
    chips: List[str],
    example: str,
    image_url: str,
):
    left, mid, right = st.columns([0.95, 1.65, 0.95], gap="large")

    with left:
        st.markdown(
            f"""
            <div class="rail enter">
              <div class="secTag">SECTION {section_no}</div>
              <div class="bigNum">{section_no:02d}</div>
              <div class="railTitle">{rail_title}</div>
              <p class="railCopy">{rail_copy}</p>
              <div class="railMini">Answer like you are briefing design and copy at the same time. Specific beats clever.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with mid:
        st.markdown(
            f"""
            <div class="surface enter">
              <div class="surfaceTitle">{surface_title}</div>
              <div class="surfaceDesc">{surface_desc}</div>
              <div class="surfaceDivider"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        chips_html = "".join([f'<div class="chip">{c}</div>' for c in chips])
        st.markdown(
            f"""
            <div class="whisper enter">
              <div class="whisperBg" style="background-image:url('{image_url}');"></div>
              <div class="whisperShade"></div>
              <div class="whisperInner">
                <div class="whisperTag">GUIDE</div>
                <div class="whisperTitle">{guide_title}</div>
                <p class="whisperBody">{guide_body}</p>
                <div class="chipRow">{chips_html}</div>
                <div class="exampleBox">{example}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return left, mid, right


def build_prompt() -> str:
    name = st.session_state.brand_name.strip()
    industry = st.session_state.industry.strip()
    website = st.session_state.website.strip()
    site_signals = st.session_state.site_signals.strip()

    audience = st.session_state.audience.strip()
    use_context = st.session_state.use_context.strip()
    desired_outcome = st.session_state.desired_outcome.strip()

    offer = st.session_state.offer.strip()
    diffs = st.session_state.differentiators.strip()
    proof = st.session_state.proof.strip()

    voice_traits = ", ".join(st.session_state.voice_traits)
    voice_refs = st.session_state.voice_refs.strip()
    w_use = st.session_state.words_to_use.strip()
    w_avoid = st.session_state.words_to_avoid.strip()

    visual_style = st.session_state.visual_style.strip()
    color_mood = st.session_state.color_mood.strip()
    typography_mood = st.session_state.typography_mood.strip()
    imagery_mood = st.session_state.imagery_mood.strip()

    # Keep output crisp, usable, and non generic. Avoid fancy dash characters in output.
    prompt = f"""
You are a world class brand strategist and brand designer.
You write like a legendary agency, but you stay practical.
Your job is to produce a premium brand bible that a team can use immediately.

Hard constraints
1. No en dash and no em dash characters in your output.
2. Avoid fluffy claims. Everything must be defendable.
3. Give examples, do and do not lists, and templates.
4. Write in clean Markdown. Short sections. Strong hierarchy.

Brand inputs
Brand name: {name}
Industry: {industry}
Website: {website}

Website signals
{site_signals if site_signals else "No site signals provided."}

Audience and context
Audience: {audience}
Context: {use_context}
Desired outcome: {desired_outcome}

Offer and proof
Offer: {offer}
Differentiators: {diffs}
Proof: {proof}

Voice
Traits: {voice_traits}
References: {voice_refs}
Words to use: {w_use}
Words to avoid: {w_avoid}

Visual direction
Style direction: {visual_style}
Color mood: {color_mood}
Typography mood: {typography_mood}
Imagery mood: {imagery_mood}

Deliverable structure
# {name.upper()}
## Executive summary
## Positioning
### Category
### Audience
### Defendable edge
### Positioning statement
## Messaging system
### Message pillars
### Proof library
### Objections and answers
## Voice system
### Voice principles
### Tone slider
### Do and do not table
### Copy templates
## Visual direction
### Art direction keywords
### Color direction
### Typography direction
### Imagery direction
### Layout rules
## Quick start page
### What to do next in one week

Make it feel premium and specific to the inputs.
"""
    return sanitize_no_fancy_dashes(prompt)


def generate_brand_bible_md() -> str:
    genai.configure(api_key=st.session_state.api_key.strip())
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = build_prompt()
    response = model.generate_content(prompt)
    out = response.text or ""
    out = sanitize_no_fancy_dashes(out)
    return out.strip()


# =============================================================================
# LANDING
# =============================================================================
def landing():
    bg = UNSPLASH[0]
    st.markdown(
        f"""
        <div class="glass heroWrap enter">
          <div class="heroBg" style="background-image:url('{bg}');"></div>
          <div class="heroShade"></div>
          <div class="heroInner">
            <div class="eyebrow">BRAND SYSTEM GENERATOR</div>
            <div class="heroTitle">Make your brand bible feel designed.</div>
            <div class="heroSub">
              A guided editorial workflow that captures strategy, voice, and visual direction, then produces a polished PDF.
              Built for founders, teams, and agencies that want alignment without the usual noise.
            </div>

            <div class="pillRow">
              <div class="pill">Editorial flow</div>
              <div class="pill">Website signals</div>
              <div class="pill">Blueprint first</div>
              <div class="pill">PDF output</div>
              <div class="pill">One time price {PRICE_USD}</div>
            </div>

            <div class="heroGrid">
              <div class="cards3">
                <div class="card">
                  <div class="cardT">Strategy</div>
                  <p class="cardB">Positioning, differentiators, and reasons to believe your team can defend.</p>
                </div>
                <div class="card">
                  <div class="cardT">Voice</div>
                  <p class="cardB">Principles, do and do not language, and templates writers can actually use.</p>
                </div>
                <div class="card">
                  <div class="cardT">Visual direction</div>
                  <p class="cardB">Keywords, avoids, and layout rules that designers trust.</p>
                </div>
              </div>

              <div class="heroImageFrame">
                <div class="heroImgShade">
                  <img class="heroImg" src="{UNSPLASH[6]}" alt="Preview" />
                </div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ctaWrap">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("Start"):
            set_transition(next_view="wizard", next_step=1)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

    cols = st.columns([1, 1, 1], gap="large")
    with cols[0]:
        st.markdown(
            """
            <div class="card enter">
              <div class="cardT">Designed experience</div>
              <p class="cardB">Short prompts. Clear context. No clutter. Inputs stay readable.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            """
            <div class="card enter">
              <div class="cardT">Premium output</div>
              <p class="cardB">A PDF built for sharing with a team or client. Clean hierarchy, usable rules.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            """
            <div class="card enter">
              <div class="cardT">Signals not vibes</div>
              <p class="cardB">Optional website parsing to ground the tone and claims in real language.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =============================================================================
# WIZARD
# =============================================================================
VOICE_TRAITS = ["Calm", "Bold", "Playful", "Human", "Precise", "Warm", "Direct", "Minimal", "Elevated", "Technical"]
VISUAL_STYLES = ["Modern minimal", "Editorial luxe", "Tech clean", "Warm craft", "Bold geometric", "Classic serif"]


def wizard_step_1():
    render_shell_header()
    render_three_panels(
        section_no=1,
        rail_title="Signals.",
        rail_copy="Ground the work. A real name and a real category create better decisions than extra adjectives.",
        surface_title="Brand identity signals",
        surface_desc="Name and category first. Website is optional. We use it as a signal source.",
        guide_title="Keep it crisp",
        guide_body="If you have a website, add it. If not, skip it. Clarity beats decoration.",
        chips=["Name", "Industry", "Website"],
        example="Example: Oura, health tech, ouraring.com",
        image_url=UNSPLASH[1],
    )

    st.markdown('<div class="formBlock enter">', unsafe_allow_html=True)
    st.text_input("Brand name", key="brand_name", placeholder="Example Oura")
    st.text_input("Industry", key="industry", placeholder="Example health tech")
    st.text_input("Website (optional)", key="website", placeholder="Example ouraring.com")
    st.text_input("Gemini API key", key="api_key", type="password", placeholder="Paste your key")

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.6])
    with c1:
        st.markdown('<div class="btnSecondary">', unsafe_allow_html=True)
        if st.button("Demo"):
            fill_demo()
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="btnGhost">', unsafe_allow_html=True)
        if st.button("Back"):
            set_transition(next_view="landing")
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        if st.button("Continue"):
            ok, msg = validate_step(1)
            if not ok:
                st.warning(msg)
            else:
                # fetch site signals once here
                st.session_state.site_signals = fetch_site_signals(st.session_state.website)
                set_transition(next_step=2)

    st.markdown("</div>", unsafe_allow_html=True)
    close_shell()


def wizard_step_2():
    render_shell_header()
    render_three_panels(
        section_no=2,
        rail_title="Outcome.",
        rail_copy="Positioning starts with a real buyer in a real situation. Name the context. Name the outcome.",
        surface_title="Audience and desired outcome",
        surface_desc="Describe who this is for, when they need you, and what success feels like.",
        guide_title="Answer like a brief",
        guide_body="Write concrete context. What is happening. What is at stake. What does better look like.",
        chips=["Role", "Context", "Outcome"],
        example="Audience: product founders. Context: shipping a launch. Outcome: clarity and speed without chaos.",
        image_url=UNSPLASH[2],
    )

    st.markdown('<div class="formBlock enter">', unsafe_allow_html=True)
    st.text_area("Audience", key="audience", placeholder="Who is it for. Include role, maturity, and what they care about.")
    st.text_area("Use context", key="use_context", placeholder="When do they reach for you. What is happening around them.")
    st.text_area("Desired outcome", key="desired_outcome", placeholder="Name the result, not the feature. What changes for them.")

    a, b, c = st.columns([1, 2, 1.4])
    with a:
        st.markdown('<div class="btnGhost">', unsafe_allow_html=True)
        if st.button("Back"):
            set_transition(next_step=1)
        st.markdown("</div>", unsafe_allow_html=True)

    with c:
        if st.button("Continue"):
            ok, msg = validate_step(2)
            if not ok:
                st.warning(msg)
            else:
                set_transition(next_step=3)

    st.markdown("</div>", unsafe_allow_html=True)
    close_shell()


def wizard_step_3():
    render_shell_header()
    render_three_panels(
        section_no=3,
        rail_title="Edge.",
        rail_copy="A brand claim is only premium if it is defendable. Give your edge, then give proof.",
        surface_title="Offer, differentiators, proof",
        surface_desc="Write what you provide, what makes it different, and why a skeptic should believe it.",
        guide_title="Defendable beats loud",
        guide_body="Proof can be metrics, process, expertise, validation, or product details. Specific wins.",
        chips=["Offer", "Edge", "Proof"],
        example="Offer: the product. Edge: why it is different. Proof: evidence and credibility.",
        image_url=UNSPLASH[3],
    )

    st.markdown('<div class="formBlock enter">', unsafe_allow_html=True)
    st.text_area("Offer", key="offer", placeholder="Describe what you provide in one clear paragraph.")
    st.text_area("Differentiators", key="differentiators", placeholder="List what you do better. Keep it concrete.")
    st.text_area("Proof", key="proof", placeholder="Why believe it. Evidence, process, expertise, validation.")

    a, b, c = st.columns([1, 2, 1.4])
    with a:
        st.markdown('<div class="btnGhost">', unsafe_allow_html=True)
        if st.button("Back"):
            set_transition(next_step=2)
        st.markdown("</div>", unsafe_allow_html=True)

    with c:
        if st.button("Continue"):
            ok, msg = validate_step(3)
            if not ok:
                st.warning(msg)
            else:
                set_transition(next_step=4)

    st.markdown("</div>", unsafe_allow_html=True)
    close_shell()


def wizard_step_4():
    render_shell_header()
    render_three_panels(
        section_no=4,
        rail_title="Voice.",
        rail_copy="Voice is a system. Principles, do and do not language, and templates that scale.",
        surface_title="Voice rules",
        surface_desc="Choose traits, then add references and guardrails. This becomes your writing system.",
        guide_title="Make it usable",
        guide_body="If a writer joins tomorrow, your rules should keep them on brand in one hour.",
        chips=["Traits", "References", "Words"],
        example="Traits: calm, precise. Use: clear, measured. Avoid: hype, jargon, empty superlatives.",
        image_url=UNSPLASH[4],
    )

    st.markdown('<div class="formBlock enter">', unsafe_allow_html=True)
    st.multiselect("Voice traits", options=VOICE_TRAITS, key="voice_traits")
    st.text_area("Voice references (optional)", key="voice_refs", placeholder="Two references help. One for tone, one for clarity.")
    st.text_area("Words to use", key="words_to_use", placeholder="A short list is enough.")
    st.text_area("Words to avoid", key="words_to_avoid", placeholder="Words that make you sound fake, generic, or off brand.")

    a, b, c = st.columns([1, 2, 1.4])
    with a:
        st.markdown('<div class="btnGhost">', unsafe_allow_html=True)
        if st.button("Back"):
            set_transition(next_step=3)
        st.markdown("</div>", unsafe_allow_html=True)

    with c:
        if st.button("Continue"):
            ok, msg = validate_step(4)
            if not ok:
                st.warning(msg)
            else:
                set_transition(next_step=5)

    st.markdown("</div>", unsafe_allow_html=True)
    close_shell()


def wizard_step_5():
    render_shell_header()
    render_three_panels(
        section_no=5,
        rail_title="Visual.",
        rail_copy="Design direction is not a mood board. It is constraints, rules, and keywords designers trust.",
        surface_title="Visual direction",
        surface_desc="Pick a style direction and describe color, type, imagery, and layout behavior.",
        guide_title="Describe behavior",
        guide_body="How should layouts feel. How much density. How much contrast. What to avoid.",
        chips=["Style", "Color", "Type", "Imagery"],
        example="Style: editorial luxe. Color: deep base, soft neutrals, one accent. Type: strong hierarchy.",
        image_url=UNSPLASH[5],
    )

    st.markdown('<div class="formBlock enter">', unsafe_allow_html=True)
    st.selectbox("Style direction", options=VISUAL_STYLES, key="visual_style")
    st.text_area("Color mood", key="color_mood", placeholder="Base, accent, and overall contrast level.")
    st.text_area("Typography mood", key="typography_mood", placeholder="Sans or serif, hierarchy, spacing, weight.")
    st.text_area("Imagery mood", key="imagery_mood", placeholder="Subjects, lighting, composition, texture, what to avoid.")

    a, b, c = st.columns([1, 2, 1.4])
    with a:
        st.markdown('<div class="btnGhost">', unsafe_allow_html=True)
        if st.button("Back"):
            set_transition(next_step=4)
        st.markdown("</div>", unsafe_allow_html=True)

    with c:
        if st.button("Continue"):
            ok, msg = validate_step(5)
            if not ok:
                st.warning(msg)
            else:
                set_transition(next_step=6)

    st.markdown("</div>", unsafe_allow_html=True)
    close_shell()


def wizard_step_6():
    render_shell_header()
    render_three_panels(
        section_no=6,
        rail_title="Synthesis.",
        rail_copy="We generate the brand bible, then you export a polished PDF.",
        surface_title="Review and unlock",
        surface_desc="One time purchase. Then we synthesize your brand system and produce the document.",
        guide_title="What you get",
        guide_body="Positioning, messaging, voice rules, visual direction, and a quick start plan.",
        chips=["Strategy", "Voice", "Visual", "PDF"],
        example="Tip: keep your inputs concrete. The output becomes a tool your team can use immediately.",
        image_url=UNSPLASH[6],
    )

    st.markdown('<div class="formBlock enter">', unsafe_allow_html=True)
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.markdown(
            f"""
            <div class="priceCard enter">
              <div class="priceT">TOTAL</div>
              <div class="priceV">${PRICE_USD}</div>
              <div class="priceB">One time strategic investment. Includes PDF export.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

        if not st.session_state.payment_ok:
            if st.button("Unlock and generate"):
                with st.spinner("Authorizing..."):
                    time.sleep(1.1)
                st.session_state.payment_ok = True
                st.success("Access verified.")
        else:
            st.success("Access verified.")

    with right:
        st.markdown(
            """
            <div class="priceCard enter">
              <div class="priceT">CHECK</div>
              <div class="tinyNote">
                Brand name, audience, edge, voice, and visual direction are included.
                Website signals are optional and used only as cues.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="footerRow">', unsafe_allow_html=True)
    l, r = st.columns([1, 1])
    with l:
        st.markdown('<div class="btnGhost">', unsafe_allow_html=True)
        if st.button("Back"):
            set_transition(next_step=5)
        st.markdown("</div>", unsafe_allow_html=True)

    with r:
        if st.session_state.payment_ok:
            if st.button("Synthesize PDF"):
                set_transition(next_view="result")
        else:
            st.markdown(
                '<div class="tinyNote">Unlock access to generate the document.</div>',
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    close_shell()


def wizard():
    step = int(st.session_state.step)
    if step == 1:
        wizard_step_1()
    elif step == 2:
        wizard_step_2()
    elif step == 3:
        wizard_step_3()
    elif step == 4:
        wizard_step_4()
    elif step == 5:
        wizard_step_5()
    else:
        wizard_step_6()


# =============================================================================
# RESULT
# =============================================================================
def result():
    st.markdown(
        """
        <div class="glass heroWrap enter">
          <div class="heroShade"></div>
          <div class="heroInner">
            <div class="eyebrow">SYNTHESIS</div>
            <div class="heroTitle">Your brand system is being written.</div>
            <div class="heroSub">
              We are generating the brand bible and preparing a PDF export.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.generated_md:
        with st.spinner("Synthesizing..."):
            try:
                md = generate_brand_bible_md()
                st.session_state.generated_md = md
            except Exception as e:
                st.error(f"Generation error: {e}")
                st.markdown('<div class="btnGhost">', unsafe_allow_html=True)
                if st.button("Back to wizard"):
                    set_transition(next_view="wizard", next_step=6)
                st.markdown("</div>", unsafe_allow_html=True)
                return

    md = st.session_state.generated_md
    st.success("Generated.")

    c1, c2 = st.columns([1.1, 0.9], gap="large")
    with c1:
        st.markdown('<div class="glass enter" style="padding:18px;">', unsafe_allow_html=True)
        st.markdown("### Preview")
        st.markdown(md)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="glass enter" style="padding:18px;">', unsafe_allow_html=True)
        st.markdown("### Export")
        pdf_bytes = create_pdf_from_markdown(md, st.session_state.brand_name.strip() or "Brand")
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"{(st.session_state.brand_name.strip() or 'Brand')}_Brand_Bible.pdf",
            mime="application/pdf",
        )

        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

        b1, b2 = st.columns([1, 1])
        with b1:
            st.markdown('<div class="btnGhost">', unsafe_allow_html=True)
            if st.button("New project"):
                for k, v in DEFAULTS.items():
                    st.session_state[k] = v
                set_transition(next_view="landing")
            st.markdown("</div>", unsafe_allow_html=True)

        with b2:
            st.markdown('<div class="btnSecondary">', unsafe_allow_html=True)
            if st.button("Back to review"):
                set_transition(next_view="wizard", next_step=6)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# ROUTER
# =============================================================================
run_transition_if_needed()

if st.session_state.view == "landing":
    landing()
elif st.session_state.view == "wizard":
    wizard()
else:
    result()
