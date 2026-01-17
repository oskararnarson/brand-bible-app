import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Tuple, List

import streamlit as st
from fpdf import FPDF

try:
    import requests
except Exception:
    requests = None

# Optional providers
try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================================================
# App config
# =========================================================
st.set_page_config(page_title="Messaging Rules Generator", layout="wide", page_icon="◼")


# =========================================================
# Session state
# =========================================================
def ss_init():
    defaults = {
        "view": "landing",
        "step_index": 0,
        "answers": {},
        "gen_used": 0,
        "gen_max": 5,
        "last_json": None,
        "pdf_bytes": None,
        "model_used": "",
        "error": "",
        # Provider
        "provider": "openai",  # openai or gemini
        "gemini_key": "",
        "openai_key": "",
        "openai_model": "gpt-4.1-mini",
        # Advanced
        "temperature": 0.25,
        "debug_json": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.gemini_key:
        st.session_state.gemini_key = (st.secrets.get("GEMINI_API_KEY", "") or "").strip()

    if not st.session_state.openai_key:
        st.session_state.openai_key = (st.secrets.get("OPENAI_API_KEY", "") or "").strip()


def go(view: str):
    st.session_state.view = view
    st.rerun()


def reset_app(keep_keys: bool = True):
    saved = {
        "gemini_key": st.session_state.gemini_key,
        "openai_key": st.session_state.openai_key,
        "openai_model": st.session_state.openai_model,
        "provider": st.session_state.provider,
        "temperature": st.session_state.temperature,
        "debug_json": st.session_state.debug_json,
    }
    st.session_state.clear()
    ss_init()
    if keep_keys:
        for k, v in saved.items():
            st.session_state[k] = v


# =========================================================
# Premium clean CSS (less noisy, more trust)
# =========================================================
def inject_css():
    st.markdown(
        """
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

.block-container { max-width: 1140px; padding-top: 4.75rem !important; padding-bottom: 3.0rem; }

:root{
  --bg:#0e1116;
  --panel:#121722;
  --panel2:#0f141f;
  --stroke:rgba(255,255,255,0.10);
  --text:rgba(245,248,255,0.92);
  --muted:rgba(245,248,255,0.68);
  --muted2:rgba(245,248,255,0.52);
  --accent:#4ea1ff;
  --danger:#ff4e6a;
  --ok:#4cffb2;
}

html, body { background: var(--bg); color: var(--text); }

.stApp{
  background:
    radial-gradient(900px 500px at 22% 22%, rgba(78,161,255,0.16), rgba(0,0,0,0) 60%),
    radial-gradient(800px 600px at 85% 30%, rgba(255,255,255,0.06), rgba(0,0,0,0) 55%),
    var(--bg);
}

.smallEyebrow{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted2);
  margin-bottom: 12px;
}

.heroTitle{
  font-size: 56px;
  line-height: 1.03;
  font-weight: 920;
  margin: 0 0 12px 0;
}

.heroSub{
  font-size: 16px;
  line-height: 1.7;
  color: var(--muted);
  margin-bottom: 18px;
  max-width: 920px;
}

hr.soft{
  border:none;
  height:1px;
  background: rgba(255,255,255,0.08);
  margin: 20px 0;
}

.panel{
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 18px;
  padding: 16px 16px;
}

.kpi{
  display:flex;
  gap:14px;
  flex-wrap:wrap;
  margin-top: 10px;
}
.kpi .pill{
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  color: rgba(245,248,255,0.70);
}

.bigBtn div.stButton > button{
  width: 320px;
  height: 54px;
  border-radius: 999px;
  font-size: 18px;
  font-weight: 900;
  background: linear-gradient(180deg, #4ea1ff, #2c7be8) !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  box-shadow: 0 16px 44px rgba(44,123,232,0.30);
}
.bigBtn div.stButton > button:hover{
  transform: translateY(-1px);
  box-shadow: 0 22px 64px rgba(44,123,232,0.40);
}

.secondaryBtn div.stButton > button{
  height: 44px;
  border-radius: 14px;
  font-weight: 900;
  background: rgba(255,255,255,0.06) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
}

label{
  font-size: 11px !important;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(245,248,255,0.50) !important;
  font-weight: 800 !important;
}

.stTextInput input, .stTextArea textarea{
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  border-radius: 14px !important;
  color: rgba(245,248,255,0.92) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus{
  border: 1px solid rgba(78,161,255,0.75) !important;
  box-shadow: 0 0 0 5px rgba(78,161,255,0.16) !important;
}

.helpText{
  color: rgba(245,248,255,0.70);
  font-size: 14px;
  line-height: 1.65;
}

.miniNote{
  color: rgba(245,248,255,0.52);
  font-size: 13px;
  line-height: 1.6;
}

</style>
""",
        unsafe_allow_html=True,
    )


# =========================================================
# Intake: 10 questions
# =========================================================
@dataclass
class Question:
    id: str
    title: str
    micro: str
    qtype: str
    key: str
    placeholder: str = ""
    required: bool = True


QUESTIONS: list[Question] = [
    Question("q1", "Company or product name", "This appears on the cover.", "text", "brand_name", placeholder="Example: MindOS"),
    Question("q2", "What do you sell in reality", "Outcome and identity shift, not features.", "textarea", "sell_outcome",
             placeholder="We sell ___ so that ___ becomes possible without ___."),
    Question("q3", "The belief you assert as fact", "Your doctrine, written like a hard truth.", "textarea", "doctrine_belief",
             placeholder="We believe ___ is true, and the market is wrong about ___."),
    Question("q4", "The misunderstood problem you fix", "Name the false assumption, then the real cause.", "textarea", "misunderstood_problem",
             placeholder="People think ___, but the real problem is ___."),
    Question("q5", "Who this is for", "One recognisable person, not a segment.", "textarea", "core_customer",
             placeholder="They are the kind of person who ___. They hate ___. They want ___."),
    Question("q6", "What this is not", "The anti model. This keeps the output clean.", "textarea", "anti_model",
             placeholder="We refuse to feel like ___. We will not promise ___."),
    Question("q7", "What language is banned", "Words, tones, metaphors, and soft claims you refuse.", "textarea", "banned_language",
             placeholder="Never say ___. Never imply ___. Never sound like ___."),
    Question("q8", "Proof standard", "What evidence counts. What does not count.", "textarea", "proof_standard",
             placeholder="We earn trust through ___. Anecdotes and vibes do not count as ___."),
    Question("q9", "One sentence sales is allowed to use", "Short, sharp, and honest.", "textarea", "sales_sentence",
             placeholder="If you are ___ and want ___, this is built for you."),
    Question("q10", "Failure mode if done wrong", "Name the hollow version so we can prevent it.", "textarea", "failure_mode",
             placeholder="If we get this wrong, it becomes ___."),
]


def steps() -> list[dict]:
    out: list[dict] = [{"type": "intro"}]
    for q in QUESTIONS:
        out.append({"type": "question", "qid": q.id})
    out.append({"type": "confirm"})
    return out


def get_question(qid: str) -> Question:
    for q in QUESTIONS:
        if q.id == qid:
            return q
    raise KeyError(qid)


# =========================================================
# Provider + prompt
# =========================================================
def utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def extract_json_object(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("{") and t.endswith("}"):
        return t
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if not m:
        raise ValueError("Model did not return JSON.")
    return m.group(0).strip()


def build_prompt(answers: dict, version_str: str) -> str:
    brand = (answers.get("brand_name", "") or "").strip()
    answers_json = json.dumps(answers, ensure_ascii=False, indent=2)

    # This is a "sellable" artifact structure: short, testable, usable.
    schema = (
        "{\n"
        '  "meta": { "brand_name": "", "version": "", "date_utc": "" },\n'
        '  "cover": { "subtitle": "", "confidence_line": "" },\n'
        '  "north_star": {\n'
        '    "what_we_sell": "",\n'
        '    "who_it_is_for": "",\n'
        '    "who_it_is_not_for": ""\n'
        "  },\n"
        '  "rules": {\n'
        '    "non_negotiables": [""],\n'
        '    "banned_language": [""],\n'
        '    "allowed_patterns": [""],\n'
        '    "forbidden_patterns": [""],\n'
        '    "proof_standard": ""\n'
        "  },\n"
        '  "voice": {\n'
        '    "must_sound_like": [""],\n'
        '    "must_not_sound_like": [""],\n'
        '    "writing_rules": [""]\n'
        "  },\n"
        '  "examples": {\n'
        '    "approved_sales_sentence": "",\n'
        '    "approved_headlines": [""],\n'
        '    "approved_openers": [""],\n'
        '    "rewrites": [ { "rule": "", "bad": "", "good": "" } ]\n'
        "  },\n"
        '  "approval": {\n'
        '    "red_flags": [""],\n'
        '    "approval_checklist": [""],\n'
        '    "rejection_phrases": [""]\n'
        "  },\n"
        '  "guardrails": {\n'
        '    "failure_modes": [""],\n'
        '    "how_this_gets_ruined": [""]\n'
        "  }\n"
        "}\n"
    )

    # Strict, practical, non fluffy.
    prompt = (
        "You are a senior messaging strategist.\n"
        "Write a sellable operational ruleset.\n"
        "This is not a brand book.\n"
        "\n"
        "CRITICAL BEHAVIOR\n"
        "Do not copy the user answers.\n"
        "Derive sharper rules from them.\n"
        "Write rules that can be used to approve or reject copy.\n"
        "No hype. No cliches. No vague positivity.\n"
        "Be specific and enforceable.\n"
        "\n"
        "OUTPUT FORMAT\n"
        "Return ONLY valid JSON matching the schema exactly.\n"
        "No markdown. No commentary. No extra keys.\n"
        "\n"
        "SCHEMA\n"
        f"{schema}\n"
        "\n"
        "INPUT\n"
        f"Brand name: {brand}\n"
        f"Version: {version_str}\n"
        f"Date UTC: {utc_date_str()}\n"
        "\n"
        "Answers JSON\n"
        f"{answers_json}\n"
        "\n"
        "Return JSON only.\n"
    )
    return prompt


def _pick_gemini_models() -> List[str]:
    if genai is None:
        return []
    models = []
    try:
        for m in genai.list_models():
            name = getattr(m, "name", "") or ""
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" in methods and "gemini" in name.lower():
                models.append(name)
    except Exception:
        return []
    # Prefer flash like models first, then pro, then everything else.
    def score(n: str) -> int:
        nl = n.lower()
        if "flash" in nl:
            return 0
        if "pro" in nl:
            return 1
        return 2
    models = sorted(models, key=score)
    return models


def generate_with_gemini(prompt: str, api_key: str, timeout_s: int = 40) -> Tuple[dict, str]:
    if genai is None:
        raise RuntimeError("google-generativeai is not installed.")
    genai.configure(api_key=api_key)

    candidates = _pick_gemini_models()
    if not candidates:
        raise RuntimeError("No Gemini models available for generateContent.")

    last_err: Optional[Exception] = None
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            # google SDK does not accept timeout everywhere; we keep it simple.
            resp = model.generate_content(prompt)
            raw = (getattr(resp, "text", "") or "").strip()
            data = json.loads(extract_json_object(raw))
            return data, model_name
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Gemini generation failed: {last_err}")


def generate_with_openai(prompt: str, api_key: str, model: str, temperature: float) -> Tuple[dict, str]:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed.")
    client = OpenAI(api_key=api_key)

    resp = client.responses.create(
        model=model,
        input=prompt,
        temperature=float(temperature),
        max_output_tokens=2400,
    )
    raw = (getattr(resp, "output_text", "") or "").strip()
    data = json.loads(extract_json_object(raw))

    required = ["meta", "cover", "north_star", "rules", "voice", "examples", "approval", "guardrails"]
    for k in required:
        if k not in data:
            raise ValueError("JSON missing required keys.")
    return data, model


# =========================================================
# PDF rendering: premium spec, no bullets, no overlap
# =========================================================
IN_TO_MM = 25.4


def inch(x: float) -> float:
    return x * IN_TO_MM


def safe_text(s: Any, latin_only: bool = False) -> str:
    if s is None:
        return ""
    t = str(s)
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2026", "...")
    t = t.replace("\u00A0", " ")
    # avoid long dash characters in output text
    t = t.replace("\u2014", "-").replace("\u2013", "-")
    if latin_only:
        t = t.encode("latin-1", "replace").decode("latin-1")
    return t


class RulesPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.margin_l = 16
        self.margin_r = 16
        self.margin_t = 16
        self.margin_b = 16

        self.brand_name = ""
        self._latin_only = False
        self._suppress_footer = False

        # Palette
        self.c_bg = (255, 255, 255)
        self.c_text = (20, 24, 32)
        self.c_muted = (92, 98, 112)
        self.c_panel = (246, 247, 249)
        self.c_stroke = (224, 227, 234)
        self.c_accent = (44, 123, 232)

        self.set_auto_page_break(auto=False)

    @property
    def live_w(self) -> float:
        return self.w - self.margin_l - self.margin_r

    @property
    def live_h(self) -> float:
        return self.h - self.margin_t - self.margin_b

    def f_head(self, size: float, bold: bool = True):
        self.set_font("Helvetica", "B" if bold else "", size)

    def f_body(self, size: float, bold: bool = False):
        self.set_font("Helvetica", "B" if bold else "", size)

    def footer(self):
        if self._suppress_footer:
            return
        self.set_y(-self.margin_b + 8)
        self.f_body(8, False)
        self.set_text_color(*self.c_muted)
        self.set_x(self.margin_l)
        self.cell(0, 4, safe_text(self.brand_name), align="L")
        self.set_x(self.w - self.margin_r - 12)
        self.cell(12, 4, str(self.page_no()), align="R")

    def page_bg(self):
        self.set_fill_color(*self.c_bg)
        self.rect(0, 0, self.w, self.h, style="F")

    def ensure(self, needed_h: float):
        if self.get_y() + needed_h > self.h - self.margin_b:
            self.add_page()
            self.page_bg()
            self.set_xy(self.margin_l, self.margin_t)

    def h_rule(self, y: Optional[float] = None):
        if y is None:
            y = self.get_y()
        self.set_draw_color(*self.c_stroke)
        self.set_line_width(0.4)
        self.line(self.margin_l, y, self.w - self.margin_r, y)

    def title_block(self, title: str, subtitle: Optional[str] = None):
        self.set_xy(self.margin_l, self.margin_t)
        self.set_text_color(*self.c_text)
        self.f_head(22, True)
        self.multi_cell(self.live_w, 10, safe_text(title))
        if subtitle:
            self.ln(1)
            self.set_text_color(*self.c_muted)
            self.f_body(11, False)
            self.multi_cell(self.live_w, 6, safe_text(subtitle))
        self.ln(2)
        self.h_rule()
        self.ln(6)

    def card(self, label: str, body: str, accent: bool = False):
        x = self.margin_l
        w = self.live_w
        pad = 6
        label_h = 6

        self.f_body(11, False)
        lines = self.multi_cell(w - pad * 2, 5.5, safe_text(body), split_only=True)
        body_h = max(len(lines), 1) * 5.5

        h = pad + label_h + 2 + body_h + pad
        self.ensure(h + 2)

        y = self.get_y()

        self.set_fill_color(*self.c_panel)
        self.rect(x, y, w, h, style="F")
        self.set_draw_color(*self.c_stroke)
        self.rect(x, y, w, h)

        if accent:
            self.set_draw_color(*self.c_accent)
            self.set_line_width(1.4)
            self.line(x, y, x, y + h)
            self.set_line_width(0.4)

        self.set_xy(x + pad, y + pad)
        self.set_text_color(*self.c_text)
        self.f_body(11, True)
        self.cell(w - pad * 2, label_h, safe_text(label), ln=1)

        self.set_text_color(*self.c_text)
        self.f_body(11, False)
        self.multi_cell(w - pad * 2, 5.5, safe_text(body))

        self.set_y(y + h + 6)

    def numbered_rules(self, heading: str, rules: List[str], start_index: int = 1):
        rules = [r.strip() for r in (rules or []) if (r or "").strip()]
        if not rules:
            return

        self.ensure(14)
        self.set_text_color(*self.c_text)
        self.f_body(12, True)
        self.cell(self.live_w, 6, safe_text(heading), ln=1)
        self.ln(2)

        idx = start_index
        for r in rules:
            self.rule_row(idx, r)
            idx += 1

        self.ln(2)

    def rule_row(self, idx: int, text: str):
        x = self.margin_l
        w = self.live_w
        pad = 6
        num_w = 10

        self.f_body(11, False)
        lines = self.multi_cell(w - pad * 2 - num_w, 5.5, safe_text(text), split_only=True)
        body_h = max(len(lines), 1) * 5.5
        h = pad + body_h + pad

        self.ensure(h + 2)
        y = self.get_y()

        self.set_fill_color(*self.c_panel)
        self.rect(x, y, w, h, style="F")
        self.set_draw_color(*self.c_stroke)
        self.rect(x, y, w, h)

        self.set_xy(x + pad, y + pad - 0.5)
        self.set_text_color(*self.c_accent)
        self.f_body(11, True)
        self.cell(num_w, 6, str(idx), align="L")

        self.set_xy(x + pad + num_w, y + pad)
        self.set_text_color(*self.c_text)
        self.f_body(11, False)
        self.multi_cell(w - pad * 2 - num_w, 5.5, safe_text(text))

        self.set_y(y + h + 4)

    def two_col(self, left_title: str, left_lines: List[str], right_title: str, right_lines: List[str]):
        left_lines = [s.strip() for s in (left_lines or []) if (s or "").strip()]
        right_lines = [s.strip() for s in (right_lines or []) if (s or "").strip()]

        gap = 8
        w = (self.live_w - gap) / 2
        x1 = self.margin_l
        x2 = self.margin_l + w + gap

        pad = 6

        def height_for(lines: List[str]) -> float:
            if not lines:
                lines = ["None"]
            total = 0.0
            for s in lines:
                self.f_body(11, False)
                wrapped = self.multi_cell(w - pad * 2, 5.5, safe_text(s), split_only=True)
                total += max(len(wrapped), 1) * 5.5 + 3
            return total

        body_h = max(height_for(left_lines), height_for(right_lines))
        h = pad + 6 + 2 + body_h + pad

        self.ensure(h + 2)
        y = self.get_y()

        for x, title, lines in [(x1, left_title, left_lines), (x2, right_title, right_lines)]:
            self.set_fill_color(*self.c_panel)
            self.rect(x, y, w, h, style="F")
            self.set_draw_color(*self.c_stroke)
            self.rect(x, y, w, h)

            self.set_xy(x + pad, y + pad)
            self.set_text_color(*self.c_text)
            self.f_body(11, True)
            self.cell(w - pad * 2, 6, safe_text(title), ln=1)

            self.ln(1)
            self.set_text_color(*self.c_text)
            self.f_body(11, False)

            if not lines:
                lines = ["None"]

            yy = self.get_y()
            for s in lines:
                self.set_xy(x + pad, yy)
                self.multi_cell(w - pad * 2, 5.5, safe_text(s))
                yy = self.get_y() + 3

        self.set_y(y + h + 6)

    def checklist(self, heading: str, items: List[str]):
        items = [s.strip() for s in (items or []) if (s or "").strip()]
        if not items:
            return
        self.ensure(14)
        self.set_text_color(*self.c_text)
        self.f_body(12, True)
        self.cell(self.live_w, 6, safe_text(heading), ln=1)
        self.ln(2)

        for it in items:
            self.card("Check", f"[ ] {it}", accent=False)


def render_pdf(schema: dict) -> bytes:
    meta = schema.get("meta", {}) or {}
    cover = schema.get("cover", {}) or {}
    ns = schema.get("north_star", {}) or {}
    rules = schema.get("rules", {}) or {}
    voice = schema.get("voice", {}) or {}
    ex = schema.get("examples", {}) or {}
    appr = schema.get("approval", {}) or {}
    guard = schema.get("guardrails", {}) or {}

    brand = (meta.get("brand_name", "") or "").strip() or "Brand"
    version = (meta.get("version", "") or "").strip() or "1"
    date_utc = (meta.get("date_utc", "") or "").strip() or utc_date_str()

    pdf = RulesPDF()
    pdf.brand_name = brand

    # Cover
    pdf._suppress_footer = True
    pdf.add_page()
    pdf.page_bg()

    pdf.set_xy(pdf.margin_l, 34)
    pdf.set_text_color(*pdf.c_text)
    pdf.f_head(34, True)
    pdf.multi_cell(pdf.live_w, 14, safe_text(brand))

    subtitle = (cover.get("subtitle", "") or "").strip() or "Messaging Rules"
    conf = (cover.get("confidence_line", "") or "").strip() or "A practical ruleset for writing and approving copy"
    pdf.ln(2)
    pdf.set_text_color(*pdf.c_muted)
    pdf.f_body(12, False)
    pdf.multi_cell(pdf.live_w, 7, safe_text(subtitle))
    pdf.ln(1)
    pdf.set_text_color(*pdf.c_muted)
    pdf.f_body(11, False)
    pdf.multi_cell(pdf.live_w, 6, safe_text(conf))

    pdf.set_y(pdf.h - pdf.margin_b - 18)
    pdf.set_text_color(*pdf.c_muted)
    pdf.f_body(10, False)
    pdf.cell(0, 6, safe_text(f"Version {version}  Date {date_utc}"), ln=1)

    pdf._suppress_footer = False

    # North star
    pdf.add_page()
    pdf.page_bg()
    pdf.set_xy(pdf.margin_l, pdf.margin_t)
    pdf.title_block("North star", "What this is, who it is for, and who it refuses to be.")

    pdf.card("What we sell", (ns.get("what_we_sell", "") or "").strip(), accent=True)
    pdf.card("Who it is for", (ns.get("who_it_is_for", "") or "").strip(), accent=False)
    pdf.card("Who it is not for", (ns.get("who_it_is_not_for", "") or "").strip(), accent=False)

    # Rules
    pdf.add_page()
    pdf.page_bg()
    pdf.set_xy(pdf.margin_l, pdf.margin_t)
    pdf.title_block("Rules", "Constraints that prevent drift. Use these to approve or reject copy.")

    pdf.numbered_rules("Non negotiables", rules.get("non_negotiables", []) or [], start_index=1)

    banned = rules.get("banned_language", []) or []
    allowed = rules.get("allowed_patterns", []) or []
    forbidden = rules.get("forbidden_patterns", []) or []

    pdf.two_col("Allowed patterns", allowed[:10], "Forbidden patterns", forbidden[:10])
    pdf.numbered_rules("Banned language", banned[:12], start_index=1)

    proof = (rules.get("proof_standard", "") or "").strip()
    if proof:
        pdf.card("Proof standard", proof, accent=True)

    # Voice
    pdf.add_page()
    pdf.page_bg()
    pdf.set_xy(pdf.margin_l, pdf.margin_t)
    pdf.title_block("Voice", "How the writing behaves under stress.")

    pdf.two_col(
        "Must sound like",
        (voice.get("must_sound_like", []) or [])[:10],
        "Must not sound like",
        (voice.get("must_not_sound_like", []) or [])[:10],
    )
    pdf.numbered_rules("Writing rules", (voice.get("writing_rules", []) or [])[:14], start_index=1)

    # Examples
    pdf.add_page()
    pdf.page_bg()
    pdf.set_xy(pdf.margin_l, pdf.margin_t)
    pdf.title_block("Examples", "Approved outputs that demonstrate the rules.")

    sales = (ex.get("approved_sales_sentence", "") or "").strip()
    if sales:
        pdf.card("Approved sales sentence", sales, accent=True)

    pdf.two_col(
        "Approved headlines",
        (ex.get("approved_headlines", []) or [])[:10],
        "Approved openers",
        (ex.get("approved_openers", []) or [])[:10],
    )

    rewrites = ex.get("rewrites", []) or []
    cleaned = []
    for it in rewrites[:10]:
        rule = (it.get("rule", "") or "").strip()
        bad = (it.get("bad", "") or "").strip()
        good = (it.get("good", "") or "").strip()
        if rule and bad and good:
            cleaned.append((rule, bad, good))

    if cleaned:
        pdf.add_page()
        pdf.page_bg()
        pdf.set_xy(pdf.margin_l, pdf.margin_t)
        pdf.title_block("Rewrites", "This is the proof that the rules are real.")
        idx = 1
        for rule, bad, good in cleaned[:8]:
            pdf.card(f"Rewrite {idx}  Rule", rule, accent=(idx == 1))
            pdf.two_col("Bad", [bad], "Good", [good])
            idx += 1

    # Approval and guardrails
    pdf.add_page()
    pdf.page_bg()
    pdf.set_xy(pdf.margin_l, pdf.margin_t)
    pdf.title_block("Approval", "A fast way to police quality and consistency.")

    pdf.numbered_rules("Red flags", (appr.get("red_flags", []) or [])[:12], start_index=1)
    pdf.checklist("Approval checklist", (appr.get("approval_checklist", []) or [])[:12])

    rej = (appr.get("rejection_phrases", []) or [])[:10]
    if rej:
        pdf.numbered_rules("Rejection phrases", rej, start_index=1)

    pdf.add_page()
    pdf.page_bg()
    pdf.set_xy(pdf.margin_l, pdf.margin_t)
    pdf.title_block("Guardrails", "How this gets ruined and how to prevent it.")

    pdf.numbered_rules("Failure modes", (guard.get("failure_modes", []) or [])[:12], start_index=1)
    pdf.numbered_rules("How this gets ruined", (guard.get("how_this_gets_ruined", []) or [])[:12], start_index=1)

    out = pdf.output(dest="S")
    return bytes(out) if isinstance(out, (bytes, bytearray)) else str(out).encode("latin-1", "replace")


# =========================================================
# UI helpers
# =========================================================
def render_progress(step_index: int, all_steps: list[dict]):
    total = len([s for s in all_steps if s["type"] == "question"])
    seen = 0
    for i in range(step_index + 1):
        if all_steps[i]["type"] == "question":
            seen += 1
    current_q = max(1, seen) if total else 0
    st.progress(min(max((step_index + 1) / max(len(all_steps), 1), 0.0), 1.0))
    st.caption(f"Question {current_q} of {total}")


def render_question(q: Question):
    key = f"ans_{q.key}"
    current = st.session_state.answers.get(q.key)

    if q.qtype == "text":
        val = st.text_input(q.title, value=current or "", placeholder=q.placeholder, key=key)
        st.session_state.answers[q.key] = (val or "").strip()
    else:
        val = st.text_area(q.title, value=current or "", placeholder=q.placeholder, height=170, key=key)
        st.session_state.answers[q.key] = (val or "").strip()


def validate_step(step: dict) -> Tuple[bool, str]:
    if step["type"] != "question":
        return True, ""
    q = get_question(step["qid"])
    val = st.session_state.answers.get(q.key)

    if not q.required:
        return True, ""

    if q.key == "brand_name" and not (val or "").strip():
        return False, "Name is required."
    if not val or (isinstance(val, str) and not val.strip()):
        return False, "Write a short answer to continue."
    return True, ""


def schema_sanity_check(data: dict) -> None:
    required = ["meta", "cover", "north_star", "rules", "voice", "examples", "approval", "guardrails"]
    for k in required:
        if k not in data:
            raise ValueError("JSON missing required keys.")


# =========================================================
# Views
# =========================================================
def landing_view():
    st.markdown('<div class="smallEyebrow">Operational language</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle">Messaging Rules</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="heroSub">A short interview that produces a usable ruleset. It derives constraints, patterns, examples, and an approval checklist. Built to create trust, not decoration.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="kpi">
          <div class="pill">Sellable PDF deliverable</div>
          <div class="pill">Enforceable rules</div>
          <div class="pill">Approved examples</div>
          <div class="pill">Fast approval checklist</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("What you get")
        st.write("A clear north star and hard constraints.")
        st.write("Approved patterns and forbidden patterns.")
        st.write("Voice behavior rules that prevent drift.")
        st.write("Examples and rewrites that prove the rules are real.")
        st.write("A checklist for approving or rejecting copy fast.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Settings")
        st.session_state.provider = st.selectbox(
            "Provider",
            options=["openai", "gemini"],
            index=0 if st.session_state.provider == "openai" else 1,
        )

        st.session_state.temperature = st.slider("Creativity", min_value=0.0, max_value=0.8, value=float(st.session_state.temperature), step=0.05)

        if st.session_state.provider == "openai":
            st.session_state.openai_key = st.text_input("OpenAI API key", type="password", value=st.session_state.openai_key)
            st.session_state.openai_model = st.text_input("OpenAI model", value=st.session_state.openai_model)
        else:
            st.session_state.gemini_key = st.text_input("Gemini API key", type="password", value=st.session_state.gemini_key)

        st.session_state.debug_json = st.checkbox("Show generated JSON", value=bool(st.session_state.debug_json))
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
    if st.button("Start interview"):
        st.session_state.step_index = 0
        go("wizard")
    st.markdown("</div>", unsafe_allow_html=True)

    st.caption("Tip: If your answers are sharp, the rules become sharp. If your answers are vague, the system will decide for you.")


def wizard_view():
    all_steps = steps()
    st.session_state.step_index = max(0, min(st.session_state.step_index, len(all_steps) - 1))
    step = all_steps[st.session_state.step_index]

    render_progress(st.session_state.step_index, all_steps)
    st.write("")

    if step["type"] == "intro":
        st.subheader("How this works")
        st.caption("Answer 10 questions. The system derives rules and examples. It does not copy your answers.")
        st.markdown('<div class="helpText">Write like you mean it. Short, assertive inputs produce a stronger ruleset.</div>', unsafe_allow_html=True)
        st.write("")
        st.markdown('<div class="miniNote">If you hate a word, ban it. If you hate a vibe, name it.</div>', unsafe_allow_html=True)

    elif step["type"] == "confirm":
        go("confirm")
        return

    else:
        q = get_question(step["qid"])
        st.subheader(q.title)
        st.caption(q.micro)
        render_question(q)

    st.write("")
    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            if st.session_state.step_index > 0:
                st.session_state.step_index -= 1
                st.rerun()
            else:
                go("landing")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        label = "Continue" if step["type"] == "intro" else "Next"
        if st.button(label):
            ok, msg = validate_step(step)
            if not ok:
                st.error(msg)
            else:
                if st.session_state.step_index >= len(all_steps) - 2:
                    go("confirm")
                else:
                    st.session_state.step_index += 1
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def confirm_view():
    st.markdown('<div class="smallEyebrow">Confirmation</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:38px;">Generate Messaging Rules</div>', unsafe_allow_html=True)

    remaining = max(st.session_state.gen_max - st.session_state.gen_used, 0)
    st.caption(f"Generations remaining: {remaining} of {st.session_state.gen_max}")

    with st.expander("Review inputs", expanded=False):
        for q in QUESTIONS:
            ans = st.session_state.answers.get(q.key)
            if not ans:
                continue
            st.markdown(f"**{q.title}**")
            st.write(ans)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back to interview"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        if st.button("Generate PDF", disabled=(remaining <= 0)):
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)


def generate_view():
    st.markdown('<div class="smallEyebrow">Generating</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:38px;">Building your ruleset</div>', unsafe_allow_html=True)
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    remaining = st.session_state.gen_max - st.session_state.gen_used
    if remaining <= 0:
        st.error("No generations remaining.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("confirm")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    brand = (st.session_state.answers.get("brand_name", "") or "").strip()
    if not brand:
        st.error("Name is required.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    prompt = build_prompt(st.session_state.answers, version_str=str(st.session_state.gen_used + 1))
    stage = st.empty()

    try:
        with st.spinner("Working..."):
            stage.write("Deriving rules and examples")
            time.sleep(0.08)

            if st.session_state.provider == "openai":
                if not (st.session_state.openai_key or "").strip():
                    raise RuntimeError("Missing OpenAI API key.")
                schema, model_used = generate_with_openai(
                    prompt=prompt,
                    api_key=(st.session_state.openai_key or "").strip(),
                    model=(st.session_state.openai_model or "gpt-4.1-mini").strip(),
                    temperature=float(st.session_state.temperature),
                )
            else:
                if not (st.session_state.gemini_key or "").strip():
                    raise RuntimeError("Missing Gemini API key.")
                schema, model_used = generate_with_gemini(
                    prompt=prompt,
                    api_key=(st.session_state.gemini_key or "").strip(),
                    timeout_s=40,
                )

            schema_sanity_check(schema)

            stage.write("Rendering PDF")
            time.sleep(0.08)
            pdf_bytes = render_pdf(schema)

        st.session_state.last_json = schema
        st.session_state.model_used = model_used
        st.session_state.pdf_bytes = pdf_bytes
        st.session_state.gen_used += 1
        go("done")

    except Exception as e:
        st.session_state.error = str(e)
        st.error(f"Generation failed: {st.session_state.error}")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("confirm")
        st.markdown("</div>", unsafe_allow_html=True)


def done_view():
    st.markdown('<div class="smallEyebrow">Ready</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:38px;">Download your ruleset</div>', unsafe_allow_html=True)

    remaining = max(st.session_state.gen_max - st.session_state.gen_used, 0)
    st.caption(f"Generations remaining: {remaining} of {st.session_state.gen_max}")

    if not st.session_state.pdf_bytes:
        st.error("No PDF available.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("confirm")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    brand = (st.session_state.answers.get("brand_name", "") or "").strip() or "Brand"
    filename = f"{brand}_Messaging_Rules_v{st.session_state.gen_used}.pdf"

    st.download_button(
        "Download PDF",
        data=st.session_state.pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Start new"):
            reset_app(keep_keys=True)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Generate again", disabled=(remaining <= 0)):
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.debug_json:
        with st.expander("Generated JSON", expanded=False):
            st.json(st.session_state.last_json or {})

    if st.session_state.model_used:
        st.caption(f"Model used: {st.session_state.model_used}")


def main():
    ss_init()
    inject_css()

    view = st.session_state.view
    if view == "landing":
        landing_view()
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
