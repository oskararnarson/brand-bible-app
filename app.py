import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import requests
from bs4 import BeautifulSoup
import time
import json
import re
from urllib.parse import urlparse

# =============================================================================
# CONFIG
# =============================================================================
st.set_page_config(
    page_title="Brand Bible Generator",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# EDITORIAL DARK UI CSS
# =============================================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: #0B0C10;
  color: rgba(255,255,255,0.92);
}

section[data-testid="stSidebar"] { display: none !important; }
header, footer { visibility: hidden !important; }

.block-container {
  max-width: 1220px !important;
  padding-top: 2.25rem;
  padding-bottom: 4rem;
  margin: 0 auto;
}

/* Subtle grid background */
.bgGrid {
  position: fixed;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
  background-size: 56px 56px;
  opacity: 0.22;
  mask-image: radial-gradient(circle at 50% 35%, rgba(0,0,0,1), rgba(0,0,0,0.25) 55%, rgba(0,0,0,0) 78%);
}
.bgGlow {
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 18% 18%, rgba(0,113,227,0.20), transparent 38%),
    radial-gradient(circle at 70% 22%, rgba(255,255,255,0.10), transparent 42%),
    radial-gradient(circle at 50% 78%, rgba(0,113,227,0.12), transparent 46%);
  opacity: 0.9;
}

/* Motion */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); filter: blur(3px); }
  to { opacity: 1; transform: translateY(0px); filter: blur(0px); }
}
.enter {
  animation: fadeUp 620ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* Landing hero */
.heroWrap {
  border-radius: 34px;
  padding: 88px 56px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 28px 90px rgba(0,0,0,0.45);
  position: relative;
  overflow: hidden;
}
.heroWrap::before {
  content: "";
  position: absolute;
  inset: -1px;
  background: radial-gradient(circle at 20% 25%, rgba(0,113,227,0.22), transparent 40%);
  opacity: 0.9;
  pointer-events: none;
}
.heroEyebrow {
  letter-spacing: 2px;
  text-transform: uppercase;
  font-weight: 700;
  font-size: 12px;
  color: rgba(255,255,255,0.75);
  margin-bottom: 14px;
}
.heroTitle {
  font-size: 64px;
  line-height: 1.02;
  letter-spacing: -2.2px;
  font-weight: 720;
  margin: 0 0 18px 0;
}
.heroSub {
  font-size: 18px;
  line-height: 1.6;
  color: rgba(255,255,255,0.70);
  max-width: 780px;
  margin: 0 0 30px 0;
}
.heroPills {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 20px;
}
.pill {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  font-size: 13px;
  color: rgba(255,255,255,0.78);
}
.heroRow {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 44px;
}
@media (max-width: 1050px) {
  .heroTitle { font-size: 44px; }
  .heroWrap { padding: 62px 22px; }
  .heroRow { grid-template-columns: 1fr; }
}
.heroCard {
  background: rgba(0,0,0,0.22);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 22px;
  padding: 18px 18px;
}
.heroCardT {
  font-weight: 650;
  letter-spacing: -0.2px;
  margin: 0 0 6px 0;
}
.heroCardB {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: rgba(255,255,255,0.66);
}

/* Spread layout */
.spread {
  border-radius: 34px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  box-shadow: 0 28px 90px rgba(0,0,0,0.52);
}
.spreadTop {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 22px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  background: rgba(0,0,0,0.22);
}
.brandMark {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dot {
  width: 34px; height: 34px;
  border-radius: 12px;
  background: radial-gradient(circle at 30% 30%, #FFFFFF 0%, #DDEBFF 40%, #0071E3 100%);
  box-shadow: 0 16px 38px rgba(0,113,227,0.24);
  border: 1px solid rgba(255,255,255,0.20);
}
.brandTxt {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.brandName {
  font-weight: 700;
  letter-spacing: -0.2px;
  font-size: 14px;
}
.brandMeta {
  font-size: 12px;
  color: rgba(255,255,255,0.60);
}
.stepDots {
  display: flex;
  gap: 10px;
  align-items: center;
}
.stepDot {
  width: 9px; height: 9px;
  border-radius: 999px;
  background: rgba(255,255,255,0.18);
}
.stepDotOn {
  background: rgba(0,113,227,1);
  box-shadow: 0 10px 20px rgba(0,113,227,0.35);
  transform: scale(1.18);
}
.spreadBody {
  display: grid;
  grid-template-columns: 0.58fr 1.18fr 0.74fr;
  min-height: 700px;
}
@media (max-width: 1100px) {
  .spreadBody { grid-template-columns: 1fr; }
}

/* Left section rail */
.rail {
  padding: 40px 34px;
  border-right: 1px solid rgba(255,255,255,0.08);
  background: rgba(0,0,0,0.20);
  position: relative;
}
.secTag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.70);
}
.bigNum {
  font-size: 88px;
  line-height: 0.95;
  letter-spacing: -4px;
  font-weight: 780;
  margin-top: 26px;
  margin-bottom: 22px;
  color: rgba(255,255,255,0.92);
}
.railTitle {
  font-size: 34px;
  line-height: 1.05;
  letter-spacing: -1.2px;
  font-weight: 760;
  margin: 0 0 12px 0;
}
.railCopy {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255,255,255,0.62);
  max-width: 260px;
}
.railMini {
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid rgba(255,255,255,0.08);
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255,255,255,0.55);
}

