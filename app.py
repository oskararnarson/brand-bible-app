import time
import re
import requests
from bs4 import BeautifulSoup
import concurrent.futures

import streamlit as st
import google.generativeai as genai
from fpdf import FPDF


# -----------------------------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Brand Bible Generator",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# -----------------------------------------------------------------------------
# CSS
# -----------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

body {
  background:
    radial-gradient(1200px 800px at 20% 40%, rgba(0, 120, 255, 0.18), rgba(0,0,0,0) 60%),
    radial-gradient(900px 600px at 80% 20%, rgba(255,255,255,0.06), rgba(0,0,0,0) 55%),
    #0b0d11;
  color: #e9edf5;
}

section[data-testid="stSidebar"] { display: none !important; }
header, footer { visibility: hidden !important; }

.block-container{
  max-width: 1220px !important;
  padding-top: 2.2rem;
  padding-bottom: 4rem;
}

/* Panels */
.glass {
  background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 28px;
  box-shadow: 0 30px 120px rgba(0,0,0,0.55);
  backdrop-filter: blur(16px);
}

.panel {
  background: linear-gradient(180deg, rgba(10,12,16,0.88), rgba(10,12,16,0.72));
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 22px;
  box-shadow: 0 18px 60px rgba(0,0,0,0.45);
}

.panel-soft {
  background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.03));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 22px;
}

/* Typography */
.h-eyebrow{
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(235,240,255,0.65);
}

.h-title{
  font-size: 58px;
  line-height: 1.05;
  letter-spacing: -0.03em;
  font-weight: 700;
  margin: 10px 0 10px 0;
}

.h-sub{
  max-width: 860px;
  font-size: 16px;
  line-height: 1.7;
  color: rgba(235,240,255,0.72);
  margin-bottom: 18px;
}

.small-muted{
  font-size: 12px;
  line-height: 1.6;
  color: rgba(235,240,255,0.60);
}

/* Pills */
.pills {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.pill {
  font-size: 12px;
  padding: 9px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  color: rgba(235,240,255,0.70);
}

/* Landing hero */
.hero-wrap{
  padding: 54px 54px 42px 54px;
  position: relative;
  overflow: hidden;
}

.hero-bg{
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(90deg, rgba(11,13,17,0.92) 0%, rgba(11,13,17,0.70) 52%, rgba(11,13,17,0.20) 100%),
    url("https://images.unsplash.com/photo-1521737604893-d14cc237f11d?q=80&w=2400&auto=format&fit=crop");
  background-size: cover;
  background-position: center;
  filter: saturate(0.9) contrast(1.05);
  transform: scale(1.03);
}

.hero-content{
  position: relative;
  z-index: 2;
}

.hero-grid{
  margin-top: 18px;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 18px;
}

.hero-cards{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.card{
  padding: 16px 16px 14px 16px;
  border-radius: 18px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
}

.cardT{
  font-size: 13px;
  font-weight: 600;
  color: rgba(235,240,255,0.90);
  margin-bottom: 6px;
}

.cardB{
  font-size: 12px;
  line-height: 1.6;
  color: rgba(235,240,255,0.68);
}

/* Inputs */
label {
  font-size: 11px !important;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(235,240,255,0.55) !important;
  font-weight: 600 !important;
}

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]{
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  border-radius: 16px !important;
  color: rgba(235,240,255,0.88) !important;
}

.stTextInput input:focus, .stTextArea textarea:focus{
  border: 1px solid rgba(28,125,255,0.75) !important;
  box-shadow: 0 0 0 5px rgba(28,125,255,0.18) !important;
}

/* Buttons */
div.stButton > button {
  background: linear-gradient(180deg, #1c7dff, #0d5fe9);
  color: white;
  font-size: 16px;
  font-weight: 650;
  padding: 14px 26px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: 0 18px 45px rgba(0,110,255,0.35);
  transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
  white-space: nowrap !important;
  min-width: 160px;
}

div.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 22px 60px rgba(0,110,255,0.45);
  filter: brightness(1.03);
}

.secondaryBtn div.stButton > button{
  background: rgba(255,255,255,0.06) !important;
  box-shadow: none !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  color: rgba(235,240,255,0.88) !important;
}

.dangerBtn div.stButton > button{
  background: rgba(255,255,255,0.03) !important;
  box-shadow: none !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  color: rgba(235,240,255,0.72) !important;
}

/* Special landing Start button */
.startBig div.stButton > button{
  font-size: 18px !important;
  padding: 18px 34px !important;
  min-width: 240px !important;
  box-shadow: 0 22px 70px rgba(0,110,255,0.42) !important;
}

/* Wizard top bar */
.wizardTop{
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.07);
  margin-bottom: 18px;
}

