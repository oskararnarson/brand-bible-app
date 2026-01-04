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
    initial_sidebar_state="collapsed"
)

# =============================================================================
# PREMIUM UI CSS
# =============================================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #111114;
  background-color: #F5F5F7;
}

section[data-testid="stSidebar"] { display: none !important; }
header, footer { visibility: hidden !important; }

.block-container {
  padding-top: 2.75rem;
  padding-bottom: 4rem;
  max-width: 1160px !important;
  margin: 0 auto;
}

:root{
  --card: #FFFFFF;
  --muted: #6B6B73;
  --muted2: #8B8B93;
  --line: rgba(17,17,20,0.06);
  --shadow: 0 24px 60px rgba(0,0,0,0.10);
  --shadow2: 0 10px 30px rgba(0,0,0,0.08);
  --blue: #0071E3;
  --blue2: #0077ED;
  --chip: #F3F4F6;
  --chipText: #111114;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(10px); filter: blur(2px); }
  to   { opacity: 1; transform: translateY(0px); filter: blur(0px); }
}
.enter { animation: fadeUp 650ms cubic-bezier(0.16, 1, 0.3, 1) both; }

.hero {
  text-align: center;
  background: var(--card);
  border-radius: 32px;
  padding: 92px 56px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.04);
  border: 1px solid var(--line);
}

.eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--blue);
  margin-bottom: 16px;
}

.h1 {
  font-size: 64px;
  line-height: 1.03;
  letter-spacing: -2.2px;
  font-weight: 700;
  margin: 0 0 18px 0;
}

.sub {
  font-size: 20px;
  line-height: 1.55;
  color: var(--muted);
  max-width: 780px;
  margin: 0 auto 36px auto;
}

.pillRow {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: 22px;
}
.pill {
  background: #F7F7FA;
  border: 1px solid var(--line);
  padding: 10px 14px;
  border-radius: 999px;
  font-size: 13px;
  color: #2B2B30;
}

.grid3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  margin-top: 44px;
  text-align: left;
}
@media (max-width: 1050px){
  .grid3 { grid-template-columns: 1fr; }
  .h1 { font-size: 46px; }
  .hero { padding: 64px 24px; }
}

.featureCard {
  background: var(--card);
  border-radius: 26px;
  border: 1px solid var(--line);
  box-shadow: 0 10px 30px rgba(0,0,0,0.04);
  padding: 22px 22px 18px 22px;
}
.featureTitle {
  font-size: 16px;
  font-weight: 650;
  margin: 0 0 8px 0;
}
.featureBody {
  font-size: 14px;
  line-height: 1.55;
  color: var(--muted);
  margin: 0;
}

.wizardShell {
  background: var(--card);
  border-radius: 32px;
  box-shadow: var(--shadow);
  border: 1px solid var(--line);
  overflow: hidden;
}