/* Center writing surface */
.surface {
  padding: 44px 44px;
  position: relative;
}
.surfaceTitle {
  font-size: 40px;
  letter-spacing: -1.2px;
  font-weight: 760;
  margin: 0 0 10px 0;
}
.surfaceDesc {
  font-size: 15px;
  line-height: 1.7;
  color: rgba(255,255,255,0.68);
  margin: 0 0 22px 0;
  max-width: 680px;
}
.surfaceDivider {
  height: 1px;
  background: rgba(255,255,255,0.08);
  margin: 18px 0 18px 0;
}

/* Right whisper panel */
.whisper {
  padding: 44px 34px;
  border-left: 1px solid rgba(255,255,255,0.08);
  background: rgba(0,0,0,0.18);
}
.whisperTag {
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.55);
  margin-bottom: 12px;
}
.whisperTitle {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 10px 0;
  letter-spacing: -0.2px;
}
.whisperBody {
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255,255,255,0.62);
  margin: 0 0 14px 0;
}
.whisperChipRow {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.whisperChip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  font-size: 12px;
  color: rgba(255,255,255,0.78);
}
.exampleBox {
  margin-top: 16px;
  padding: 14px 14px;
  border-radius: 18px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255,255,255,0.66);
}

/* Inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
  background: rgba(255,255,255,0.06) !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  border-radius: 18px !important;
  padding: 14px 16px !important;
  font-size: 15px !important;
  color: rgba(255,255,255,0.92) !important;
}
.stTextArea textarea { line-height: 1.65 !important; }

.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: rgba(0,113,227,0.75) !important;
  box-shadow: 0 0 0 4px rgba(0,113,227,0.22) !important;
}

label {
  font-size: 11px !important;
  font-weight: 700 !important;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.55) !important;
}

/* Buttons */
div.stButton > button {
  background: rgba(0,113,227,1);
  border: none;
  color: white;
  font-weight: 700;
  font-size: 15px;
  padding: 14px 22px;
  border-radius: 999px;
  box-shadow: 0 16px 36px rgba(0,113,227,0.25);
  transition: transform 140ms ease, box-shadow 140ms ease, background 140ms ease;
}
div.stButton > button:hover {
  background: rgba(0,119,237,1);
  transform: translateY(-1px);
  box-shadow: 0 22px 44px rgba(0,113,227,0.28);
}
.secondaryBtn button {
  background: rgba(255,255,255,0.06) !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  box-shadow: none !important;
}

/* Hide Streamlit "press enter" hints */
div[data-testid="InputInstructions"] { display: none !important; }
</style>