.brandDot{
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.85);
  box-shadow: 0 0 0 6px rgba(255,255,255,0.06);
  display:inline-block;
  margin-right: 10px;
}

.topTitle{
  font-size: 13px;
  font-weight: 600;
  color: rgba(235,240,255,0.92);
}

.topSub{
  font-size: 12px;
  color: rgba(235,240,255,0.60);
}

.dotRow{
  display:flex;
  gap: 8px;
}

.stepDot{
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: rgba(235,240,255,0.18);
  border: 1px solid rgba(255,255,255,0.12);
}

.stepDot.active{
  background: rgba(28,125,255,0.95);
  border: 1px solid rgba(28,125,255,0.95);
  box-shadow: 0 0 0 6px rgba(28,125,255,0.18);
}

/* Section card */
.sectionCard{
  padding: 22px;
}

.sectionTag{
  display:inline-flex;
  align-items:center;
  gap: 8px;
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(235,240,255,0.65);
  padding: 10px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
}

.sectionNum{
  font-size: 54px;
  font-weight: 700;
  margin: 16px 0 4px 0;
  letter-spacing: -0.02em;
}

.sectionName{
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 10px;
}

.sectionDesc{
  font-size: 13px;
  line-height: 1.7;
  color: rgba(235,240,255,0.68);
  max-width: 320px;
}

.sectionTip{
  margin-top: 16px;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(235,240,255,0.52);
}

/* Form panel */
.formPanel{
  padding: 22px;
}

.formTitle{
  font-size: 18px;
  font-weight: 700;
  color: rgba(235,240,255,0.92);
}

.formSub{
  font-size: 12px;
  line-height: 1.6;
  color: rgba(235,240,255,0.62);
  margin-top: 6px;
  margin-bottom: 14px;
}

.hr{
  height: 1px;
  background: rgba(255,255,255,0.07);
  margin: 14px 0 18px 0;
}

/* Guide card */
.guideCard{
  padding: 18px;
  position: relative;
  overflow: hidden;
}

.guideBg{
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  filter: saturate(0.9) contrast(1.05);
}

.guideContent{
  position: relative;
  z-index: 2;
}

.guideTag{
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(235,240,255,0.62);
  margin-bottom: 10px;
}

.guideTitle{
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 8px;
}

.guideText{
  font-size: 12px;
  line-height: 1.65;
  color: rgba(235,240,255,0.72);
}

