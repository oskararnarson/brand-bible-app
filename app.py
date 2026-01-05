import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
import concurrent.futures

import streamlit as st
import google.generativeai as genai
from fpdf import FPDF


st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")


# =========================
# Session state
# =========================
def ss_init():
    defaults = {
        "view": "landing",  # landing, commitment, wizard, confirm, generate, done
        "step_index": 0,
        "answers": {},
        "gen_used": 0,
        "gen_max": 5,
        "refine_mode": False,
        "refine_sections": [],
        "brand_name": "",
        "last_json": None,
        "pdf_bytes": None,
        "model_used": "",
        "error": "",
        "debug_last_raw": "",
        "api_key": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.api_key:
        st.session_state.api_key = (st.secrets.get("GEMINI_API_KEY", "") or "").strip()


def reset_for_new_brand(keep_api_key: bool = True):
    api_key = st.session_state.api_key
    st.session_state.view = "landing"
    st.session_state.step_index = 0
    st.session_state.answers = {}
    st.session_state.refine_mode = False
    st.session_state.refine_sections = []
    st.session_state.brand_name = ""
    st.session_state.last_json = None
    st.session_state.pdf_bytes = None
    st.session_state.model_used = ""
    st.session_state.error = ""
    st.session_state.debug_last_raw = ""
    if keep_api_key:
        st.session_state.api_key = api_key
    else:
        st.session_state.api_key = (st.secrets.get("GEMINI_API_KEY", "") or "").strip()


def go(view: str):
    st.session_state.view = view
    st.rerun()


# =========================
# CSS
# =========================
def inject_css():
    st.markdown(
        """
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

.block-container { max-width: 1100px; padding-top: 2.4rem; padding-bottom: 3.2rem; }

:root {
  --bg: #0b0d11;
  --fg: rgba(235,240,255,0.92);
  --muted: rgba(235,240,255,0.70);
  --muted2: rgba(235,240,255,0.55);
  --card: rgba(255,255,255,0.06);
  --card2: rgba(255,255,255,0.04);
  --stroke: rgba(255,255,255,0.10);
  --accent: #1c7dff;
}

html, body { background: var(--bg); color: var(--fg); }
.stApp {
  background:
    radial-gradient(1100px 700px at 20% 35%, rgba(0,120,255,0.18), rgba(0,0,0,0) 60%),
    radial-gradient(900px 600px at 80% 20%, rgba(255,255,255,0.06), rgba(0,0,0,0) 55%),
    #0b0d11;
}

.card {
  background: linear-gradient(180deg, var(--card), var(--card2));
  border: 1px solid var(--stroke);
  border-radius: 22px;
  padding: 28px;
  box-shadow: 0 30px 120px rgba(0,0,0,0.55);
  backdrop-filter: blur(14px);
}

.eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted2);
  margin-bottom: 10px;
}

.heroTitle {
  font-size: 52px;
  line-height: 1.05;
  font-weight: 800;
  margin: 0 0 10px 0;
}

.heroSub {
  font-size: 16px;
  line-height: 1.7;
  color: var(--muted);
  margin-bottom: 18px;
  max-width: 820px;
}

hr.soft {
  border: none;
  height: 1px;
  background: rgba(255,255,255,0.08);
  margin: 18px 0;
}

.pills { display:flex; gap:10px; flex-wrap:wrap; margin-top: 12px; }
.pill {
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  color: rgba(235,240,255,0.75);
}

.bigBtn div.stButton > button {
  width: 280px;
  height: 54px;
  border-radius: 999px;
  font-size: 18px;
  font-weight: 800;
  background: linear-gradient(180deg, #1c7dff, #0d5fe9) !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  box-shadow: 0 18px 50px rgba(0,110,255,0.35);
}
.bigBtn div.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 22px 66px rgba(0,110,255,0.45);
}

.secondaryBtn div.stButton > button {
  height: 44px;
  border-radius: 14px;
  font-weight: 800;
  background: rgba(255,255,255,0.06) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
}

.smallNote { font-size: 12px; color: rgba(235,240,255,0.58); }

label {
  font-size: 11px !important;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(235,240,255,0.55) !important;
  font-weight: 700 !important;
}
.stTextInput input, .stTextArea textarea {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  border-radius: 14px !important;
  color: rgba(235,240,255,0.92) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border: 1px solid rgba(28,125,255,0.75) !important;
  box-shadow: 0 0 0 5px rgba(28,125,255,0.18) !important;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.fadeIn { animation: fadeIn 220ms ease-out; }
</style>
""",
        unsafe_allow_html=True,
    )


# =========================
# Intake data
# =========================
@dataclass
class Section:
    id: str
    title: str
    one_liner: str
    est_minutes: int


@dataclass
class Question:
    id: str
    section_id: str
    title: str
    microcopy: str
    qtype: str  # text, textarea, cards, checkboxes
    placeholder: str = ""
    options: list | None = None
    required: bool = True
    answer_key: str = ""


SECTIONS = [
    Section("foundation", "Foundation", "Strong brands are built on decisions, not descriptions.", 3),
    Section("audience", "Audience", "People buy relief, status or clarity. Decide which one you deliver.", 3),
    Section("positioning", "Positioning", "If you do not define your position, the market will do it for you.", 3),
    Section("voice", "Voice", "Tone is what people remember when they forget details.", 3),
    Section("visual", "Visual direction", "Taste is a strategy, not decoration.", 3),
]

QUESTIONS = [
    Question("q1", "foundation", "Brand name", "The name is the anchor. Everything else follows.", "text",
             placeholder="Example: Oura", answer_key="brand_name"),
    Question("q2", "foundation", "Define the brand in one sentence", "If this is vague, the rest will be noise.", "textarea",
             placeholder="We help ... by ...", answer_key="one_sentence"),
    Question("q3", "foundation", "Why does this brand deserve to exist", "Not your origin story. The reason this matters.", "textarea",
             placeholder="Because ...", answer_key="why_exist"),
    Question("q4", "foundation", "What is the misunderstood problem you are here to fix", "The market's lazy assumption that you reject.", "textarea",
             placeholder="Most people think ... but ...", answer_key="misunderstood_problem"),
    Question("q5", "foundation", "What do you sell in reality", "Not the product. The outcome people pay for.", "textarea",
             placeholder="We sell ...", answer_key="real_outcome"),
    Question("q6", "foundation", "What is your hard no", "The boundary that keeps the brand clean.", "textarea",
             placeholder="We will never ...", answer_key="hard_no"),

    Question("q7", "audience", "Describe one core customer you would recognize instantly", "Write one real person, not a segment.", "textarea",
             placeholder="They are ... They care about ...", answer_key="core_customer"),
    Question("q8", "audience", "What do they want but rarely say out loud", "This lever is where competitors usually fail.", "textarea",
             placeholder="Secretly they want ...", answer_key="secret_want"),
    Question("q9", "audience", "What stops them from buying", "Name the objection in their words.", "textarea",
             placeholder="I am not sure because ...", answer_key="primary_objection"),
    Question("q10", "audience", "What convinces them", "Proof they trust, not claims you like.", "textarea",
             placeholder="They trust ...", answer_key="trust_trigger"),
    Question("q11", "audience", "What misconception about your category must be broken", "The myth you refuse to repeat.", "textarea",
             placeholder="People assume ...", answer_key="category_myth"),
    Question("q12", "audience", "What is the worst experience they could have with you", "Define what must never happen.", "textarea",
             placeholder="They must never feel ...", answer_key="worst_experience"),

    Question("q13", "positioning", "What brand do you refuse to resemble", "Your anti model clarifies you fast.", "textarea",
             placeholder="We refuse to feel like ...", answer_key="anti_brand"),
    Question("q14", "positioning", "Finish this sentence: They are the brand that ...", "Write the truth, not a slogan.", "textarea",
             placeholder="They are the brand that ...", answer_key="positioning_sentence"),
    Question("q15", "positioning", "What is your unfair advantage", "Hard to copy, even with money.", "textarea",
             placeholder="We have ... that others cannot ...", answer_key="unfair_advantage"),
    Question("q16", "positioning", "What wrong category do people place you in", "Where people misfile you.", "text",
             placeholder="Example: productivity app", answer_key="wrong_category"),
    Question("q17", "positioning", "What category do you actually own", "The simplest category that makes you instantly understood.", "text",
             placeholder="Example: recovery tech", answer_key="right_category"),
    Question("q18", "positioning", "Pick an animal that matches your posture and energy", "Not cute. Useful shorthand.", "cards",
             options=["Fox", "Hawk", "Panther", "Owl", "Dolphin", "Other"], answer_key="animal"),

    Question("q19", "voice", "Three words you must sound like", "If you choose friendly, you have chosen nothing.", "text",
             placeholder="Example: precise, calm, bold", answer_key="tone_words"),
    Question("q20", "voice", "Three banned words", "If you use these, the brand becomes generic.", "text",
             placeholder="Example: innovative, seamless, disruptive", answer_key="banned_words"),
    Question("q21", "voice", "What is your signature belief", "The opinion that creates gravity.", "textarea",
             placeholder="We believe ...", answer_key="signature_belief"),
    Question("q22", "voice", "Write one close sentence sales can use", "If this is unclear, the brand is unclear.", "textarea",
             placeholder="The simplest truth is ...", answer_key="close_sentence"),
    Question("q23", "voice", "Write what a satisfied customer would say", "Write it like a real person talking.", "textarea",
             placeholder="Honestly, I ...", answer_key="customer_quote"),
    Question("q24", "voice", "Choose your voice energy", "Choose energy, not adjectives.", "cards",
             options=["Calm", "Confident", "Bold", "Sharp", "Warm", "Clinical"], answer_key="voice_energy"),

    Question("q25", "visual", "List 3 to 5 taste reference brands and why", "Name them fast. One word why is enough.", "textarea",
             placeholder="Brand: why\nBrand: why", answer_key="taste_refs"),
    Question("q26", "visual", "Select vibes to avoid", "What would instantly make you look wrong.", "checkboxes",
             options=["Corporate", "Startup hype", "Luxury cliche", "Playful cartoon", "Sterile tech", "Lifestyle fluff", "Trend chasing"],
             required=True, answer_key="avoid_vibes"),
    Question("q27", "visual", "If the brand were a place, what place is it", "This sets layout and atmosphere.", "cards",
             options=["Gallery", "High end hotel", "Workshop", "Library", "Clinic", "Studio", "Other"], answer_key="brand_place"),
    Question("q28", "visual", "What should people feel before they understand", "First impression matters more than features.", "cards",
             options=["Calm", "Controlled", "Excited", "Safe", "Powerful", "Curious"], answer_key="first_impression"),
    Question("q29", "visual", "What must never appear in your visuals", "Hard constraints save time later.", "textarea",
             placeholder="Never use ...", answer_key="never_visuals"),
    Question("q30", "visual", "What are you afraid this could become if done wrong", "Name the failure mode.", "textarea",
             placeholder="If we get this wrong, it becomes ...", answer_key="fear"),
]


def get_section(section_id: str) -> Section:
    for s in SECTIONS:
        if s.id == section_id:
            return s
    return SECTIONS[0]


def get_question(qid: str) -> Question:
    for q in QUESTIONS:
        if q.id == qid:
            return q
    raise KeyError(qid)


def build_wizard_steps(refine_mode: bool, refine_sections: list[str]) -> list[dict]:
    steps: list[dict] = []
    allowed_sections = set(refine_sections) if refine_mode else None

    for sec in SECTIONS:
        if allowed_sections is not None and sec.id not in allowed_sections:
            continue
        steps.append({"type": "section_intro", "section_id": sec.id})
        for q in QUESTIONS:
            if q.section_id == sec.id:
                steps.append({"type": "question", "question_id": q.id})
    return steps


# =========================
# Gemini helpers
# =========================
PREFERRED_MODEL_CONTAINS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0",
    "gemini",
]


def utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def list_generation_models() -> list[str]:
    out = []
    try:
        for m in genai.list_models():
            name = getattr(m, "name", "") or ""
            methods = getattr(m, "supported_generation_methods", None) or []
            if name and "generateContent" in methods:
                out.append(name)
    except Exception:
        return []
    return out


def choose_models_to_try() -> list[str]:
    avail = list_generation_models()
    if not avail:
        return PREFERRED_MODEL_CONTAINS[:]

    chosen: list[str] = []
    for p in PREFERRED_MODEL_CONTAINS:
        for n in avail:
            if p in n and n not in chosen:
                chosen.append(n)
    for n in avail:
        if n not in chosen:
            chosen.append(n)
    return chosen


def build_schema_prompt(brand_name: str, answers: dict, version_str: str, is_refine: bool, refine_focus: str) -> str:
    answers_json = json.dumps(answers, ensure_ascii=False, indent=2)

    refine_clause = ""
    if is_refine:
        refine_clause = (
            "\nRefinement mode is active.\n"
            "Refine the existing system.\n"
            "Keep what works. Sharpen what is vague.\n"
            "Do not reinvent unless necessary.\n"
            f"Refinement focus: {refine_focus}\n"
        )

    schema = (
        "{\n"
        '  "meta": { "brand_name": "", "version": "", "generated_date": "" },\n'
        '  "executive_summary": { "decisions": [""] },\n'
        '  "positioning": { "positioning_statement": "", "category": "", "anti_position": "" },\n'
        '  "audience": { "core_customer": "", "core_tension": "", "primary_objection": "", "trust_trigger": "" },\n'
        '  "messaging": { "core_message": "", "key_messages": [ { "message": "", "proof": "" } ] },\n'
        '  "voice": { "principles": [""], "do_say": [""], "do_not_say": [""], "examples": { "before": "", "after": "" } },\n'
        '  "visual_direction": { "intent": "", "feels_like": [""], "never_feels_like": [""] },\n'
        '  "guardrails": { "failure_modes": [""] },\n'
        '  "usage": { "how_to_use": [""] }\n'
        "}\n"
    )

    prompt = (
        "You are a senior brand strategist at a top tier agency.\n"
        "Your job is not to describe. Your job is to decide.\n"
        "Be opinionated, concise, and practical.\n"
        "If input is vague, sharpen it.\n"
        "Do not write essays.\n"
        "Do not hedge.\n\n"
        f"{refine_clause}\n"
        "TASK\n"
        "Based on the intake answers below, generate a brand bible as a decision system.\n\n"
        "Return ONLY valid JSON that matches the schema exactly.\n"
        "No markdown. No commentary. No extra keys.\n\n"
        "OUTPUT RULES\n"
        "Write in clear, confident, declarative language.\n"
        "Prefer rules over descriptions.\n"
        "Avoid cliches, hype, and generic startup language.\n"
        "Never say: this brand aims to\n"
        "Never say: this brand seeks to\n\n"
        "JSON SCHEMA\n"
        f"{schema}\n"
        "INPUT\n"
        f"Brand name: {brand_name}\n"
        f"Requested version: {version_str}\n"
        f"Generated date (UTC): {utc_date_str()}\n\n"
        "Intake answers JSON:\n"
        f"{answers_json}\n\n"
        "Return JSON only.\n"
    )
    return prompt