<div class="bgGlow"></div>
<div class="bgGrid"></div>
""",
    unsafe_allow_html=True,
)

# =============================================================================
# STATE
# =============================================================================
def ss_init(key, default):
    if key not in st.session_state:
        st.session_state[key] = default


ss_init("page", "landing")
ss_init("step", 1)
ss_init("payment_ok", False)
ss_init("api_key", "")

ss_init("brand_name", "")
ss_init("brand_url", "")
ss_init("industry", "")

ss_init("audience", "")
ss_init("offer", "")
ss_init("proof", "")

ss_init("competitors", "")
ss_init("positioning", "")

ss_init("traits", "")
ss_init("values", "")
ss_init("voice_do", "")
ss_init("voice_dont", "")

ss_init("visual_keywords", "")
ss_init("visual_avoid", "")
ss_init("color_bias", "Neutral with one accent")
ss_init("type_bias", "Modern sans")
ss_init("doc_depth", "Standard")

ss_init("generated_blueprint", None)
ss_init("generated_markdown", None)

TOTAL_STEPS = 7

# =============================================================================
# UTILS
# =============================================================================
def safe_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not re.match(r"^https?://", u, flags=re.I):
        u = "https://" + u
    try:
        p = urlparse(u)
        if not p.netloc:
            return ""
        return u
    except Exception:
        return ""


@st.cache_data(show_spinner=False, ttl=3600)
def scrape_site(url: str) -> dict:
    data = {
        "title": "",
        "description": "",
        "og_title": "",
        "og_description": "",
        "headings": [],
        "snippets": [],
    }
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code >= 400:
            return data
        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        data["title"] = title

        dtag = soup.find("meta", attrs={"name": "description"})
        if dtag and dtag.get("content"):
            data["description"] = dtag.get("content").strip()

        ogt = soup.find("meta", property="og:title")
        if ogt and ogt.get("content"):
            data["og_title"] = ogt.get("content").strip()

        ogd = soup.find("meta", property="og:description")
        if ogd and ogd.get("content"):
            data["og_description"] = ogd.get("content").strip()

        headings = []
        for tag in soup.find_all(["h1", "h2"], limit=10):
            txt = tag.get_text(" ", strip=True)
            if txt and len(txt) <= 90:
                headings.append(txt)
        data["headings"] = headings[:8]

        snippets = []
        for p in soup.find_all("p", limit=18):
            txt = p.get_text(" ", strip=True)
            if txt and 40 <= len(txt) <= 190:
                snippets.append(txt)
        data["snippets"] = snippets[:6]

        return data
    except Exception:
        return data


def dots_html(current: int, total: int) -> str:
    out = []
    for i in range(1, total + 1):
        cls = "stepDot stepDotOn" if i == current else "stepDot"
        out.append(f'<div class="{cls}"></div>')
    return "".join(out)


def sanitize_pdf_text(text: str) -> str:
    m = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
    }
    for k, v in m.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def render_pdf(md: str, brand: str) -> bytes:
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 10)
            self.set_text_color(120, 120, 130)
            self.cell(0, 10, sanitize_pdf_text(f"{brand.upper()}  BRAND BIBLE"), 0, 1, "C")
            self.ln(1)

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=16)

    # Cover
    pdf.add_page()
    pdf.set_text_color(20, 20, 24)
    pdf.set_font("Arial", "B", 28)
    pdf.ln(30)
    pdf.multi_cell(0, 12, sanitize_pdf_text(brand))
    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(90, 90, 100)
    pdf.ln(4)
    pdf.multi_cell(0, 7, sanitize_pdf_text("Brand Bible"))
    pdf.ln(8)
    pdf.set_text_color(20, 20, 24)

    # Body
    pdf.add_page()
    pdf.set_font("Arial", "", 11)

    for raw_line in md.split("\n"):
        line = raw_line.rstrip()

        if line.startswith("# "):
            pdf.set_font("Arial", "B", 18)
            pdf.ln(6)
            pdf.multi_cell(0, 10, sanitize_pdf_text(line[2:]))
            pdf.ln(2)
            pdf.set_font("Arial", "", 11)

        elif line.startswith("## "):
            pdf.set_font("Arial", "B", 14)
            pdf.ln(5)
            pdf.multi_cell(0, 8, sanitize_pdf_text(line[3:]))
            pdf.ln(1)
            pdf.set_font("Arial", "", 11)

        elif line.startswith("### "):
            pdf.set_font("Arial", "B", 12)
            pdf.ln(4)
            pdf.multi_cell(0, 7, sanitize_pdf_text(line[4:]))
            pdf.set_font("Arial", "", 11)

        elif line.strip() == "":
            pdf.ln(3)

        else:
            pdf.multi_cell(0, 5.6, sanitize_pdf_text(line))

    return pdf.output(dest="S").encode("latin-1")


def build_intake(site_data: dict) -> dict:
    def split_lines(x: str):
        items = []
        for part in re.split(r"[,\n]", (x or "").strip()):
            s = part.strip()
            if s:
                items.append(s)
        return items

    return {
        "brand_name": st.session_state.brand_name.strip(),
        "brand_url": st.session_state.brand_url.strip(),
        "industry": st.session_state.industry.strip(),
        "audience": st.session_state.audience.strip(),
        "offer": st.session_state.offer.strip(),
        "proof": st.session_state.proof.strip(),
        "competitors": split_lines(st.session_state.competitors),
        "positioning": st.session_state.positioning.strip(),
        "traits": split_lines(st.session_state.traits),
        "values": split_lines(st.session_state.values),
        "voice_do": split_lines(st.session_state.voice_do),
        "voice_dont": split_lines(st.session_state.voice_dont),
        "visual_keywords": split_lines(st.session_state.visual_keywords),
        "visual_avoid": split_lines(st.session_state.visual_avoid),
        "color_bias": st.session_state.color_bias,
        "type_bias": st.session_state.type_bias,
        "doc_depth": st.session_state.doc_depth,
        "site_intelligence": site_data,
    }


def gemini_blueprint(intake: dict) -> dict:
    genai.configure(api_key=st.session_state.api_key.strip())
    model = genai.GenerativeModel("gemini-1.5-flash")

    schema_hint = {
        "brand": {
            "name": "string",
            "one_liner": "string",
            "category": "string",
            "audience": "string",
            "offer": "string",
            "positioning_statement": "string",
        },
        "strategy": {
            "core_problem": "string",
            "insight": "string",
            "promise": "string",
            "reasons_to_believe": ["string"],
            "competitive_set": ["string"],
            "differentiators": ["string"],
        },
        "essence": {
            "mission": "string",
            "vision": "string",
            "values": ["string"],
            "personality_traits": ["string"],
            "beliefs": ["string"],
        },
        "voice": {
            "principles": ["string"],
            "do_say": ["string"],
            "dont_say": ["string"],
            "taglines": ["string"],
            "about_blurb": "string",
            "product_copy": "string",
            "social_caption": "string",
        },
        "visual": {
            "keywords": ["string"],
            "avoid": ["string"],
            "color_system": {
                "approach": "string",
                "notes": "string",
                "sample_hex": ["string"],
            },
            "typography": {
                "approach": "string",
                "headline_style": "string",
                "body_style": "string",
            },
            "imagery": {
                "principles": ["string"],
                "composition": "string",
                "lighting": "string",
                "seek": ["string"],
                "avoid": ["string"],
            },
            "layout_rules": ["string"],
        },
        "usage": {
            "quick_checks": ["string"],
            "good_example": "string",
            "bad_example": "string",
        },
    }

    prompt = f"""