.chips{
  display:flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.chip{
  font-size: 11px;
  padding: 7px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  color: rgba(235,240,255,0.74);
}

/* Bottom action bar */
.actionBar{
  margin-top: 18px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(255,255,255,0.07);
  background: rgba(255,255,255,0.03);
}

/* Transition overlay */
@keyframes fadeOverlay {
  0% { opacity: 0; transform: scale(1.01); }
  100% { opacity: 1; transform: scale(1.00); }
}

.overlay{
  position: fixed;
  inset: 0;
  background: radial-gradient(1200px 800px at 30% 40%, rgba(0,120,255,0.20), rgba(0,0,0,0) 60%),
              #07080a;
  z-index: 9999;
  animation: fadeOverlay 0.35s ease forwards;
  display:flex;
  align-items:center;
  justify-content:center;
}

.overlayText{
  font-size: 14px;
  color: rgba(235,240,255,0.68);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# SESSION STATE
# -----------------------------------------------------------------------------
def ss_init(key, value):
    if key not in st.session_state:
        st.session_state[key] = value


ss_init("view", "landing")               # landing, wizard, pay, generate
ss_init("step", 1)                      # 1..4
ss_init("do_transition", False)

ss_init("payment_ok", False)
ss_init("generated_text", "")
ss_init("website_signals", "")

ss_init("gen_running", False)
ss_init("gen_error", "")
ss_init("cancel_requested", False)

for k in [
    "company_name", "industry", "website", "api_key",
    "audience", "offer", "proof",
    "voice", "do_say", "dont_say",
    "visual_style", "colors", "typography", "imagery",
]:
    ss_init(k, "")


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def scrape_website_text(url: str) -> str:
    if not url:
        return ""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        text = normalize_whitespace(text)
        return text[:5000]
    except Exception:
        return ""


def sanitize_pdf_text(text: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "’": "'",
        "“": '"',
        "”": '"',
    }
    for a, b in replacements.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def pdf_from_markdown(md: str, company: str) -> bytes:
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 10)
            self.set_text_color(40, 40, 40)
            self.cell(0, 10, f"{company.upper()}  BRAND SYSTEM", 0, 1, "C")
            self.ln(2)

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_font("Arial", size=11)
    pdf.set_text_color(20, 20, 20)

    for line in md.split("\n"):
        s = sanitize_pdf_text(line.rstrip())
        if s.startswith("# "):
            pdf.ln(4)
            pdf.set_font("Arial", "B", 18)
            pdf.multi_cell(0, 9, s[2:])
            pdf.set_font("Arial", size=11)
            pdf.ln(2)
        elif s.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Arial", "B", 14)
            pdf.multi_cell(0, 8, s[3:])
            pdf.set_font("Arial", size=11)
            pdf.ln(1)
        else:
            pdf.multi_cell(0, 5.5, s)

    return pdf.output(dest="S").encode("latin-1")


def dots(step: int, total: int = 4) -> str:
    items = []
    for i in range(1, total + 1):
        cls = "stepDot active" if i == step else "stepDot"
        items.append(f'<div class="{cls}"></div>')
    return "".join(items)


def transition_then(next_view: str, next_step: int | None = None):
    st.session_state.do_transition = True
    st.session_state._next_view = next_view
    st.session_state._next_step = next_step


def render_transition_if_needed():
    if st.session_state.get("do_transition"):
        st.markdown(
            """
            <div class="overlay">
              <div class="overlayText">Opening the editor</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        time.sleep(0.35)
        st.session_state.do_transition = False
        st.session_state.view = st.session_state.get("_next_view", "wizard")
        if st.session_state.get("_next_step") is not None:
            st.session_state.step = st.session_state._next_step
        st.rerun()


def build_prompt() -> str:
    company = st.session_state.company_name.strip()
    industry = st.session_state.industry.strip()

    site = st.session_state.website.strip()
    signals = st.session_state.website_signals.strip()

    parts = []
    parts.append("Role: world class brand strategist and editorial designer.")
    parts.append("Output: a brand bible in markdown. Premium, usable, specific.")
    parts.append("Avoid fluff. Avoid vague adjectives without rules or examples.")
    parts.append("")
    parts.append(f"Brand: {company}")
    parts.append(f"Industry: {industry}")
    if site:
        parts.append(f"Website: {site}")
    parts.append("")
    parts.append("Inputs")
    parts.append(f"Audience: {st.session_state.audience}")
    parts.append(f"Offer: {st.session_state.offer}")
    parts.append(f"Proof: {st.session_state.proof}")
    parts.append("")
    parts.append(f"Voice reference: {st.session_state.voice}")
    parts.append(f"Do say: {st.session_state.do_say}")
    parts.append(f"Do not say: {st.session_state.dont_say}")
    parts.append("")
    parts.append(f"Visual style: {st.session_state.visual_style}")
    parts.append(f"Color direction: {st.session_state.colors}")
    parts.append(f"Typography direction: {st.session_state.typography}")
    parts.append(f"Imagery direction: {st.session_state.imagery}")
    parts.append("")

    if signals:
        parts.append("Website signals")
        parts.append("Use these only as evidence. If unclear, do not invent.")
        parts.append(signals[:2500])
        parts.append("")

    parts.append("Structure")
    parts.append(f"# {company}")
    parts.append("## Executive summary")
    parts.append("## Positioning")
    parts.append("Include category, audience focus, and defendable edge.")
    parts.append("## Messaging system")
    parts.append("Include key messages, proof points, tagline options, and a short elevator pitch.")
    parts.append("## Voice and tone")
    parts.append("Include principles, do and do not lists, and 6 example sentences in the voice.")
    parts.append("## Visual direction")
    parts.append("Include palette logic, typography intent, layout rules, imagery rules, and what to avoid.")
    parts.append("## Quick start")
    parts.append("One page summary as bullets a team can paste into a doc.")
    parts.append("")
    parts.append("Quality bar")
    parts.append("Reads like a small agency deliverable. Tight, confident, usable.")
    parts.append("No invented awards or fake history. If unsure, frame as options.")
    return "\n".join(parts)


def gemini_generate_with_timeout(prompt: str, timeout_s: int = 45, retries: int = 1) -> str:
    genai.configure(api_key=st.session_state.api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    last_err = None
    for _ in range(retries + 1):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(model.generate_content, prompt)
                resp = fut.result(timeout=timeout_s)
            return (resp.text or "").strip()
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Generation failed or timed out: {last_err}")


# -----------------------------------------------------------------------------
# LANDING
# -----------------------------------------------------------------------------
def render_landing():
    st.markdown(
        """
        <div class="glass hero-wrap">
          <div class="hero-bg"></div>
          <div class="hero-content">
            <div class="h-eyebrow">Brand system generator</div>
            <div class="h-title">Make your brand bible feel designed.</div>
            <div class="h-sub">
              A guided editorial workflow that captures strategy, voice, and visual direction, then produces a polished PDF.
              Built for founders, teams, and agencies that want alignment without noise.
            </div>

            <div class="pills">
              <div class="pill">Editorial flow</div>
              <div class="pill">Website signals</div>
              <div class="pill">Blueprint first</div>
              <div class="pill">PDF output</div>
              <div class="pill">One time price 99</div>
            </div>

            <div class="hero-grid">
              <div class="hero-cards">
                <div class="card">
                  <div class="cardT">Strategy</div>
                  <div class="cardB">Positioning, differentiators, and reasons to believe your team can defend.</div>
                </div>
                <div class="card">
                  <div class="cardT">Voice</div>
                  <div class="cardB">Principles, do and do not language, and copy starters writers can use.</div>
                </div>
                <div class="card">
                  <div class="cardT">Visual direction</div>
                  <div class="cardB">Keywords, avoids, and layout rules designers trust.</div>
                </div>
              </div>

              <div class="panel-soft" style="padding:18px; border-radius:22px;">
                <div class="small-muted" style="margin-bottom:10px;">Preview</div>
                <div style="border-radius:18px; overflow:hidden; border:1px solid rgba(255,255,255,0.10);">
                  <img src="https://images.unsplash.com/photo-1557682260-96773eb01377?q=80&w=1400&auto=format&fit=crop"
                       style="width:100%; height:220px; object-fit:cover; display:block;" />
                </div>
                <div class="small-muted" style="margin-top:10px;">
                  Clean hierarchy. Concrete rules. Client ready structure.
                </div>
              </div>
            </div>

          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.2, 1, 1.2])
    with c2:
        st.markdown("<div class='startBig'>", unsafe_allow_html=True)
        if st.button("Start"):
            transition_then("wizard", 1)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# WIZARD UI