def extract_json_object(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("{") and t.endswith("}"):
        return t
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if not m:
        raise ValueError("Model did not return JSON.")
    return m.group(0).strip()


def generate_schema_json(prompt: str, timeout_s: int = 35) -> tuple[dict, str, str]:
    models_to_try = choose_models_to_try()
    last_err = None
    last_raw = ""

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(model.generate_content, prompt)
                resp = fut.result(timeout=timeout_s)

            raw = (getattr(resp, "text", "") or "").strip()
            last_raw = raw

            data = json.loads(extract_json_object(raw))
            for k in ["meta", "executive_summary", "positioning", "audience", "messaging", "voice", "visual_direction", "guardrails", "usage"]:
                if k not in data:
                    raise ValueError("JSON missing required keys.")
            return data, model_name, last_raw

        except concurrent.futures.TimeoutError:
            last_err = RuntimeError(f"Timeout after {timeout_s} seconds.")
        except Exception as e:
            last_err = e

    raise RuntimeError(f"Generation failed. Last error: {last_err}. Raw: {last_raw[:220]}")


def generate_with_retry(prompt: str, timeout_s: int = 35) -> tuple[dict, str, str]:
    try:
        return generate_schema_json(prompt, timeout_s=timeout_s)
    except Exception:
        tightened = prompt + "\nIMPORTANT: Return ONLY valid JSON. No extra text. No code fences.\n"
        return generate_schema_json(tightened, timeout_s=timeout_s)


# =========================
# PDF rendering with FPDF
# =========================
def _safe_pdf_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2026", "...")
    s = s.replace("\u2022", "-")  # bullet • -> hyphen
    return s.encode("latin-1", "replace").decode("latin-1")


class BrandPDF(FPDF):
    def header(self):
        return

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        brand = _safe_pdf_text((self._meta_brand or "").strip())
        if brand:
            self.cell(0, 10, brand, align="L")
        self.set_x(-30)
        self.cell(20, 10, str(self.page_no()), align="R")


def pdf_render(schema: dict, brand_name_fallback: str, version_str: str) -> bytes:
    data = schema or {}
    meta = data.get("meta", {}) or {}

    brand = (meta.get("brand_name", "") or "").strip() or brand_name_fallback or "Brand"
    gen_date = (meta.get("generated_date", "") or "").strip() or utc_date_str()
    ver = (meta.get("version", "") or "").strip() or version_str

    pdf = BrandPDF(format="Letter")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    pdf._meta_brand = brand

    def cover():
        pdf.add_page()
        pdf.set_text_color(25, 28, 35)
        pdf.set_font("Helvetica", "B", 30)
        pdf.ln(35)
        pdf.multi_cell(0, 12, _safe_pdf_text(brand))

        pos = (data.get("positioning", {}) or {}).get("positioning_statement", "") or ""
        pos = _safe_pdf_text(pos.strip())
        if pos:
            pdf.ln(4)
            pdf.set_font("Helvetica", "", 12)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 7, pos)

        pdf.ln(8)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(90, 90, 90)
        pdf.multi_cell(0, 6, "Brand system and decision guide")

        pdf.set_y(-24)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 10, _safe_pdf_text(f"Version {ver}   Generated {gen_date}"), align="L")

    def section_intro(title: str, one_liner: str):
        pdf.add_page()
        pdf.set_text_color(25, 28, 35)
        pdf.set_font("Helvetica", "B", 20)
        pdf.ln(6)
        pdf.multi_cell(0, 10, _safe_pdf_text(title))

        pdf.set_text_color(70, 70, 70)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, _safe_pdf_text(one_liner))

        pdf.ln(4)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.set_draw_color(220, 220, 220)
        pdf.line(18, y, 198, y)
        pdf.ln(10)

    def decision_list(decisions: list[str]):
        pdf.set_text_color(25, 28, 35)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "Decisions", ln=1)

        pdf.set_draw_color(220, 220, 220)
        y = pdf.get_y()
        pdf.line(18, y, 198, y)
        pdf.ln(8)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(45, 45, 45)
        for d in (decisions or [])[:5]:
            d = _safe_pdf_text((d or "").strip())
            if not d:
                continue
            pdf.multi_cell(0, 7, f"- {d}")
            pdf.ln(2)

    def body_text(text: str):
        t = _safe_pdf_text((text or "").strip())
        if not t:
            return
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(45, 45, 45)
        for para in t.split("\n"):
            para = para.strip()
            if not para:
                pdf.ln(2)
                continue
            pdf.multi_cell(0, 7, para)
            pdf.ln(2)

    def simple_list(title: str, items: list[str], limit: int = 8):
        if title:
            pdf.set_text_color(25, 28, 35)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, _safe_pdf_text(title), ln=1)
            pdf.set_draw_color(220, 220, 220)
            y = pdf.get_y()
            pdf.line(18, y, 198, y)
            pdf.ln(8)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(45, 45, 45)
        count = 0
        for it in items or []:
            if count >= limit:
                break
            it = _safe_pdf_text((it or "").strip())
            if not it:
                continue
            pdf.multi_cell(0, 7, f"- {it}")
            count += 1
        pdf.ln(2)

    def do_dont(left_title: str, left_items: list[str], right_title: str, right_items: list[str]):
        left_items = [x for x in (left_items or []) if (x or "").strip()][:7]
        right_items = [x for x in (right_items or []) if (x or "").strip()][:7]

        x0 = 18
        y0 = pdf.get_y()
        col_gap = 10
        col_w = (198 - 18 - col_gap) / 2

        def col(x: float, y: float, title: str, items: list[str]) -> float:
            pdf.set_xy(x, y)
            pdf.set_text_color(25, 28, 35)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(col_w, 6, _safe_pdf_text(title), ln=1)

            pdf.set_xy(x, pdf.get_y() + 2)
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 11)
            for it in items:
                it = _safe_pdf_text((it or "").strip())
                if not it:
                    continue
                pdf.set_x(x)
                pdf.multi_cell(col_w, 7, f"- {it}")
                pdf.ln(1)
            return pdf.get_y()

        # Divider line across both columns
        pdf.set_draw_color(220, 220, 220)
        pdf.line(18, y0, 198, y0)
        pdf.ln(6)

        y_start = pdf.get_y()
        ly = col(x0, y_start, left_title, left_items)
        ry = col(x0 + col_w + col_gap, y_start, right_title, right_items)

        pdf.set_y(max(ly, ry) + 4)

    def key_messages(items: list[dict]):
        pdf.set_text_color(25, 28, 35)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "Key messages", ln=1)
        pdf.set_draw_color(220, 220, 220)
        y = pdf.get_y()
        pdf.line(18, y, 198, y)
        pdf.ln(8)

        for km in (items or [])[:3]:
            msg = _safe_pdf_text((km.get("message", "") or "").strip())
            proof = _safe_pdf_text((km.get("proof", "") or "").strip())
            if not msg:
                continue
            pdf.set_text_color(25, 28, 35)
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 7, msg)
            if proof:
                pdf.set_text_color(60, 60, 60)
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 6, proof)
            pdf.ln(4)

    cover()

    section_intro("Executive summary", "The decisions that keep this brand consistent.")
    decisions = (data.get("executive_summary", {}) or {}).get("decisions", []) or []
    decision_list(decisions)

    section_intro("Positioning", "Where this brand stands, and what it refuses to be.")
    pos = data.get("positioning", {}) or {}
    body_text((pos.get("positioning_statement", "") or "").strip())

    left = []
    cat = (pos.get("category", "") or "").strip()
    if cat:
        left.append(f"Category: {cat}")
    right = []
    anti = (pos.get("anti_position", "") or "").strip()
    if anti:
        right.append(anti)
    do_dont("What we are", left or ["Clear category ownership."], "What we are not", right or ["Vague, polite, or generic."])

    section_intro("Audience and insight", "One real customer, and what actually moves them.")
    aud = data.get("audience", {}) or {}
    aud_items = [
        (aud.get("core_customer", "") or "").strip(),
        (aud.get("core_tension", "") or "").strip(),
        (aud.get("primary_objection", "") or "").strip(),
        (aud.get("trust_trigger", "") or "").strip(),
    ]
    simple_list("What to know", [x for x in aud_items if x], limit=8)

    section_intro("Messaging system", "Repeatable messages, backed by credible proof.")
    msg = data.get("messaging", {}) or {}
    body_text((msg.get("core_message", "") or "").strip())
    key_messages(msg.get("key_messages", []) or [])

    section_intro("Voice", "Rules that stop the wrong words before they are written.")
    voice = data.get("voice", {}) or {}
    simple_list("Principles", [x for x in (voice.get("principles", []) or []) if (x or "").strip()], limit=6)
    do_dont(
        "Do say",
        [x for x in (voice.get("do_say", []) or []) if (x or "").strip()],
        "Do not say",
        [x for x in (voice.get("do_not_say", []) or []) if (x or "").strip()],
    )
    ex = voice.get("examples", {}) or {}
    before = (ex.get("before", "") or "").strip()
    after = (ex.get("after", "") or "").strip()
    if before or after:
        section_intro("Voice examples", "Before and after. Clear contrast.")
        if before:
            simple_list("Before", [before], limit=1)
        if after:
            simple_list("After", [after], limit=1)

    section_intro("Visual direction", "Taste and constraints, not design specs.")
    vis = data.get("visual_direction", {}) or {}
    body_text((vis.get("intent", "") or "").strip())
    do_dont(
        "Feels like",
        [x for x in (vis.get("feels_like", []) or []) if (x or "").strip()],
        "Never feels like",
        [x for x in (vis.get("never_feels_like", []) or []) if (x or "").strip()],
    )

    section_intro("Guardrails", "How this brand gets ruined. Avoid these.")
    guard = data.get("guardrails", {}) or {}
    simple_list("Failure modes", [x for x in (guard.get("failure_modes", []) or []) if (x or "").strip()], limit=9)

    section_intro("How to use this", "When to open this document, and what not to debate.")
    usage = data.get("usage", {}) or {}
    simple_list("Use it like this", [x for x in (usage.get("how_to_use", []) or []) if (x or "").strip()], limit=9)

    out = pdf.output(dest="S").encode("latin-1", "replace")
    return out