You are a legendary brand strategy agency.
Return STRICT JSON only.
No markdown. No code fences. No commentary.

SCHEMA SHAPE:
{json.dumps(schema_hint, ensure_ascii=False, indent=2)}

INTAKE:
{json.dumps(intake, ensure_ascii=False, indent=2)}

QUALITY:
Write like a premium agency.
Avoid generic filler.
Be concrete and usable.
Stay consistent with the intake.
If something is missing, infer carefully from site_intelligence.
"""

    r = model.generate_content(prompt)
    text = (r.text or "").strip().strip("` \n")
    text = re.sub(r"^json\s*", "", text, flags=re.I)

    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def blueprint_to_markdown(b: dict) -> str:
    def bullets(items):
        return "\n".join([f"* {x}" for x in items if str(x).strip()])

    md = []
    md.append(f"# {b['brand']['name']}")
    md.append("")
    md.append("## Executive Summary")
    md.append(f"**One liner:** {b['brand']['one_liner']}")
    md.append(f"**Category:** {b['brand']['category']}")
    md.append(f"**Audience:** {b['brand']['audience']}")
    md.append(f"**Offer:** {b['brand']['offer']}")
    md.append("")
    md.append("## Positioning")
    md.append(b["brand"]["positioning_statement"])
    md.append("")
    md.append("## Strategy")
    md.append(f"**Core problem:** {b['strategy']['core_problem']}")
    md.append(f"**Insight:** {b['strategy']['insight']}")
    md.append(f"**Promise:** {b['strategy']['promise']}")
    md.append("")
    md.append("### Reasons to believe")
    md.append(bullets(b["strategy"]["reasons_to_believe"]))
    md.append("")
    md.append("### Differentiators")
    md.append(bullets(b["strategy"]["differentiators"]))
    md.append("")
    md.append("### Competitive set")
    md.append(bullets(b["strategy"]["competitive_set"]))
    md.append("")
    md.append("## Essence")
    md.append(f"**Mission:** {b['essence']['mission']}")
    md.append(f"**Vision:** {b['essence']['vision']}")
    md.append("")
    md.append("### Values")
    md.append(bullets(b["essence"]["values"]))
    md.append("")
    md.append("### Personality traits")
    md.append(bullets(b["essence"]["personality_traits"]))
    md.append("")
    md.append("### Beliefs")
    md.append(bullets(b["essence"]["beliefs"]))
    md.append("")
    md.append("## Voice")
    md.append("### Principles")
    md.append(bullets(b["voice"]["principles"]))
    md.append("")
    md.append("### Do say")
    md.append(bullets(b["voice"]["do_say"]))
    md.append("")
    md.append("### Do not say")
    md.append(bullets(b["voice"]["dont_say"]))
    md.append("")
    md.append("### Taglines")
    md.append(bullets(b["voice"]["taglines"]))
    md.append("")
    md.append("### About blurb")
    md.append(b["voice"]["about_blurb"])
    md.append("")
    md.append("### Product copy")
    md.append(b["voice"]["product_copy"])
    md.append("")
    md.append("### Social caption")
    md.append(b["voice"]["social_caption"])
    md.append("")
    md.append("## Visual Direction")
    md.append("### Keywords")
    md.append(bullets(b["visual"]["keywords"]))
    md.append("")
    md.append("### Avoid")
    md.append(bullets(b["visual"]["avoid"]))
    md.append("")
    md.append("### Color system")
    md.append(f"**Approach:** {b['visual']['color_system']['approach']}")
    md.append(b["visual"]["color_system"]["notes"])
    md.append("")
    md.append("**Sample hex**")
    md.append(bullets(b["visual"]["color_system"]["sample_hex"]))
    md.append("")
    md.append("### Typography")
    md.append(f"**Approach:** {b['visual']['typography']['approach']}")
    md.append(f"**Headlines:** {b['visual']['typography']['headline_style']}")
    md.append(f"**Body:** {b['visual']['typography']['body_style']}")
    md.append("")
    md.append("### Imagery")
    md.append("**Principles**")
    md.append(bullets(b["visual"]["imagery"]["principles"]))
    md.append("")
    md.append(f"**Composition:** {b['visual']['imagery']['composition']}")
    md.append(f"**Lighting:** {b['visual']['imagery']['lighting']}")
    md.append("")
    md.append("**Seek**")
    md.append(bullets(b["visual"]["imagery"]["seek"]))
    md.append("")
    md.append("**Avoid**")
    md.append(bullets(b["visual"]["imagery"]["avoid"]))
    md.append("")
    md.append("### Layout rules")
    md.append(bullets(b["visual"]["layout_rules"]))
    md.append("")
    md.append("## Usage")
    md.append("### Quick checks")
    md.append(bullets(b["usage"]["quick_checks"]))
    md.append("")
    md.append("### Good example")
    md.append(b["usage"]["good_example"])
    md.append("")
    md.append("### Bad example")
    md.append(b["usage"]["bad_example"])
    md.append("")
    return "\n".join(md)


def validate_step(step: int) -> tuple[bool, str]:
    if step == 1:
        if not st.session_state.brand_name.strip():
            return False, "Brand name is required."
        if not st.session_state.api_key.strip():
            return False, "Gemini API key is required."
        return True, ""
    if step == 2:
        if not st.session_state.audience.strip():
            return False, "Audience is required."
        if not st.session_state.offer.strip():
            return False, "Offer is required."
        return True, ""
    if step == 3:
        if not st.session_state.positioning.strip():
            return False, "Positioning statement is required."
        return True, ""
    if step == 4:
        if not st.session_state.traits.strip():
            return False, "Traits are required."
        return True, ""
    if step == 5:
        if not st.session_state.visual_keywords.strip():
            return False, "Visual keywords are required."
        return True, ""
    return True, ""


def reset_all():
    keep_page = st.session_state.get("page", "landing")
    st.session_state.clear()
    st.session_state["page"] = keep_page
    ss_init("page", "landing")
    ss_init("step", 1)
    ss_init("payment_ok", False)
    ss_init("api_key", "")
    ss_init("brand_name", "")
    ss_init("brand_url", "")
    ss_init("industry", "")
    ss_init("audience", "")
    ss_init("offer", "")
    ss_init("proof", "")
    ss_init("competitors", "")
    ss_init("positioning", "")
    ss_init("traits", "")
    ss_init("values", "")
    ss_init("voice_do", "")
    ss_init("voice_dont", "")
    ss_init("visual_keywords", "")
    ss_init("visual_avoid", "")
    ss_init("color_bias", "Neutral with one accent")
    ss_init("type_bias", "Modern sans")
    ss_init("doc_depth", "Standard")
    ss_init("generated_blueprint", None)
    ss_init("generated_markdown", None)


# =============================================================================
# RENDER HELPERS
# =============================================================================
def render_spread(section_no: int, rail_title: str, rail_copy: str, surface_title: str, surface_desc: str,
                  whisper_title: str, whisper_body: str, whisper_chips: list[str], example_text: str):
    st.markdown(
        f"""