# -----------------------------------------------------------------------------
def render_wizard_top():
    st.markdown(
        f"""
        <div class="wizardTop">
          <div style="display:flex; align-items:center;">
            <span class="brandDot"></span>
            <div>
              <div class="topTitle">Brand Bible Generator</div>
              <div class="topSub">A guided interview that outputs a client ready document.</div>
            </div>
          </div>
          <div class="dotRow">{dots(st.session_state.step, 4)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_shell(
    section_tag: str,
    num: str,
    name: str,
    desc: str,
    tip: str,
    guide_title: str,
    guide_text: str,
    guide_chips: list[str],
    guide_img: str,
):
    left, mid, right = st.columns([1.0, 1.65, 1.0], gap="large")

    with left:
        st.markdown(
            f"""
            <div class="panel sectionCard">
              <div class="sectionTag">{section_tag}</div>
              <div class="sectionNum">{num}</div>
              <div class="sectionName">{name}</div>
              <div class="sectionDesc">{desc}</div>
              <div class="sectionTip">{tip}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        chips_html = "".join([f'<div class="chip">{c}</div>' for c in guide_chips])
        st.markdown(
            f"""
            <div class="panel guideCard" style="height:100%;">
              <div class="guideBg" style="background-image:
                linear-gradient(180deg, rgba(10,12,16,0.30), rgba(10,12,16,0.92)),
                url('{guide_img}');"></div>
              <div class="guideContent">
                <div class="guideTag">Guide</div>
                <div class="guideTitle">{guide_title}</div>
                <div class="guideText">{guide_text}</div>
                <div class="chips">{chips_html}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return mid


def action_bar(left_label: str | None, left_kind: str, left_cb, right_label: str, right_kind: str, right_cb):
    st.markdown("<div class='actionBar'>", unsafe_allow_html=True)
    a, b, c = st.columns([1, 1, 1])

    with a:
        if left_label:
            if left_kind == "secondary":
                st.markdown("<div class='secondaryBtn'>", unsafe_allow_html=True)
            elif left_kind == "danger":
                st.markdown("<div class='dangerBtn'>", unsafe_allow_html=True)
            if st.button(left_label, use_container_width=True):
                left_cb()
            if left_kind in ["secondary", "danger"]:
                st.markdown("</div>", unsafe_allow_html=True)

    with c:
        if right_kind == "secondary":
            st.markdown("<div class='secondaryBtn'>", unsafe_allow_html=True)
        if st.button(right_label, use_container_width=True):
            right_cb()
        if right_kind == "secondary":
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def demo_fill():
    st.session_state["company_name"] = "Oura"
    st.session_state["industry"] = "Health tech"
    st.session_state["website"] = "ouraring.com"


def step_1():
    mid = render_step_shell(
        section_tag="Section 1",
        num="01",
        name="Signals",
        desc="Ground the work in reality. Name and category first. Website is optional.",
        tip="Specific beats clever. Write like you are briefing design and copy at the same time.",
        guide_title="Keep it crisp",
        guide_text="If you have a site, add it. If not, skip it. Clarity beats decoration.",
        guide_chips=["Name", "Industry", "Website"],
        guide_img="https://images.unsplash.com/photo-1522071820081-009f0129c71c?q=80&w=1200&auto=format&fit=crop",
    )

    with mid:
        st.markdown(
            """
            <div class="panel formPanel">
              <div class="formTitle">Brand identity signals</div>
              <div class="formSub">We use these to anchor strategy and tone in something real.</div>
              <div class="hr"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.text_input("Brand name", key="company_name", placeholder="Example Oura")
        st.text_input("Industry", key="industry", placeholder="Example health tech")
        st.text_input("Website (optional)", key="website", placeholder="Example ouraring.com")
        st.text_input("Gemini API key", key="api_key", type="password", placeholder="Paste your key")

        def go_next():
            if not st.session_state.company_name or not st.session_state.api_key:
                st.warning("Brand name and API key are required.")
                return
            if st.session_state.website:
                st.session_state.website_signals = scrape_website_text(st.session_state.website)
            st.session_state.step = 2
            st.rerun()

        def do_demo():
            demo_fill()
            st.rerun()

        st.markdown("<div class='actionBar'>", unsafe_allow_html=True)
        a, b, c = st.columns([1, 1, 1])
        with a:
            st.markdown("<div class='secondaryBtn'>", unsafe_allow_html=True)
            st.button("Demo", use_container_width=True, on_click=do_demo)
            st.markdown("</div>", unsafe_allow_html=True)
        with c:
            st.button("Continue", use_container_width=True, on_click=go_next)
        st.markdown("</div>", unsafe_allow_html=True)


def step_2():
    mid = render_step_shell(
        section_tag="Section 2",
        num="02",
        name="Offer",
        desc="Define who it is for, what it delivers, and why anyone should believe it.",
        tip="Name the outcome. Then give proof. If you cannot defend it, do not claim it.",
        guide_title="Answer like a brief",
        guide_text="Real buyer in real context. Then outcome. Then proof.",
        guide_chips=["Audience", "Outcome", "Proof"],
        guide_img="https://images.unsplash.com/photo-1522202176988-66273c2fd55f?q=80&w=1200&auto=format&fit=crop",
    )

    with mid:
        st.markdown(
            """
            <div class="panel formPanel">
              <div class="formTitle">Offer definition</div>
              <div class="formSub">This becomes your positioning foundation.</div>
              <div class="hr"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.text_area("Audience", key="audience", height=110, placeholder="Who is it for. Include role, context, and what they care about.")
        st.text_area("Offer", key="offer", height=110, placeholder="What do they get. Name the outcome, not the feature.")
        st.text_area("Proof", key="proof", height=110, placeholder="Why believe it. Evidence, process, metrics, credibility.")

        def go_back():
            st.session_state.step = 1
            st.rerun()

        def go_next():
            if not st.session_state.audience or not st.session_state.offer:
                st.warning("Audience and Offer are required.")
                return
            st.session_state.step = 3
            st.rerun()

        action_bar("Back", "secondary", go_back, "Continue", "primary", go_next)


def step_3():
    mid = render_step_shell(
        section_tag="Section 3",
        num="03",
        name="Voice",
        desc="Set the speaking rules. Make it usable for writing, sales, and support.",
        tip="Rules beat adjectives. Give examples. Give constraints.",
        guide_title="Do and do not",
        guide_text="Define principles, then phrases you would use and phrases you would never use.",
        guide_chips=["Principles", "Do say", "Do not say"],
        guide_img="https://images.unsplash.com/photo-1526948128573-703ee1aeb6fa?q=80&w=1200&auto=format&fit=crop",
    )

    with mid:
        st.markdown(
            """
            <div class="panel formPanel">
              <div class="formTitle">Voice system</div>
              <div class="formSub">Concrete enough that a writer can apply it tomorrow.</div>
              <div class="hr"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.text_area("Voice reference", key="voice", height=90, placeholder="Optional. Example: calm, precise, warm.")
        st.text_area("Do say", key="do_say", height=120, placeholder="Words, phrases, sentence patterns you use.")
        st.text_area("Do not say", key="dont_say", height=120, placeholder="Words, phrases, patterns you avoid.")

        def go_back():
            st.session_state.step = 2
            st.rerun()

        def go_next():
            st.session_state.step = 4
            st.rerun()

        action_bar("Back", "secondary", go_back, "Continue", "primary", go_next)


def step_4():
    mid = render_step_shell(
        section_tag="Section 4",
        num="04",
        name="Visual direction",
        desc="Give designers a lane: look, palette logic, typography intent, imagery rules.",
        tip="Describe decisions, not vibes. Rules should survive different designers.",
        guide_title="Art direction notes",
        guide_text="Keywords, avoids, and rules about composition and texture.",
        guide_chips=["Style", "Color", "Type", "Imagery"],
        guide_img="https://images.unsplash.com/photo-1557682250-33bd709cbe85?q=80&w=1200&auto=format&fit=crop",
    )

    with mid:
        st.markdown(
            """
            <div class="panel formPanel">
              <div class="formTitle">Visual direction</div>
              <div class="formSub">We translate this into designer friendly direction.</div>
              <div class="hr"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.text_area("Visual style", key="visual_style", height=90, placeholder="Example: minimal, high contrast, editorial, precise grid.")
        st.text_area("Color direction", key="colors", height=100, placeholder="Palette logic. Example: one primary, one neutral system, one accent.")
        st.text_area("Typography direction", key="typography", height=100, placeholder="Font qualities. Example: modern sans, strong numerals, readable UI.")
        st.text_area("Imagery direction", key="imagery", height=100, placeholder="Photo and illustration rules. Example: candid, natural light, low saturation.")

        def go_back():
            st.session_state.step = 3
            st.rerun()

        def go_next():
            st.session_state.view = "pay"
            st.rerun()

        action_bar("Back", "secondary", go_back, "Unlock and generate", "primary", go_next)


# -----------------------------------------------------------------------------
# PAYMENT
# -----------------------------------------------------------------------------
def render_pay():
    st.markdown(
        """
        <div class="glass" style="padding:22px;">
        """,
        unsafe_allow_html=True,
    )
    render_wizard_top()

    st.markdown(
        """
        <div class="panel" style="padding:26px; border-radius:22px; max-width:760px; margin: 0 auto;">
          <div class="h-eyebrow">Total</div>
          <div style="font-size:42px; font-weight:800; letter-spacing:-0.02em; margin-top:6px;">99.00</div>
          <div class="small-muted" style="margin-top:6px;">Mocked payment screen. Replace with your checkout.</div>
          <div class="hr"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if not st.session_state.payment_ok:
            if st.button("Confirm purchase", use_container_width=True):
                st.session_state.payment_ok = True
                st.rerun()
        else:
            st.success("Verified.")
            if st.button("Generate PDF", use_container_width=True):
                st.session_state.view = "generate"
                st.session_state.generated_text = ""
                st.session_state.gen_running = False
                st.session_state.gen_error = ""
                st.session_state.cancel_requested = False
                st.rerun()

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<div class='secondaryBtn'>", unsafe_allow_html=True)
        if st.button("Back to editor", use_container_width=True):
            st.session_state.view = "wizard"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# GENERATION
# -----------------------------------------------------------------------------
def render_generate():
    st.markdown(
        """
        <div class="glass" style="padding:22px;">
        """,
        unsafe_allow_html=True,
    )
    render_wizard_top()

    st.markdown(
        """
        <div class="panel" style="padding:26px; border-radius:22px; max-width:860px; margin: 0 auto;">
          <div class="formTitle">Generating</div>
          <div class="formSub">Synthesizing strategy, voice, and visual direction into a PDF.</div>
          <div class="hr"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<div class='dangerBtn'>", unsafe_allow_html=True)
        if st.button("Cancel generation", use_container_width=True):
            st.session_state.cancel_requested = True
            st.session_state.gen_running = False
            st.session_state.generated_text = ""
            st.session_state.gen_error = ""
            st.session_state.view = "wizard"
            st.session_state.step = 4
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if not st.session_state.api_key:
        st.error("Missing API key.")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.markdown("<div class='secondaryBtn'>", unsafe_allow_html=True)
            if st.button("Back", use_container_width=True):
                st.session_state.view = "wizard"
                st.session_state.step = 1
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if (not st.session_state.generated_text) and (not st.session_state.gen_running) and (not st.session_state.gen_error):
        st.session_state.gen_running = True
        st.session_state.cancel_requested = False

        status = st.empty()
        progress = st.progress(0)

        try:
            status.info("Preparing prompt...")
            progress.progress(15)

            prompt = build_prompt()
            status.info("Contacting Gemini...")
            progress.progress(45)

            text = gemini_generate_with_timeout(prompt, timeout_s=45, retries=1)

            status.info("Formatting output...")
            progress.progress(90)

            st.session_state.generated_text = text
            st.session_state.gen_running = False

            progress.progress(100)
            status.empty()

            st.rerun()

        except Exception as e:
            st.session_state.gen_running = False
            st.session_state.gen_error = str(e)
            status.empty()
            st.rerun()

    if st.session_state.gen_error:
        st.error(st.session_state.gen_error)
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            if st.button("Retry", use_container_width=True):
                st.session_state.gen_error = ""
                st.session_state.generated_text = ""
                st.session_state.gen_running = False
                st.rerun()

    if st.session_state.generated_text:
        md = normalize_whitespace(st.session_state.generated_text)
        pdf_bytes = pdf_from_markdown(md, st.session_state.company_name or "Brand")

        st.success("Ready.")
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"{(st.session_state.company_name or 'Brand').strip()}_Brand_Bible.pdf",
            mime="application/pdf",
        )

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.markdown("<div class='secondaryBtn'>", unsafe_allow_html=True)
            if st.button("Start new", use_container_width=True):
                keep = {"view", "step", "do_transition"}
                for k in list(st.session_state.keys()):
                    if k not in keep:
                        st.session_state.pop(k, None)
                st.session_state.view = "landing"
                st.session_state.step = 1
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# MAIN ROUTER
# -----------------------------------------------------------------------------
render_transition_if_needed()

if st.session_state.view == "landing":
    render_landing()

elif st.session_state.view == "wizard":
    st.markdown("<div class='glass' style='padding:22px;'>", unsafe_allow_html=True)
    render_wizard_top()

    if st.session_state.step == 1:
        step_1()
    elif st.session_state.step == 2:
        step_2()
    elif st.session_state.step == 3:
        step_3()
    else:
        step_4()

    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.view == "pay":
    render_pay()

elif st.session_state.view == "generate":
    render_generate()

else:
    st.session_state.view = "landing"
    st.rerun()