# =========================
# UI helpers
# =========================
def card_start():
    st.markdown('<div class="card fadeIn">', unsafe_allow_html=True)


def card_end():
    st.markdown("</div>", unsafe_allow_html=True)


def render_progress(step_index: int, steps: list[dict]):
    question_steps = [s for s in steps if s["type"] == "question"]
    total_questions = len(question_steps)

    current_question_num = 0
    if steps[step_index]["type"] == "question":
        qid = steps[step_index]["question_id"]
        for i, s in enumerate(question_steps, start=1):
            if s["question_id"] == qid:
                current_question_num = i
                break
    else:
        for s in steps[step_index:]:
            if s["type"] == "question":
                qid = s["question_id"]
                for i, qs in enumerate(question_steps, start=1):
                    if qs["question_id"] == qid:
                        current_question_num = i
                        break
                break
        if current_question_num == 0:
            current_question_num = total_questions

    progress = min(max((step_index + 1) / max(len(steps), 1), 0.0), 1.0)
    st.progress(progress)

    current_section_id = steps[step_index].get("section_id")
    if steps[step_index]["type"] == "question":
        current_section_id = get_question(steps[step_index]["question_id"]).section_id
    sec = get_section(current_section_id or SECTIONS[0].id)
    sec_index = [s.id for s in SECTIONS].index(sec.id) + 1

    st.caption(f"Section {sec_index} of {len(SECTIONS)}   Question {current_question_num} of {total_questions}")