.wizardTop {
  padding: 22px 26px;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.brandmark {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logoDot {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: radial-gradient(circle at 30% 30%, #FFFFFF 0%, #DDEBFF 45%, #0071E3 100%);
  border: 1px solid rgba(0,113,227,0.25);
  box-shadow: 0 12px 24px rgba(0,113,227,0.10);
}
.brandTitle {
  font-weight: 650;
  letter-spacing: -0.2px;
}
.brandSub {
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}

.stepper {
  display: flex;
  gap: 10px;
  align-items: center;
}
.dot {
  width: 10px; height: 10px;
  border-radius: 999px;
  background: rgba(17,17,20,0.10);
}
.dot.on { background: var(--blue); transform: scale(1.18); }

.wizardBody {
  display: grid;
  grid-template-columns: 1.2fr 0.9fr;
  min-height: 680px;
}
@media (max-width: 1050px){
  .wizardBody { grid-template-columns: 1fr; }
}

.leftPane {
  padding: 46px 46px 38px 46px;
}
@media (max-width: 1050px){
  .leftPane { padding: 32px 22px 22px 22px; }
}

.rightPane {
  background: #F0F0F2;
  border-left: 1px solid var(--line);
  padding: 44px 34px;
}
@media (max-width: 1050px){
  .rightPane { border-left: none; border-top: 1px solid var(--line); }
}

.h2 {
  font-size: 40px;
  font-weight: 700;
  letter-spacing: -1.2px;
  margin: 0 0 10px 0;
}
.desc {
  font-size: 16px;
  line-height: 1.65;
  color: var(--muted);
  margin: 0 0 22px 0;
  max-width: 720px;
}

.miniHint {
  font-size: 13px;
  line-height: 1.55;
  color: var(--muted);
  padding: 14px 14px;
  background: #F7F7FA;
  border: 1px solid var(--line);
  border-radius: 18px;
  margin-top: 12px;
}

.callout {
  padding: 16px 16px;
  background: #F7FAFF;
  border: 1px solid rgba(0,113,227,0.18);
  border-radius: 18px;
  color: #0B2D55;
  font-size: 13px;
  line-height: 1.55;
}

.smallCaps {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.8px;
  color: var(--muted2);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.rightTitle {
  font-size: 18px;
  font-weight: 650;
  letter-spacing: -0.2px;
  margin: 0 0 10px 0;
}
.rightBody {
  font-size: 13px;
  line-height: 1.7;
  color: var(--muted);
  margin: 0 0 18px 0;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
}
.chip {
  border-radius: 999px;
  background: var(--chip);
  color: var(--chipText);
  border: 1px solid var(--line);
  padding: 8px 12px;
  font-size: 12px;
}

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
  background-color: #FBFBFD !important;
  border: 1px solid rgba(17,17,20,0.16) !important;
  border-radius: 16px !important;
  padding: 14px 16px !important;
  font-size: 16px !important;
  color: #111114 !important;
  transition: all 140ms ease;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: rgba(0,113,227,0.65) !important;
  box-shadow: 0 0 0 4px rgba(0,113,227,0.12) !important;
  background-color: #FFFFFF !important;
}

label {
  font-size: 12px !important;
  font-weight: 700 !important;
  color: var(--muted2) !important;
  letter-spacing: 0.4px;
}

div.stButton > button {
  background-color: var(--blue);
  color: white;
  font-size: 16px;
  font-weight: 600;
  padding: 14px 26px;
  border-radius: 999px;
  border: none;
  box-shadow: 0 10px 24px rgba(0,113,227,0.22);
  transition: transform 120ms ease, box-shadow 120ms ease, background-color 120ms ease;
}
div.stButton > button:hover {
  background-color: var(--blue2);
  transform: translateY(-1px);
  box-shadow: 0 14px 34px rgba(0,113,227,0.28);
}

.secondaryBtn button {
  background: #F5F5F7 !important;
  color: #111114 !important;
  border: 1px solid var(--line) !important;
  box-shadow: none !important;
}
.ghostBtn button {
  background: transparent !important;
  color: #111114 !important;
  border: 1px solid var(--line) !important;
  box-shadow: none !important;
}

.kpiBox {
  background: #F5F5F7;
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 18px 18px;
}
.kpiPrice {
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -1.5px;
  margin: 6px 0 2px 0;
}
.kpiSub {
  font-size: 13px;
  color: var(--muted);
}

hr { border: none; border-top: 1px solid var(--line); margin: 18px 0; }
</style>
""",
    unsafe_allow_html=True
)

# =============================================================================
# SESSION STATE
# =============================================================================
def ss_init(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

ss_init("page", "landing")
ss_init("step", 1)
ss_init("payment_ok", False)
ss_init("api_key", "")

# Brand intake model
ss_init("brand_name", "")
ss_init("brand_url", "")
ss_init("industry", "")
ss_init("audience", "")
ss_init("offer", "")
ss_init("proof", "")
ss_init("competitors", "")
ss_init("positioning", "")
ss_init("personality_traits", [])
ss_init("values", "")
ss_init("voice_sliders", {"clarity": 7, "warmth": 6, "boldness": 6, "formality": 4})
ss_init("do_say", "")
ss_init("dont_say", "")
ss_init("visual_keywords", [])
ss_init("visual_avoid", "")
ss_init("color_bias", "Neutral with one accent")
ss_init("type_bias", "Modern sans")
ss_init("doc_depth", "Standard")
ss_init("generated_blueprint", None)
ss_init("generated_markdown", None)

# =============================================================================
# UTILITIES
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
    """
    Lightweight brand intelligence.
    Pull title, meta description, og tags, and a few headings.
    """
    data = {
        "title": "",
        "description": "",
        "og_title": "",
        "og_description": "",
        "headings": [],
        "snippets": []
    }
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code >= 400:
            return data
        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        data["title"] = title

        desc = ""
        dtag = soup.find("meta", attrs={"name": "description"})
        if dtag and dtag.get("content"):
            desc = dtag.get("content").strip()
        data["description"] = desc

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
            if txt and 40 <= len(txt) <= 180:
                snippets.append(txt)
        data["snippets"] = snippets[:6]

        return data
    except Exception:
        return data

def set_chip_list(key: str, value: str, max_items: int = 6):
    value = value.strip()
    if not value:
        return
    current = st.session_state.get(key, [])
    if value in current:
        return
    if len(current) >= max_items:
        current = current[: max_items - 1]
    current.append(value)
    st.session_state[key] = current

def remove_chip(key: str, value: str):
    current = st.session_state.get(key, [])
    st.session_state[key] = [c for c in current if c != value]

def dots(current: int, total: int):
    return "".join([f'<div class="dot {"on" if i == current else ""}"></div>' for i in range(1, total + 1)])

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
            return False, "Positioning is required."
        return True, ""
    if step == 4:
        if len(st.session_state.personality_traits) < 3:
            return False, "Pick at least 3 personality traits."
        return True, ""
    if step == 5:
        if len(st.session_state.visual_keywords) < 3:
            return False, "Pick at least 3 visual keywords."
        return True, ""
    return True, ""

def sanitize_pdf_text(text: str) -> str:
    # Keep simple latin1 compatibility for FPDF.
    # Avoid fancy punctuation so PDFs do not break.
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

def render_pdf_from_markdown(md: str, brand: str) -> bytes:
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 10)
            self.set_text_color(90, 90, 100)
            self.cell(0, 10, f"{brand.upper()}  BRAND BIBLE", 0, 1, "C")
            self.ln(2)

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=16)

    # Cover
    pdf.add_page()
    pdf.set_text_color(17, 17, 20)
    pdf.set_font("Arial", "B", 26)
    pdf.ln(30)
    pdf.multi_cell(0, 12, sanitize_pdf_text(brand))
    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(107, 107, 115)
    pdf.ln(4)
    pdf.multi_cell(0, 7, sanitize_pdf_text("Brand Bible generated by the Brand Bible Generator"))
    pdf.ln(10)
    pdf.set_text_color(17, 17, 20)

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
            pdf.multi_cell(0, 5.5, sanitize_pdf_text(line))

    return pdf.output(dest="S").encode("latin-1")

def build_intake_payload(site_data: dict) -> dict:
    return {
        "brand_name": st.session_state.brand_name.strip(),
        "brand_url": st.session_state.brand_url.strip(),
        "industry": st.session_state.industry.strip(),
        "audience": st.session_state.audience.strip(),
        "offer": st.session_state.offer.strip(),
        "proof": st.session_state.proof.strip(),
        "competitors": st.session_state.competitors.strip(),
        "positioning": st.session_state.positioning.strip(),
        "personality_traits": st.session_state.personality_traits,
        "values": st.session_state.values.strip(),
        "voice_sliders": st.session_state.voice_sliders,
        "do_say": st.session_state.do_say.strip(),
        "dont_say": st.session_state.dont_say.strip(),
        "visual_keywords": st.session_state.visual_keywords,
        "visual_avoid": st.session_state.visual_avoid.strip(),
        "color_bias": st.session_state.color_bias,
        "type_bias": st.session_state.type_bias,
        "doc_depth": st.session_state.doc_depth,
        "site_intelligence": site_data,
    }

def gemini_generate_blueprint(intake: dict) -> dict:
    """
    Two stage generation:
    1) Strict JSON blueprint
    2) Polished Markdown from blueprint
    """
    genai.configure(api_key=st.session_state.api_key.strip())
    model = genai.GenerativeModel("gemini-1.5-flash")

    json_schema_hint = {
        "brand": {
            "name": "string",
            "one_liner": "string",
            "category": "string",
            "audience": "string",
            "offer": "string",
            "positioning_statement": "string"
        },
        "strategy": {
            "core_problem": "string",
            "insight": "string",
            "promise": "string",
            "reasons_to_believe": ["string"],
            "competitors": ["string"],
            "differentiators": ["string"]
        },
        "essence": {
            "mission": "string",
            "vision": "string",
            "values": ["string"],
            "personality_traits": ["string"],
            "brand_beliefs": ["string"]
        },
        "voice": {
            "voice_principles": ["string"],
            "tone_sliders_explained": {
                "clarity": "string",
                "warmth": "string",
                "boldness": "string",
                "formality": "string"
            },
            "do_say": ["string"],
            "dont_say": ["string"],
            "sample_lines": {
                "taglines": ["string"],
                "about_blurb": "string",
                "product_copy": "string",
                "social_caption": "string"
            }
        },
        "visual": {
            "visual_keywords": ["string"],
            "visual_avoid": ["string"],
            "color_system": {
                "approach": "string",
                "palette_notes": "string",
                "sample_hex": ["string"]
            },
            "typography": {
                "approach": "string",
                "headline_style": "string",
                "body_style": "string"
            },
            "imagery": {
                "principles": ["string"],
                "composition_notes": "string",
                "lighting_notes": "string",
                "subjects_to_seek": ["string"],
                "subjects_to_avoid": ["string"]
            },
            "layout_rules": ["string"]
        },
        "usage": {
            "quick_checks": ["string"],
            "examples": {
                "good_example": "string",
                "bad_example": "string"
            }
        }
    }

    prompt_json = f"""
You are a legendary brand strategy agency.
Create a brand bible blueprint as STRICT JSON only.
No commentary. No markdown. No code fences.
Follow this schema shape exactly and fill it with specific, realistic content:

SCHEMA SHAPE:
{json.dumps(json_schema_hint, ensure_ascii=False, indent=2)}

INTAKE:
{json.dumps(intake, ensure_ascii=False, indent=2)}

QUALITY BAR:
Write like a premium agency.
Avoid generic filler. Be concrete and usable.
Keep it aligned to the provided intake.
If intake is missing, infer carefully from site_intelligence.
"""

    r1 = model.generate_content(prompt_json)
    text = r1.text.strip()

    # Clean common failures
    text = text.strip("` \n")
    text = re.sub(r"^json\s*", "", text, flags=re.I)

    try:
        blueprint = json.loads(text)
        return blueprint
    except Exception:
        # Try to salvage by extracting first JSON object
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise

def blueprint_to_markdown(blueprint: dict) -> str:
    b = blueprint

    def bullet(lines):
        return "\n".join([f"* {x}" for x in lines if str(x).strip()])

    md = []
    md.append(f"# {b['brand']['name']}")
    md.append("")
    md.append("## Snapshot")
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
    md.append(bullet(b["strategy"]["reasons_to_believe"]))
    md.append("")
    md.append("### Differentiators")
    md.append(bullet(b["strategy"]["differentiators"]))
    md.append("")
    md.append("### Competitive set")
    md.append(bullet(b["strategy"]["competitors"]))
    md.append("")
    md.append("## Essence")
    md.append(f"**Mission:** {b['essence']['mission']}")
    md.append(f"**Vision:** {b['essence']['vision']}")
    md.append("")
    md.append("### Values")
    md.append(bullet(b["essence"]["values"]))
    md.append("")
    md.append("### Personality traits")
    md.append(bullet(b["essence"]["personality_traits"]))
    md.append("")
    md.append("### Brand beliefs")
    md.append(bullet(b["essence"]["brand_beliefs"]))
    md.append("")
    md.append("## Voice")
    md.append("### Voice principles")
    md.append(bullet(b["voice"]["voice_principles"]))
    md.append("")
    md.append("### Tone sliders explained")
    md.append(f"* Clarity: {b['voice']['tone_sliders_explained']['clarity']}")
    md.append(f"* Warmth: {b['voice']['tone_sliders_explained']['warmth']}")
    md.append(f"* Boldness: {b['voice']['tone_sliders_explained']['boldness']}")
    md.append(f"* Formality: {b['voice']['tone_sliders_explained']['formality']}")
    md.append("")
    md.append("### Do say")
    md.append(bullet(b["voice"]["do_say"]))
    md.append("")
    md.append("### Do not say")
    md.append(bullet(b["voice"]["dont_say"]))
    md.append("")
    md.append("### Copy starters")
    md.append("**Taglines**")
    md.append(bullet(b["voice"]["sample_lines"]["taglines"]))
    md.append("")
    md.append("**About blurb**")
    md.append(b["voice"]["sample_lines"]["about_blurb"])
    md.append("")
    md.append("**Product copy**")
    md.append(b["voice"]["sample_lines"]["product_copy"])
    md.append("")
    md.append("**Social caption**")
    md.append(b["voice"]["sample_lines"]["social_caption"])
    md.append("")
    md.append("## Visual direction")
    md.append("### Keywords")
    md.append(bullet(b["visual"]["visual_keywords"]))
    md.append("")
    md.append("### Avoid")
    md.append(bullet(b["visual"]["visual_avoid"]))
    md.append("")
    md.append("### Color system")
    md.append(f"**Approach:** {b['visual']['color_system']['approach']}")
    md.append(b["visual"]["color_system"]["palette_notes"])
    md.append("")
    md.append("**Sample hex**")
    md.append(bullet(b["visual"]["color_system"]["sample_hex"]))
    md.append("")
    md.append("### Typography")
    md.append(f"**Approach:** {b['visual']['typography']['approach']}")
    md.append(f"**Headlines:** {b['visual']['typography']['headline_style']}")
    md.append(f"**Body:** {b['visual']['typography']['body_style']}")
    md.append("")
    md.append("### Imagery")
    md.append("**Principles**")
    md.append(bullet(b["visual"]["imagery"]["principles"]))
    md.append("")
    md.append(f"**Composition:** {b['visual']['imagery']['composition_notes']}")
    md.append(f"**Lighting:** {b['visual']['imagery']['lighting_notes']}")
    md.append("")
    md.append("**Subjects to seek**")
    md.append(bullet(b["visual"]["imagery"]["subjects_to_seek"]))
    md.append("")
    md.append("**Subjects to avoid**")
    md.append(bullet(b["visual"]["imagery"]["subjects_to_avoid"]))
    md.append("")
    md.append("### Layout rules")
    md.append(bullet(b["visual"]["layout_rules"]))
    md.append("")
    md.append("## Usage")
    md.append("### Quick checks")
    md.append(bullet(b["usage"]["quick_checks"]))
    md.append("")
    md.append("### Examples")
    md.append("**Good**")
    md.append(b["usage"]["examples"]["good_example"])
    md.append("")
    md.append("**Bad**")
    md.append(b["usage"]["examples"]["bad_example"])
    md.append("")

    return "\n".join(md)

def run_generation(site_data: dict):
    intake = build_intake_payload(site_data)
    blueprint = gemini_generate_blueprint(intake)
    md = blueprint_to_markdown(blueprint)
    st.session_state.generated_blueprint = blueprint
    st.session_state.generated_markdown = md

def reset_all():
    keep = {"page": st.session_state.page}
    st.session_state.clear()
    for k, v in keep.items():
        st.session_state[k] = v
    # Re init
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
    ss_init("personality_traits", [])
    ss_init("values", "")
    ss_init("voice_sliders", {"clarity": 7, "warmth": 6, "boldness": 6, "formality": 4})
    ss_init("do_say", "")
    ss_init("dont_say", "")
    ss_init("visual_keywords", [])
    ss_init("visual_avoid", "")
    ss_init("color_bias", "Neutral with one accent")
    ss_init("type_bias", "Modern sans")
    ss_init("doc_depth", "Standard")
    ss_init("generated_blueprint", None)
    ss_init("generated_markdown", None)

# =============================================================================
# LANDING
# =============================================================================
if st.session_state.page == "landing":
    st.markdown(
        """
<div class="hero enter">
  <div class="eyebrow">Brand system generator</div>
  <div class="h1">Build a brand bible that feels agency made.</div>
  <div class="sub">
    A guided interview that captures strategy, voice, and visual direction in minutes.
    Then delivers a clean, client ready PDF you can hand to a designer, a team, or a future you.
  </div>
  <div class="pillRow">
    <div class="pill">Guided intake with examples</div>
    <div class="pill">Website intelligence</div>
    <div class="pill">Structured brand blueprint</div>
    <div class="pill">Premium PDF output</div>
    <div class="pill">One time price 99</div>
  </div>
  <div class="grid3">
    <div class="featureCard">
      <div class="featureTitle">Strategy that has teeth</div>
      <p class="featureBody">Positioning, differentiators, reasons to believe, and usage checks that prevent vague brand mush.</p>
    </div>
    <div class="featureCard">
      <div class="featureTitle">Voice people can actually write with</div>
      <p class="featureBody">Principles, do and do not language, and copy starters that hold up across web, ads, and product.</p>
    </div>
    <div class="featureCard">
      <div class="featureTitle">Visual direction designers trust</div>
      <p class="featureBody">Keywords, avoids, color approach, typography approach, and imagery rules ready for a moodboard or brief.</p>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True
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
    TOTAL_STEPS = 7

    # Top shell
    st.markdown('<div class="wizardShell enter">', unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="wizardTop">
  <div class="brandmark">
    <div class="logoDot"></div>
    <div>
      <div class="brandTitle">Brand Bible Generator</div>
      <div class="brandSub">A guided brand interview</div>
    </div>
  </div>
  <div class="stepper">
    {dots(st.session_state.step, TOTAL_STEPS)}
  </div>
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown('<div class="wizardBody">', unsafe_allow_html=True)
    left_col, right_col = st.columns([1.2, 0.9], gap="large")

    # Right pane content helper
    def right_panel(title: str, body: str, chips_list: list[str] | None = None):
        with right_col:
            st.markdown('<div class="rightPane">', unsafe_allow_html=True)
            st.markdown(f'<div class="smallCaps">Guide</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="rightTitle">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="rightBody">{body}</div>', unsafe_allow_html=True)
            if chips_list:
                st.markdown('<div class="chips">', unsafe_allow_html=True)
                for c in chips_list:
                    st.markdown(f'<div class="chip">{c}</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown('<div class="callout">Tip: answer like you are briefing a designer and a copywriter at the same time. Specific beats clever.</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # Left pane
    with left_col:
        st.markdown('<div class="leftPane">', unsafe_allow_html=True)

        # Step 1
        if st.session_state.step == 1:
            st.markdown('<div class="h2">Start with signals.</div>', unsafe_allow_html=True)
            st.markdown('<div class="desc">We will pull a few cues from your site, then ask only what the model cannot reliably infer.</div>', unsafe_allow_html=True)

            st.text_input("Brand name", key="brand_name", placeholder="Example Oura")
            st.text_input("Website", key="brand_url", placeholder="Example ouraring.com")
            st.text_input("Industry", key="industry", placeholder="Example health tech")
            st.text_input("Gemini API key", key="api_key", type="password")
            st.markdown(
                '<div class="miniHint">Your key stays in your browser session. It is only used to generate your document.</div>',
                unsafe_allow_html=True
            )

            cols = st.columns([1, 1, 2])
            with cols[0]:
                st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                if st.button("Reset"):
                    reset_all()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with cols[1]:
                if st.button("Continue"):
                    ok, msg = validate_step(1)
                    if not ok:
                        st.warning(msg)
                    else:
                        st.session_state.step = 2
                        st.rerun()

            right_panel(
                "What happens next",
                "If you provide a site, we will extract a few useful cues such as the title, meta description, and headings. Then we use your answers to lock in positioning and voice.",
                ["Fast", "Specific", "Client ready"]
            )

        # Step 2
        elif st.session_state.step == 2:
            st.markdown('<div class="h2">Audience and offer.</div>', unsafe_allow_html=True)
            st.markdown('<div class="desc">This is where most generators fail. Do not describe everyone. Describe the buyer with a problem and a context.</div>', unsafe_allow_html=True)

            st.text_area(
                "Audience",
                key="audience",
                height=100,
                placeholder="Who is this for, in one crisp paragraph. Include role, situation, and what they care about."
            )
            st.text_area(
                "Offer",
                key="offer",
                height=90,
                placeholder="What do you sell or provide. Include the outcome, not just the feature."
            )
            st.text_area(
                "Proof",
                key="proof",
                height=90,
                placeholder="Why should anyone believe you. Metrics, credibility, process, patents, years, results, or social proof."
            )

            nav = st.columns([1, 2, 1])
            with nav[0]:
                st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                if st.button("Back"):
                    st.session_state.step = 1
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with nav[2]:
                if st.button("Continue"):
                    ok, msg = validate_step(2)
                    if not ok:
                        st.warning(msg)
                    else:
                        st.session_state.step = 3
                        st.rerun()

            right_panel(
                "How to answer in premium mode",
                "Imagine a smart friend asks: who is it for, what do they want, and why you. If a designer read only this, could they already picture the brand in the world.",
                ["Role", "Context", "Outcome", "Proof"]
            )

        # Step 3
        elif st.session_state.step == 3:
            st.markdown('<div class="h2">Positioning.</div>', unsafe_allow_html=True)
            st.markdown('<div class="desc">Say what you are, who you are for, and why you are the obvious choice. One strong paragraph beats ten weak ones.</div>', unsafe_allow_html=True)

            st.text_area(
                "Competitive set",
                key="competitors",
                height=80,
                placeholder="List competitors or alternatives. Brands, categories, DIY, spreadsheets, agencies, whatever the buyer compares you to."
            )
            st.text_area(
                "Positioning statement",
                key="positioning",
                height=120,
                placeholder="Example: For X, Brand is the Y that delivers Z, because A. Unlike B."
            )

            nav = st.columns([1, 2, 1])
            with nav[0]:
                st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                if st.button("Back"):
                    st.session_state.step = 2
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with nav[2]:
                if st.button("Continue"):
                    ok, msg = validate_step(3)
                    if not ok:
                        st.warning(msg)
                    else:
                        st.session_state.step = 4
                        st.rerun()

            right_panel(
                "Positioning that does not sound fake",
                "Name the category, then narrow the audience, then claim a clear advantage that you can defend. If you cannot defend it, do not say it.",
                ["Category", "Narrow audience", "Defendable edge"]
            )

        # Step 4
        elif st.session_state.step == 4:
            st.markdown('<div class="h2">Personality and voice.</div>', unsafe_allow_html=True)
            st.markdown('<div class="desc">Pick traits you can write with. Then calibrate tone like a mixing board.</div>', unsafe_allow_html=True)

            trait_presets = [
                "Precise", "Warm", "Bold", "Calm", "Playful", "Minimal", "Luxurious",
                "Technical", "Human", "Provocative", "Optimistic", "Authoritative"
            ]

            st.markdown("**Choose up to 6 traits**")
            preset_cols = st.columns(4)
            for i, t in enumerate(trait_presets):
                with preset_cols[i % 4]:
                    if st.button(t, key=f"trait_{t}"):
                        set_chip_list("personality_traits", t, max_items=6)
                        st.rerun()

            if st.session_state.personality_traits:
                st.markdown("**Selected**")
                chip_cols = st.columns(6)
                for i, c in enumerate(st.session_state.personality_traits):
                    with chip_cols[i % 6]:
                        st.markdown('<div class="ghostBtn">', unsafe_allow_html=True)
                        if st.button(f"Remove {c}", key=f"rm_trait_{c}"):
                            remove_chip("personality_traits", c)
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)

            st.text_area(
                "Values in plain language",
                key="values",
                height=90,
                placeholder="3 to 6 values. Write them like actions, not posters."
            )

            st.markdown("**Tone sliders**")
            st.session_state.voice_sliders["clarity"] = st.slider("Clarity", 1, 10, st.session_state.voice_sliders["clarity"])
            st.session_state.voice_sliders["warmth"] = st.slider("Warmth", 1, 10, st.session_state.voice_sliders["warmth"])
            st.session_state.voice_sliders["boldness"] = st.slider("Boldness", 1, 10, st.session_state.voice_sliders["boldness"])
            st.session_state.voice_sliders["formality"] = st.slider("Formality", 1, 10, st.session_state.voice_sliders["formality"])

            st.text_area(
                "Do say",
                key="do_say",
                height=80,
                placeholder="Words, phrases, and patterns you want. Short bullets are fine."
            )
            st.text_area(
                "Do not say",
                key="dont_say",
                height=80,
                placeholder="Words, clichés, and patterns you want to avoid."
            )

            nav = st.columns([1, 2, 1])
            with nav[0]:
                st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                if st.button("Back"):
                    st.session_state.step = 3
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with nav[2]:
                if st.button("Continue"):
                    ok, msg = validate_step(4)
                    if not ok:
                        st.warning(msg)
                    else:
                        st.session_state.step = 5
                        st.rerun()

            right_panel(
                "Why sliders beat adjectives",
                "Adjectives are vague. Sliders force tradeoffs. A brand can be warm and precise, but if it is also bold and formal, the writing needs a very intentional rhythm.",
                ["Traits", "Sliders", "Do and do not language"]
            )

        # Step 5
        elif st.session_state.step == 5:
            st.markdown('<div class="h2">Visual direction.</div>', unsafe_allow_html=True)
            st.markdown('<div class="desc">We are not designing a logo here. We are defining a visual grammar that makes future work consistent.</div>', unsafe_allow_html=True)

            visual_presets = [
                "Clean", "Editorial", "Swiss", "High contrast", "Soft light", "Tactile",
                "Cinematic", "Technical", "Modern luxury", "Organic", "Playful", "Monochrome"
            ]

            st.markdown("**Choose up to 6 keywords**")
            preset_cols = st.columns(4)
            for i, t in enumerate(visual_presets):
                with preset_cols[i % 4]:
                    if st.button(t, key=f"vk_{t}"):
                        set_chip_list("visual_keywords", t, max_items=6)
                        st.rerun()

            if st.session_state.visual_keywords:
                st.markdown("**Selected**")
                chip_cols = st.columns(6)
                for i, c in enumerate(st.session_state.visual_keywords):
                    with chip_cols[i % 6]:
                        st.markdown('<div class="ghostBtn">', unsafe_allow_html=True)
                        if st.button(f"Remove {c}", key=f"rm_vk_{c}"):
                            remove_chip("visual_keywords", c)
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)

            st.text_area(
                "Avoid list",
                key="visual_avoid",
                height=80,
                placeholder="What should it never look like. Examples: childish gradients, stocky corporate, noisy patterns, harsh neon."
            )

            st.selectbox(
                "Color bias",
                ["Neutral with one accent", "Bold and energetic", "Dark and premium", "Warm and human", "Bright and minimal"],
                key="color_bias"
            )
            st.selectbox(
                "Typography bias",
                ["Modern sans", "Editorial serif", "Grotesk neutral", "Tech mono", "Humanist sans"],
                key="type_bias"
            )
            st.selectbox(
                "Document depth",
                ["Standard", "Deep"],
                key="doc_depth"
            )

            nav = st.columns([1, 2, 1])
            with nav[0]:
                st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                if st.button("Back"):
                    st.session_state.step = 4
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with nav[2]:
                if st.button("Continue"):
                    ok, msg = validate_step(5)
                    if not ok:
                        st.warning(msg)
                    else:
                        st.session_state.step = 6
                        st.rerun()

            right_panel(
                "Make it usable for designers",
                "Keywords define direction. Avoids protect quality. Bias selections give the model a spine so the output does not become generic.",
                ["Keywords", "Avoids", "Color approach", "Type approach"]
            )

        # Step 6
        elif st.session_state.step == 6:
            st.markdown('<div class="h2">Unlock generation.</div>', unsafe_allow_html=True)
            st.markdown('<div class="desc">One time purchase. Generate as many times as you want in this session.</div>', unsafe_allow_html=True)

            st.markdown('<div class="kpiBox">', unsafe_allow_html=True)
            st.markdown('<div class="smallCaps">Total</div>', unsafe_allow_html=True)
            st.markdown('<div class="kpiPrice">99</div>', unsafe_allow_html=True)
            st.markdown('<div class="kpiSub">One time strategic investment.</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            if not st.session_state.payment_ok:
                st.markdown('<div class="miniHint">Payment is mocked here. Replace with Stripe Checkout when you are ready.</div>', unsafe_allow_html=True)
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

            st.markdown("<hr/>", unsafe_allow_html=True)

            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Back"):
                st.session_state.step = 5
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            right_panel(
                "What you get",
                "A structured brand blueprint plus a polished document with strategy, voice, visual direction, and usage checks. The PDF is designed to be handed to a designer or a team without extra explanation.",
                ["Strategy", "Voice", "Visual direction", "Usage checks"]
            )

        # Step 7
        elif st.session_state.step == 7:
            st.markdown('<div class="h2">Synthesis.</div>', unsafe_allow_html=True)
            st.markdown('<div class="desc">We generate a strict blueprint first, then write the brand bible from that blueprint.</div>', unsafe_allow_html=True)

            url = safe_url(st.session_state.brand_url)
            site_data = {}
            if url:
                with st.spinner("Reading your site signals..."):
                    site_data = scrape_site(url)

            if st.session_state.generated_markdown is None:
                progress = st.empty()
                try:
                    progress.info("Building blueprint...")
                    time.sleep(0.25)
                    run_generation(site_data)
                    progress.success("Complete.")
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                    if st.button("Back"):
                        st.session_state.step = 6
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

            if st.session_state.generated_markdown:
                st.success("Brand bible generated.")
                st.download_button(
                    "Download PDF",
                    data=render_pdf_from_markdown(st.session_state.generated_markdown, st.session_state.brand_name.strip() or "Brand"),
                    file_name=f"{(st.session_state.brand_name.strip() or 'Brand').replace(' ', '_')}_Brand_Bible.pdf",
                    mime="application/pdf"
                )

                with st.expander("Preview"):
                    st.markdown(st.session_state.generated_markdown)

                st.markdown("<hr/>", unsafe_allow_html=True)
                cols = st.columns([1, 1, 2])
                with cols[0]:
                    st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                    if st.button("Back"):
                        st.session_state.step = 6
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                with cols[1]:
                    if st.button("Generate again"):
                        st.session_state.generated_blueprint = None
                        st.session_state.generated_markdown = None
                        st.rerun()
                with cols[2]:
                    st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
                    if st.button("New project"):
                        reset_all()
                        st.session_state.page = "wizard"
                        st.session_state.step = 1
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

            right_panel(
                "Why this stays high quality",
                "Blueprint first prevents the model from wandering. Then we render a consistent document that reads like an agency deliverable, not a chat response.",
                ["Blueprint", "Consistent output", "Designer ready"]
            )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)  # wizardBody
    st.markdown("</div>", unsafe_allow_html=True)  # wizardShell