<div class="spread enter">
  <div class="spreadTop">
    <div class="brandMark">
      <div class="dot"></div>
      <div class="brandTxt">
        <div class="brandName">Brand Bible Generator</div>
        <div class="brandMeta">A guided brand interview that outputs a client ready document</div>
      </div>
    </div>
    <div class="stepDots">{dots_html(st.session_state.step, TOTAL_STEPS)}</div>
  </div>

  <div class="spreadBody">
    <div class="rail">
      <div class="secTag">SECTION {section_no}</div>
      <div class="bigNum">{section_no:02d}</div>
      <div class="railTitle">{rail_title}</div>
      <p class="railCopy">{rail_copy}</p>
      <div class="railMini">Write like you are briefing a designer and a copywriter.</div>
    </div>

    <div class="surface">
      <div class="surfaceTitle">{surface_title}</div>
      <div class="surfaceDesc">{surface_desc}</div>
      <div class="surfaceDivider"></div>
""",
        unsafe_allow_html=True,
    )

    # Content gets inserted by caller here in Streamlit

    st.markdown(
        """
    </div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
    <div class="whisper">
      <div class="whisperTag">GUIDE</div>
      <div class="whisperTitle">{whisper_title}</div>
      <p class="whisperBody">{whisper_body}</p>
      <div class="whisperChipRow">
        {''.join([f'<div class="whisperChip">{c}</div>' for c in whisper_chips])}
      </div>
      <div class="exampleBox">{example_text}</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# =============================================================================