def render_question_input(q: Question):
    key = f"ans_{q.answer_key}"
    current = st.session_state.answers.get(q.answer_key)

    if q.qtype == "text":
        val = st.text_input(q.title, value=current or "", placeholder=q.placeholder, key=key)
        st.session_state.answers[q.answer_key] = val.strip()

    elif q.qtype == "textarea":
        val = st.text_area(q.title, value=current or "", placeholder=q.placeholder, height=160, key=key)
        st.session_state.answers[q.answer_key] = val.strip()

    elif q.qtype == "cards":
        options = q.options or []
        idx = options.index(current) if current in options else 0
        val = st.radio(q.title, options=options, index=idx, key=key)
        if val == "Other":
            other_key = f"{key}_other"
            other_val = st.text_input("Other", value=st.session_state.answers.get(q.answer_key + "_other", ""), key=other_key)
            st.session_state.answers[q.answer_key + "_other"] = other_val.strip()
            st.session_state.answers[q.answer_key] = "Other"
        else:
            st.session_state.answers[q.answer_key] = val

    elif q.qtype == "checkboxes":
        options = q.options or []
        current_list = current if isinstance(current, list) else []
        chosen = []
        st.write(q.title)
        for opt in options:
            checked = opt in current_list
            if st.checkbox(opt, value=checked, key=f"{key}_{opt}"):
                chosen.append(opt)
        st.session_state.answers[q.answer_key] = chosen

    else:
        st.session_state.answers[q.answer_key] = current or ""


def validate_current_step(step: dict) -> tuple[bool, str]:
    if step["type"] != "question":
        return True, ""

    q = get_question(step["question_id"])
    val = st.session_state.answers.get(q.answer_key)

    if not q.required:
        return True, ""

    if q.answer_key == "brand_name":
        if not (val or "").strip():
            return False, "Brand name is required."
        return True, ""

    if q.qtype == "checkboxes":
        if not isinstance(val, list) or len(val) == 0:
            return False, "Select at least one option."
        return True, ""

    if not val or (isinstance(val, str) and not val.strip()):
        return False, "Please write a short answer to continue."
    return True, ""


# =========================
# Views
# =========================
def landing_view():
    card_start()
    st.markdown('<div class="eyebrow">Brand system generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle">Build a brand that stays consistent when you are not in the room</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="heroSub">A guided brand interview that turns strategy, voice and visual direction into a clear, usable brand bible you can actually follow.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="pills">
          <div class="pill">Decision system</div>
          <div class="pill">Non boring intake</div>
          <div class="pill">PDF deliverable</div>
          <div class="pill">Built like an agency</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2], gap="large")
    with col1:
        st.subheader("Why a brand bible matters")
        st.write("Most brands do not fail because of bad ideas.")
        st.write("They fail because nothing is defined.")
        st.write("A brand bible is not a document. It is a decision system.")
        st.write("")
        st.write("With a brand system, teams decide faster, argue less, and stay consistent without trying.")

    with col2:
        st.subheader("What you get")
        st.write("Positioning and category clarity")
        st.write("Messaging system with proof points")
        st.write("Voice rules with examples")
        st.write("Visual direction and guardrails")
        st.write("")
        st.caption("One time purchase. Includes room to refine.")

    st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
    if st.button("Start brand interview"):
        go("commitment")
    st.markdown("</div>", unsafe_allow_html=True)

    if not st.session_state.api_key:
        st.info("Developer note: Set GEMINI_API_KEY in secrets.toml for generation to work.")
        with st.expander("Developer settings"):
            st.session_state.api_key = st.text_input("Gemini API key", type="password", value=st.session_state.api_key)

    st.markdown('<div class="smallNote">Includes 5 generations. Most people use 2 to 3.</div>', unsafe_allow_html=True)
    card_end()