# LANDING
# =============================================================================
if st.session_state.page == "landing":
    st.markdown(
        """
<div class="heroWrap enter">
  <div class="heroEyebrow">Brand system generator</div>
  <div class="heroTitle">Make your brand bible feel designed.</div>
  <div class="heroSub">
    A guided editorial workflow that captures strategy, voice, and visual direction, then produces a polished PDF.
    Built for founders, teams, and agencies that want alignment without the usual noise.
  </div>

  <div class="heroPills">
    <div class="pill">Editorial flow</div>
    <div class="pill">Website signals</div>
    <div class="pill">Blueprint first</div>
    <div class="pill">PDF output</div>
    <div class="pill">One time price 99</div>
  </div>

  <div class="heroRow">
    <div class="heroCard">
      <div class="heroCardT">Strategy</div>
      <p class="heroCardB">Positioning, differentiators, and reasons to believe that your team can defend.</p>
    </div>
    <div class="heroCard">
      <div class="heroCardT">Voice</div>
      <p class="heroCardB">Do and do not language, principles, and copy starters that writers can actually use.</p>
    </div>
    <div class="heroCard">
      <div class="heroCardT">Visual direction</div>
      <p class="heroCardB">Keywords, avoids, and art direction notes that designers trust.</p>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("Start"):
            st.session_state.page = "wizard"
            st.session_state.step = 1
            st.rerun()

# =============================================================================
# WIZARD
# =============================================================================
else:
    # STEP 1
    if st.session_state.step == 1:
        render_spread(
            section_no=1,
            rail_title="Signals.",
            rail_copy="Start with what exists. We will extract cues from your site, then only ask what we cannot infer.",
            surface_title="Brand identity signals",
            surface_desc="Give the brand name and the simplest possible context. If you have a site, include it.",
            whisper_title="Keep it crisp",
            whisper_body="This step is about grounding. A good name and a real site produce better inference than extra adjectives.",
            whisper_chips=["Name", "Industry", "Website"],
            example_text="Example: Oura, health tech, ouraring.com",
        )

        st.text_input("Brand name", key="brand_name", placeholder="Example Oura")
        st.text_input("Website", key="brand_url", placeholder="Example ouraring.com")
        st.text_input("Industry", key="industry", placeholder="Example health tech")
        st.text_input("Gemini API key", key="api_key", type="password")

        nav = st.columns([1, 1, 2])
        with nav[0]:
            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Reset"):
                reset_all()
                st.session_state.page = "wizard"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav[1]:
            if st.button("Continue"):
                ok, msg = validate_step(1)
                if not ok:
                    st.warning(msg)
                else:
                    st.session_state.step = 2
                    st.rerun()

    # STEP 2
    elif st.session_state.step == 2:
        render_spread(
            section_no=2,
            rail_title="Offer.",
            rail_copy="Define who it is for, what it gives them, and why they should believe it.",
            surface_title="Audience, offer, proof",
            surface_desc="If you only nail one step, nail this one. This is where positioning becomes possible.",
            whisper_title="Answer like a brief",
            whisper_body="Describe a real buyer in a real context. Then name the outcome. Then give proof.",
            whisper_chips=["Role", "Context", "Outcome", "Proof"],
            example_text="Audience: founders shipping fast. Offer: brand system in a day. Proof: past launches, results, examples.",
        )

        st.text_area("Audience", key="audience", height=110, placeholder="Who is it for. Include role, context, and what they care about.")
        st.text_area("Offer", key="offer", height=90, placeholder="What you provide. Name the outcome, not just the feature.")
        st.text_area("Proof", key="proof", height=90, placeholder="Why believe it. Evidence, process, metrics, credibility.")

        nav = st.columns([1, 1, 2])
        with nav[0]:
            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Back"):
                st.session_state.step = 1
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav[1]:
            if st.button("Continue"):
                ok, msg = validate_step(2)
                if not ok:
                    st.warning(msg)
                else:
                    st.session_state.step = 3
                    st.rerun()

    # STEP 3
    elif st.session_state.step == 3:
        render_spread(
            section_no=3,
            rail_title="Positioning.",
            rail_copy="Say what you are, who you are for, and why you are the obvious choice.",
            surface_title="Positioning statement",
            surface_desc="One strong paragraph beats ten weak ones. If you cannot defend the claim, do not make it.",
            whisper_title="Positioning that sounds real",
            whisper_body="Name the category, narrow the audience, then claim a defendable edge.",
            whisper_chips=["Category", "Narrow audience", "Defendable edge"],
            example_text="For busy teams, Brand is the simplest way to stay consistent, because the system forces clarity and removes guesswork.",
        )

        st.text_area(
            "Competitive set",
            key="competitors",
            height=90,
            placeholder="List competitors or alternatives. Separate with commas or new lines.",
        )
        st.text_area(
            "Positioning statement",
            key="positioning",
            height=160,
            placeholder="For X, Brand is the Y that delivers Z, because A. Unlike B.",
        )

        nav = st.columns([1, 1, 2])
        with nav[0]:
            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Back"):
                st.session_state.step = 2
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav[1]:
            if st.button("Continue"):
                ok, msg = validate_step(3)
                if not ok:
                    st.warning(msg)
                else:
                    st.session_state.step = 4
                    st.rerun()

    # STEP 4
    elif st.session_state.step == 4:
        render_spread(
            section_no=4,
            rail_title="Voice.",
            rail_copy="Lock the personality, values, and language rules so writing becomes consistent.",
            surface_title="Voice rules",
            surface_desc="Keep this practical. A writer should be able to follow it without guessing.",
            whisper_title="Write rules, not vibes",
            whisper_body="Traits define the posture. Do and do not language prevents drift. Values keep it honest.",
            whisper_chips=["Traits", "Values", "Do say", "Do not say"],
            example_text="Traits: precise, warm, confident. Do say: clear verbs, concrete nouns. Do not say: buzzwords, empty hype.",
        )

        st.text_area(
            "Personality traits",
            key="traits",
            height=90,
            placeholder="3 to 6 traits. Separate with commas or new lines. Example: precise, warm, confident",
        )
        st.text_area(
            "Values",
            key="values",
            height=90,
            placeholder="3 to 6 values written as actions. Separate with commas or new lines.",
        )
        st.text_area(
            "Do say",
            key="voice_do",
            height=90,
            placeholder="Words, phrases, patterns. Separate with commas or new lines.",
        )
        st.text_area(
            "Do not say",
            key="voice_dont",
            height=90,
            placeholder="Cliches, banned words, patterns to avoid. Separate with commas or new lines.",
        )

        nav = st.columns([1, 1, 2])
        with nav[0]:
            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Back"):
                st.session_state.step = 3
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav[1]:
            if st.button("Continue"):
                ok, msg = validate_step(4)
                if not ok:
                    st.warning(msg)
                else:
                    st.session_state.step = 5
                    st.rerun()

    # STEP 5
    elif st.session_state.step == 5:
        render_spread(
            section_no=5,
            rail_title="Visuals.",
            rail_copy="Define the grammar, not the logo. Keywords, avoids, and direction that designers can trust.",
            surface_title="Visual direction",
            surface_desc="This is the design brief embedded into the bible. Make it specific and consistent.",
            whisper_title="Design language",
            whisper_body="Keywords create the mood. Avoids protect quality. Bias choices give the system a spine.",
            whisper_chips=["Keywords", "Avoids", "Color bias", "Typography bias"],
            example_text="Keywords: editorial, minimal, high contrast. Avoid: noisy textures, childish gradients, generic stock.",
        )

        st.text_area(
            "Visual keywords",
            key="visual_keywords",
            height=110,
            placeholder="3 to 8 keywords. Separate with commas or new lines. Example: editorial, minimal, high contrast",
        )
        st.text_area(
            "Visual avoid list",
            key="visual_avoid",
            height=90,
            placeholder="What it should never look like. Separate with commas or new lines.",
        )
        st.selectbox(
            "Color bias",
            ["Neutral with one accent", "Dark and premium", "Bold and energetic", "Warm and human", "Bright and minimal"],
            key="color_bias",
        )
        st.selectbox(
            "Typography bias",
            ["Modern sans", "Editorial serif", "Grotesk neutral", "Tech mono", "Humanist sans"],
            key="type_bias",
        )
        st.selectbox(
            "Document depth",
            ["Standard", "Deep"],
            key="doc_depth",
        )

        nav = st.columns([1, 1, 2])
        with nav[0]:
            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Back"):
                st.session_state.step = 4
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with nav[1]:
            if st.button("Continue"):
                ok, msg = validate_step(5)
                if not ok:
                    st.warning(msg)
                else:
                    st.session_state.step = 6
                    st.rerun()

    # STEP 6
    elif st.session_state.step == 6:
        render_spread(
            section_no=6,
            rail_title="Access.",
            rail_copy="One time purchase. Then generate the PDF. Replace this step with Stripe when ready.",
            surface_title="Unlock generation",
            surface_desc="This build simulates payment for development. Swap in Stripe Checkout in production.",
            whisper_title="What you get",
            whisper_body="A structured blueprint plus a polished brand bible in PDF form, ready to share with a team or a designer.",
            whisper_chips=["Strategy", "Voice", "Visuals", "Usage rules"],
            example_text="Tip: keep regeneration available, founders change their mind and the best tools allow iteration.",
        )

        st.markdown(
            """
<div style="padding:18px 18px; border-radius:22px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); max-width: 520px;">
  <div style="font-size:11px; letter-spacing:2px; text-transform:uppercase; color: rgba(255,255,255,0.55); font-weight:700;">TOTAL</div>
  <div style="font-size:46px; letter-spacing:-1.5px; font-weight:800; margin-top: 6px;">99</div>
  <div style="font-size:13px; color: rgba(255,255,255,0.60); margin-top: 6px;">One time strategic investment.</div>
</div>
""",
            unsafe_allow_html=True,
        )

        if not st.session_state.payment_ok:
            if st.button("Simulate purchase"):
                with st.spinner("Authorizing..."):
                    time.sleep(1.1)
                st.session_state.payment_ok = True
                st.rerun()
        else:
            st.success("Payment verified.")
            if st.button("Generate brand bible"):
                st.session_state.step = 7
                st.rerun()

        nav = st.columns([1, 1, 2])
        with nav[0]:
            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Back"):
                st.session_state.step = 5
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # STEP 7
    elif st.session_state.step == 7:
        render_spread(
            section_no=7,
            rail_title="Synthesis.",
            rail_copy="Blueprint first, then the document. This prevents wandering and keeps output consistent.",
            surface_title="Generating your document",
            surface_desc="We read site signals, build a strict blueprint, then render the brand bible and PDF.",
            whisper_title="Why this stays consistent",
            whisper_body="The blueprint forces structure. The bible becomes a designed artifact, not a chat response.",
            whisper_chips=["Signals", "Blueprint", "Bible", "PDF"],
            example_text="Tip: if output feels generic, the fix is usually stronger proof and sharper positioning.",
        )

        url = safe_url(st.session_state.brand_url)
        site_data = {}
        if url:
            with st.spinner("Reading site signals..."):
                site_data = scrape_site(url)

        if st.session_state.generated_markdown is None:
            status = st.empty()
            try:
                status.info("Building blueprint...")
                time.sleep(0.2)
                intake = build_intake(site_data)
                blueprint = gemini_blueprint(intake)
                md = blueprint_to_markdown(blueprint)
                st.session_state.generated_blueprint = blueprint
                st.session_state.generated_markdown = md
                status.success("Complete.")
            except Exception as e:
                status.empty()
                st.error(f"Generation failed: {e}")

        if st.session_state.generated_markdown:
            md = st.session_state.generated_markdown
            brand = st.session_state.brand_name.strip() or "Brand"
            pdf_bytes = render_pdf(md, brand)

            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=f"{brand.replace(' ', '_')}_Brand_Bible.pdf",
                mime="application/pdf",
            )

            with st.expander("Preview"):
                st.markdown(md)

            nav = st.columns([1, 1, 2])
            with nav[0]:
                st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                if st.button("Back"):
                    st.session_state.step = 6
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with nav[1]:
                if st.button("Generate again"):
                    st.session_state.generated_blueprint = None
                    st.session_state.generated_markdown = None
                    st.rerun()
            with nav[2]:
                st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                if st.button("New project"):
                    reset_all()
                    st.session_state.page = "wizard"
                    st.session_state.step = 1
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