def commitment_view():
    card_start()
    st.markdown('<div class="eyebrow">Before we start</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">A quick guided interview</div>', unsafe_allow_html=True)
    st.write("Takes about 12 to 15 minutes.")
    st.write("One question at a time.")
    st.write("You can pause and resume at any time.")
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("landing")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        if st.button("Begin interview"):
            st.session_state.refine_mode = False
            st.session_state.refine_sections = []
            st.session_state.step_index = 0
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)
    card_end()


def wizard_view():
    steps = build_wizard_steps(st.session_state.refine_mode, st.session_state.refine_sections)
    if not steps:
        st.session_state.error = "Wizard has no steps."
        go("landing")
        return

    st.session_state.step_index = max(0, min(st.session_state.step_index, len(steps) - 1))
    step = steps[st.session_state.step_index]

    card_start()
    render_progress(st.session_state.step_index, steps)
    st.write("")
    st.markdown(f'<div class="fadeIn" id="step_{st.session_state.step_index}">', unsafe_allow_html=True)

    if step["type"] == "section_intro":
        sec = get_section(step["section_id"])
        st.subheader(sec.title)
        st.write(sec.one_liner)
        st.caption(f"{sec.est_minutes} minutes")
    else:
        q = get_question(step["question_id"])
        if q.answer_key == "brand_name":
            st.session_state.brand_name = (st.session_state.answers.get("brand_name", "") or "").strip()
        st.subheader(q.title)
        st.caption(q.microcopy)
        render_question_input(q)

    st.markdown("</div>", unsafe_allow_html=True)
    st.write("")

    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back", key="wiz_back"):
            if st.session_state.step_index > 0:
                st.session_state.step_index -= 1
                st.rerun()
            else:
                go("commitment")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        next_label = "Continue" if step["type"] == "section_intro" else "Next"
        if st.button(next_label, key="wiz_next"):
            ok, msg = validate_current_step(step)
            if not ok:
                st.error(msg)
            else:
                if st.session_state.step_index >= len(steps) - 1:
                    go("confirm")
                else:
                    st.session_state.step_index += 1
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    card_end()


def confirm_view():
    card_start()
    st.markdown('<div class="eyebrow">Confirmation</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">This is enough to build a real brand system</div>', unsafe_allow_html=True)
    st.write("You will get positioning, messaging, voice rules, visual direction, and guardrails.")
    st.caption("Agencies typically charge thousands for this step.")
    st.write("")
    st.write(f"Generations remaining: {max(st.session_state.gen_max - st.session_state.gen_used, 0)} of {st.session_state.gen_max}")

    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    with st.expander("Review your inputs", expanded=False):
    for q in QUESTIONS:
        ans = st.session_state.answers.get(q.answer_key)
        if ans is None or ans == "" or ans == []:
            continue
        st.markdown(f"**{q.title}**")
        if isinstance(ans, list):
            st.write(", ".join(ans))
        else:
            st.write(ans)
        st.markdown("")


    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back to interview"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        remaining = st.session_state.gen_max - st.session_state.gen_used
        disabled = remaining <= 0
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        if st.button("Generate brand bible", disabled=disabled):
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)

        if disabled:
            st.info("No generations remaining. Start a new brand or add more generations later.")

    card_end()


def generate_view():
    card_start()
    st.markdown('<div class="eyebrow">Generating</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Building your brand bible</div>', unsafe_allow_html=True)
    st.write("This usually takes under a minute.")
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    api_key = (st.session_state.api_key or "").strip()
    if not api_key:
        st.error("Missing API key. Set GEMINI_API_KEY in secrets.toml.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("landing")
        st.markdown("</div>", unsafe_allow_html=True)
        card_end()
        return

    remaining = st.session_state.gen_max - st.session_state.gen_used
    if remaining <= 0:
        st.error("No generations remaining.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("done" if st.session_state.pdf_bytes else "confirm")
        st.markdown("</div>", unsafe_allow_html=True)
        card_end()
        return

    st.session_state.error = ""
    st.session_state.model_used = ""
    st.session_state.debug_last_raw = ""

    genai.configure(api_key=api_key)

    brand = (st.session_state.answers.get("brand_name", "") or "").strip() or "Brand"
    version_str = str(st.session_state.gen_used + 1)

    refine_focus = "Everything"
    if st.session_state.refine_mode and st.session_state.refine_sections:
        refine_focus = ", ".join(st.session_state.refine_sections)

    prompt = build_schema_prompt(
        brand_name=brand,
        answers=st.session_state.answers,
        version_str=version_str,
        is_refine=st.session_state.refine_mode,
        refine_focus=refine_focus,
    )

    stages = ["Analyzing inputs", "Defining positioning", "Writing voice rules", "Setting visual direction", "Assembling PDF"]
    stage_slot = st.empty()

    try:
        with st.spinner("Working..."):
            for s in stages[:2]:
                stage_slot.write(s)
                time.sleep(0.12)

            data, model_used, raw = generate_with_retry(prompt, timeout_s=35)
            st.session_state.last_json = data
            st.session_state.model_used = model_used
            st.session_state.debug_last_raw = raw

            for s in stages[2:]:
                stage_slot.write(s)
                time.sleep(0.10)

            pdf = pdf_render(data, brand_name_fallback=brand, version_str=version_str)
            st.session_state.pdf_bytes = pdf

            st.session_state.gen_used += 1
            st.session_state.refine_mode = False
            st.session_state.refine_sections = []

            go("done")

    except Exception as e:
        st.session_state.error = str(e)
        st.error(f"Generation failed: {st.session_state.error}")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back to confirmation"):
            go("confirm")
        st.markdown("</div>", unsafe_allow_html=True)

    card_end()


def done_view():
    card_start()
    st.markdown('<div class="eyebrow">Ready</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Download your brand bible</div>', unsafe_allow_html=True)

    remaining = max(st.session_state.gen_max - st.session_state.gen_used, 0)
    st.caption(f"Generations remaining: {remaining} of {st.session_state.gen_max}")

    if not st.session_state.pdf_bytes:
        st.error("No PDF found yet.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("confirm")
        st.markdown("</div>", unsafe_allow_html=True)
        card_end()
        return

    brand = (st.session_state.answers.get("brand_name", "") or "").strip() or "Brand"
    filename = f"{brand}_Brand_Bible_v{st.session_state.gen_used}.pdf"

    st.download_button(
        "Download PDF",
        data=st.session_state.pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True,
    )

    if st.session_state.model_used:
        st.caption(f"Model used: {st.session_state.model_used}")

    with st.expander("Preview JSON", expanded=False):
        st.json(st.session_state.last_json or {})

    st.markdown('<hr class="soft" />', unsafe_allow_html=True)
    st.subheader("Refine")
    st.caption("Refinement works best when you focus on one area.")

    focus = st.radio(
        "What would you like to refine",
        options=["Positioning", "Messaging", "Voice", "Visual direction", "Everything"],
        index=0,
        horizontal=True,
        key="refine_focus_radio",
    )

    focus_to_sections = {
        "Positioning": ["positioning"],
        "Messaging": ["foundation", "audience", "positioning"],
        "Voice": ["voice"],
        "Visual direction": ["visual"],
        "Everything": ["foundation", "audience", "positioning", "voice", "visual"],
    }

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Start new brand"):
            reset_for_new_brand(keep_api_key=True)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        can_refine = remaining > 0
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Refine inputs", disabled=not can_refine):
            st.session_state.refine_mode = True
            st.session_state.refine_sections = focus_to_sections.get(focus, ["foundation"])
            st.session_state.step_index = 0
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)

    with col3:
        can_generate = remaining > 0
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        if st.button("Generate refined version", disabled=not can_generate):
            st.session_state.refine_mode = True
            st.session_state.refine_sections = focus_to_sections.get(focus, ["foundation"])
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)

    if remaining <= 0:
        st.info("No generations remaining. Start a new brand now. Add more generations later.")

    card_end()


# =========================
# Router
# =========================
def main():
    ss_init()
    inject_css()

    view = st.session_state.view

    if view == "landing":
        landing_view()
    elif view == "commitment":
        commitment_view()
    elif view == "wizard":
        wizard_view()
    elif view == "confirm":
        confirm_view()
    elif view == "generate":
        generate_view()
    else:
        done_view()


if __name__ == "__main__":
    main()
