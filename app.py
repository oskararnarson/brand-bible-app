import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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
        "provider": "gemini",  # gemini or openai
        "gemini_key": "",
        "openai_key": "",
        "openai_model": "gpt-4.1-mini",
        # Images (optional)
        "include_images": False,
        "unsplash_key": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.gemini_key:
        st.session_state.gemini_key = (st.secrets.get("GEMINI_API_KEY", "") or "").strip()

    if not st.session_state.openai_key:
        st.session_state.openai_key = (st.secrets.get("OPENAI_API_KEY", "") or "").strip()

    if not st.session_state.unsplash_key:
        st.session_state.unsplash_key = (st.secrets.get("UNSPLASH_ACCESS_KEY", "") or "").strip()


def go(view: str):
    st.session_state.view = view
    st.rerun()


def reset_app(keep_keys: bool = True):
    saved = {
        "gemini_key": st.session_state.gemini_key,
        "openai_key": st.session_state.openai_key,
        "openai_model": st.session_state.openai_model,
        "unsplash_key": st.session_state.unsplash_key,
        "provider": st.session_state.provider,
        "include_images": st.session_state.include_images,
    }
    st.session_state.clear()
    ss_init()
    if keep_keys:
        for k, v in saved.items():
            st.session_state[k] = v


# =========================================================
# CSS
# =========================================================
def inject_css():
    st.markdown(
        """
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

.block-container { max-width: 1180px; padding-top: 6.0rem !important; padding-bottom: 3.0rem; }

:root{
  --bg:#0b0d11;
  --fg:rgba(235,240,255,0.92);
  --muted:rgba(235,240,255,0.70);
  --muted2:rgba(235,240,255,0.55);
  --card:rgba(255,255,255,0.06);
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

.bigBtn div.stButton > button{
  width: 320px;
  height: 54px;
  border-radius: 999px;
  font-size: 18px;
  font-weight: 900;
  background: linear-gradient(180deg, #1c7dff, #0d5fe9) !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  box-shadow: 0 18px 50px rgba(0,110,255,0.35);
}
.bigBtn div.stButton > button:hover{
  transform: translateY(-1px);
  box-shadow: 0 22px 66px rgba(0,110,255,0.45);
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
  color: rgba(235,240,255,0.55) !important;
  font-weight: 800 !important;
}

.stTextInput input, .stTextArea textarea{
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  border-radius: 14px !important;
  color: rgba(235,240,255,0.92) !important;
}

.stTextInput input:focus, .stTextArea textarea:focus{
  border: 1px solid rgba(28,125,255,0.75) !important;
  box-shadow: 0 0 0 5px rgba(28,125,255,0.18) !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


# =========================================================
# Intake: 10 questions only
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
    Question("q1", "Company or product name", "The label on the ruleset.", "text", "brand_name", placeholder="Example: MindOS"),
    Question("q2", "What do you actually sell", "Not the product. The outcome people pay for.", "textarea", "sell_outcome",
             placeholder="We sell ___ so that ___ no longer has to ___."),
    Question("q3", "The belief you assert as fact", "Your doctrine. Not a slogan.", "textarea", "doctrine_belief",
             placeholder="We believe ___."),
    Question("q4", "The misunderstood problem you fix", "The lazy assumption you reject.", "textarea", "misunderstood_problem",
             placeholder="Most people think ___, but the real problem is ___."),
    Question("q5", "Who this is absolutely for", "Describe one recognisable person, not a segment.", "textarea", "core_customer",
             placeholder="They are the kind of person who ___. They are frustrated by ___."),
    Question("q6", "What this is not", "The anti model. What you refuse to resemble.", "textarea", "anti_model",
             placeholder="We refuse to feel like ___."),
    Question("q7", "What language is banned", "Words, tones, or implications that corrupt the brand.", "textarea", "banned_language",
             placeholder="Never say or imply ___. Never sound like ___."),
    Question("q8", "What proof is required before claims are trusted", "Your evidence standard.", "textarea", "proof_standard",
             placeholder="We earn trust through ___."),
    Question("q9", "One sentence sales is allowed to use", "If this fails, everything fails.", "textarea", "sales_sentence",
             placeholder="If you are ___ and want ___, this exists for you."),
    Question("q10", "Failure mode if done wrong", "The version of this that becomes hollow or performative.", "textarea", "failure_mode",
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

    schema = (
        "{\n"
        '  "meta": { "brand_name": "", "version": "", "date_utc": "" },\n'
        '  "hero": { "headline": "", "subhead": "", "deck_subtitle": "" },\n'
        '  "executive_summary": { "decisions": [""] },\n'
        '  "messaging_rules": {\n'
        '    "what_we_sell": "",\n'
        '    "doctrine": [""],\n'
        '    "allowed_framing_patterns": [""],\n'
        '    "forbidden_framing_patterns": [""],\n'
        '    "banned_words": [""],\n'
        '    "proof_standard": "",\n'
        '    "non_negotiables": [""]\n'
        "  },\n"
        '  "voice_rules": {\n'
        '    "must_sound_like": [""],\n'
        '    "must_not_sound_like": [""],\n'
        '    "rules": [""]\n'
        "  },\n"
        '  "examples": {\n'
        '    "sales_sentence": "",\n'
        '    "headlines": [""],\n'
        '    "social_posts": [""],\n'
        '    "before_after": [ { "rule": "", "before": "", "after": "" } ]\n'
        "  },\n"
        '  "guardrails": {\n'
        '    "failure_modes": [""],\n'
        '    "red_flags": [""],\n'
        '    "approval_checklist": [""]\n'
        "  },\n"
        '  "appendix": {\n'
        '    "color_suggestions": [ { "name": "", "hex": "", "reason": "" } ],\n'
        '    "typography_suggestions": { "primary": "", "secondary": "", "rationale": "" }\n'
        "  }\n"
        "}\n"
    )

    prompt = (
        "You are a senior strategist writing an operational language ruleset.\n"
        "Write rules, constraints, and tests. Do not write a brand book.\n"
        "Do not echo user answers verbatim. Derive sharper rules.\n"
        "Be decisive. If user input is vague, resolve it.\n"
        "No hype. No cliches. No startup buzzwords.\n"
        "Return ONLY valid JSON matching the schema exactly.\n"
        "No markdown. No commentary. No extra keys.\n\n"
        "JSON SCHEMA:\n"
        f"{schema}\n"
        "INPUT:\n"
        f"Brand name: {brand}\n"
        f"Version: {version_str}\n"
        f"Date UTC: {utc_date_str()}\n\n"
        "Intake answers JSON:\n"
        f"{answers_json}\n\n"
        "Return JSON only.\n"
    )
    return prompt


def generate_with_gemini(prompt: str, api_key: str, timeout_s: int = 35) -> tuple[dict, str]:
    if genai is None:
        raise RuntimeError("google-generativeai not installed.")

    genai.configure(api_key=api_key)

    # Discover valid models dynamically
    models = []
    for m in genai.list_models():
        name = getattr(m, "name", "")
        methods = getattr(m, "supported_generation_methods", []) or []
        if "generateContent" in methods:
            models.append(name)

    if not models:
        raise RuntimeError("No Gemini models available for generateContent.")

    last_err = None
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            raw = (getattr(resp, "text", "") or "").strip()
            data = json.loads(extract_json_object(raw))
            return data, model_name
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Gemini generation failed: {last_err}")


def generate_with_openai(prompt: str, api_key: str, model: str) -> tuple[dict, str]:
    if OpenAI is None:
        raise RuntimeError("openai package not installed.")
    client = OpenAI(api_key=api_key)

    resp = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.2,
        max_output_tokens=2200,
    )
    raw = (getattr(resp, "output_text", "") or "").strip()
    data = json.loads(extract_json_object(raw))
    for k in ["meta", "hero", "executive_summary", "messaging_rules", "voice_rules", "examples", "guardrails", "appendix"]:
        if k not in data:
            raise ValueError("JSON missing required keys.")
    return data, model


# =========================================================
# Optional images (off by default)
# =========================================================
UNSPLASH_API = "https://api.unsplash.com"


def _unsplash_headers(access_key: str) -> dict:
    return {
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1",
        "User-Agent": "MessagingRulesGenerator/1.0",
    }


def _download_image_to_temp(url: str) -> Optional[str]:
    if requests is None:
        return None
    try:
        r = requests.get(url, timeout=18, headers={"User-Agent": "MessagingRulesGenerator/1.0"}, allow_redirects=True)
        if r.status_code != 200 or not r.content:
            return None
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        f.write(r.content)
        f.flush()
        f.close()
        if os.path.getsize(f.name) < 50_000:
            try:
                os.unlink(f.name)
            except Exception:
                pass
            return None
        return f.name
    except Exception:
        return None


def unsplash_one(access_key: str, query: str, orientation: str = "landscape") -> Optional[str]:
    if not access_key or requests is None:
        return None
    params = {"query": query, "orientation": orientation, "content_filter": "high", "count": 1}
    try:
        r = requests.get(f"{UNSPLASH_API}/photos/random", headers=_unsplash_headers(access_key), params=params, timeout=18)
        if r.status_code != 200:
            return None
        js = r.json()
        if isinstance(js, list) and js:
            js = js[0]
        urls = (js or {}).get("urls", {}) or {}
        url = urls.get("regular") or urls.get("full") or urls.get("raw")
        if not url:
            return None
        return _download_image_to_temp(url)
    except Exception:
        return None


# =========================================================
# PDF rendering: clean layout, no bullets, no black boxes
# =========================================================
IN_TO_MM = 25.4


def inch(x: float) -> float:
    return x * IN_TO_MM


def safe_text(s: Any, latin_only: bool = False) -> str:
    if s is None:
        return ""
    t = str(s)
    # normalize common punctuation to avoid encoding issues
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2026", "...")
    t = t.replace("\u00A0", " ")
    if latin_only:
        t = t.encode("latin-1", "replace").decode("latin-1")
    return t


def _hex_to_rgb(h: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    hs = (h or "").strip()
    if hs.startswith("#"):
        hs = hs[1:]
    if len(hs) != 6:
        return fallback
    try:
        return (int(hs[0:2], 16), int(hs[2:4], 16), int(hs[4:6], 16))
    except Exception:
        return fallback


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


class BrandPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Letter landscape
        self.page_w = inch(11.0)
        self.page_h = inch(8.5)

        self.margin_l = inch(0.85)
        self.margin_r = inch(0.85)
        self.margin_t = inch(0.75)
        self.margin_b = inch(0.70)

        self.live_w = self.page_w - self.margin_l - self.margin_r
        self.live_h = self.page_h - self.margin_t - self.margin_b

        self.brand_name = ""
        self._latin_only = False
        self._suppress_footer = False

        # Palette
        self.c_bg = (255, 255, 255)
        self.c_text = (18, 22, 30)
        self.c_muted = (90, 96, 110)
        self.c_panel = (246, 247, 249)
        self.c_stroke = (225, 228, 234)
        self.c_accent = (28, 125, 255)

    def set_brand_fonts(self):
        # Use built-in fonts for maximum reliability
        # You can re-add your fontpack later once layout is stable
        self._latin_only = False

    def f_head(self, size: float, bold: bool = True):
        self.set_font("Helvetica", "B" if bold else "", size)

    def f_body(self, size: float, bold: bool = False):
        self.set_font("Helvetica", "B" if bold else "", size)

    def footer(self):
        if self._suppress_footer:
            return
        self.set_y(-self.margin_b + inch(0.22))
        self.f_body(8, False)
        self.set_text_color(*self.c_muted)
        self.set_x(self.margin_l)
        self.cell(0, inch(0.18), safe_text(self.brand_name, self._latin_only), align="L")
        self.set_x(self.page_w - self.margin_r - inch(0.35))
        self.cell(inch(0.35), inch(0.18), str(self.page_no()), align="R")

    def page_bg(self):
        self.set_fill_color(*self.c_bg)
        self.rect(0, 0, self.w, self.h, style="F")

    def title_bar(self, title: str, subtitle: Optional[str] = None):
        # top title area, consistent
        x = self.margin_l
        y = self.margin_t
        self.set_xy(x, y)
        self.set_text_color(*self.c_text)
        self.f_head(22, True)
        self.cell(0, inch(0.30), safe_text(title, self._latin_only), ln=1)
        if subtitle:
            self.set_x(x)
            self.set_text_color(*self.c_muted)
            self.f_body(11, False)
            self.multi_cell(self.live_w, inch(0.22), safe_text(subtitle, self._latin_only))
        self.ln(inch(0.08))
        # thin rule
        self.set_draw_color(*self.c_stroke)
        self.set_line_width(0.6)
        self.line(x, self.get_y(), x + self.live_w, self.get_y())
        self.ln(inch(0.18))

    def ensure_space(self, needed_h: float):
        if self.get_y() + needed_h > self.h - self.margin_b:
            self.add_page(orientation="L")
            self.page_bg()

    def panel(self, title: str, body: str, accent: bool = False):
        # a clean text block
        x = self.margin_l
        w = self.live_w
        pad = inch(0.18)

        title_h = inch(0.22)
        # estimate body height by splitting lines after write
        self.f_body(11, False)
        lines = self.multi_cell(w - pad * 2, inch(0.22), safe_text(body, self._latin_only), split_only=True)
        body_h = max(len(lines), 1) * inch(0.22)

        h = pad + title_h + inch(0.10) + body_h + pad
        self.ensure_space(h)

        y = self.get_y()
        self.set_fill_color(*self.c_panel)
        self.rect(x, y, w, h, style="F")
        self.set_draw_color(*self.c_stroke)
        self.rect(x, y, w, h)

        if accent:
            self.set_draw_color(*self.c_accent)
            self.set_line_width(2.0)
            self.line(x, y, x, y + h)
            self.set_line_width(0.6)

        self.set_xy(x + pad, y + pad)
        self.set_text_color(*self.c_text)
        self.f_body(11, True)
        self.cell(w - pad * 2, title_h, safe_text(title, self._latin_only), ln=1)
        self.ln(inch(0.02))

        self.set_text_color(*self.c_text)
        self.f_body(11, False)
        self.multi_cell(w - pad * 2, inch(0.22), safe_text(body, self._latin_only))

        self.set_y(y + h + inch(0.14))

    def rules_block(self, heading: str, rules: list[str], start_index: int = 1):
        x = self.margin_l
        w = self.live_w

        self.ensure_space(inch(0.40))
        self.set_text_color(*self.c_text)
        self.f_body(12, True)
        self.cell(0, inch(0.24), safe_text(heading, self._latin_only), ln=1)
        self.ln(inch(0.06))

        idx = start_index
        for r in rules:
            rr = (r or "").strip()
            if not rr:
                continue
            # Rule panel
            pad = inch(0.16)
            num_w = inch(0.34)

            self.f_body(11, False)
            lines = self.multi_cell(w - pad * 2 - num_w, inch(0.22), safe_text(rr, self._latin_only), split_only=True)
            body_h = max(len(lines), 1) * inch(0.22)
            h = pad + body_h + pad

            self.ensure_space(h + inch(0.08))
            y = self.get_y()

            self.set_fill_color(*self.c_panel)
            self.rect(x, y, w, h, style="F")
            self.set_draw_color(*self.c_stroke)
            self.rect(x, y, w, h)

            # Number
            self.set_xy(x + pad, y + pad - inch(0.02))
            self.set_text_color(*self.c_accent)
            self.f_body(11, True)
            self.cell(num_w, inch(0.22), str(idx), align="L")

            # Text
            self.set_xy(x + pad + num_w, y + pad)
            self.set_text_color(*self.c_text)
            self.f_body(11, False)
            self.multi_cell(w - pad * 2 - num_w, inch(0.22), safe_text(rr, self._latin_only))

            self.set_y(y + h + inch(0.10))
            idx += 1

        self.ln(inch(0.08))

    def two_col_panels(self, left_title: str, left_body: str, right_title: str, right_body: str):
        # two equal panels, stable layout
        gap = inch(0.20)
        x = self.margin_l
        y = self.get_y()

        w = (self.live_w - gap) / 2
        pad = inch(0.16)

        # estimate heights
        self.f_body(11, False)
        l_lines = self.multi_cell(w - pad * 2, inch(0.22), safe_text(left_body, self._latin_only), split_only=True)
        r_lines = self.multi_cell(w - pad * 2, inch(0.22), safe_text(right_body, self._latin_only), split_only=True)
        title_h = inch(0.22)

        l_h = pad + title_h + inch(0.08) + max(len(l_lines), 1) * inch(0.22) + pad
        r_h = pad + title_h + inch(0.08) + max(len(r_lines), 1) * inch(0.22) + pad
        h = max(l_h, r_h)

        self.ensure_space(h + inch(0.10))
        y = self.get_y()

        # left panel
        self.set_fill_color(*self.c_panel)
        self.rect(x, y, w, h, style="F")
        self.set_draw_color(*self.c_stroke)
        self.rect(x, y, w, h)
        self.set_xy(x + pad, y + pad)
        self.set_text_color(*self.c_text)
        self.f_body(11, True)
        self.cell(w - pad * 2, inch(0.22), safe_text(left_title, self._latin_only), ln=1)
        self.ln(inch(0.02))
        self.f_body(11, False)
        self.multi_cell(w - pad * 2, inch(0.22), safe_text(left_body, self._latin_only))

        # right panel
        rx = x + w + gap
        self.set_fill_color(*self.c_panel)
        self.rect(rx, y, w, h, style="F")
        self.set_draw_color(*self.c_stroke)
        self.rect(rx, y, w, h)
        self.set_xy(rx + pad, y + pad)
        self.set_text_color(*self.c_text)
        self.f_body(11, True)
        self.cell(w - pad * 2, inch(0.22), safe_text(right_title, self._latin_only), ln=1)
        self.ln(inch(0.02))
        self.f_body(11, False)
        self.multi_cell(w - pad * 2, inch(0.22), safe_text(right_body, self._latin_only))

        self.set_y(y + h + inch(0.18))


def render_pdf(schema: dict, include_images: bool, unsplash_key: str) -> bytes:
    meta = schema.get("meta", {}) or {}
    hero = schema.get("hero", {}) or {}
    brand = (meta.get("brand_name", "") or "").strip() or "Brand"

    pdf = BrandPDF(orientation="L", unit="mm", format="letter")
    pdf.set_auto_page_break(auto=True, margin=pdf.margin_b)
    pdf.set_brand_fonts()
    pdf.brand_name = brand

    # Optional cover photo, but default off
    cover_img = None
    temp_files: list[str] = []
    if include_images:
        if not unsplash_key:
            include_images = False
        elif requests is None:
            include_images = False
        else:
            cover_img = unsplash_one(unsplash_key, query="minimal architecture interior empty", orientation="landscape")
            if cover_img:
                temp_files.append(cover_img)

    # Cover
    pdf._suppress_footer = True
    pdf.add_page(orientation="L")
    pdf.page_bg()
    if include_images and cover_img:
        try:
            pdf.image(cover_img, x=0, y=0, w=pdf.w, h=pdf.h)
        except Exception:
            pass

    # subtle overlay to ensure readability, not black box
    pdf.set_fill_color(255, 255, 255)
    pdf.set_alpha(0.92) if hasattr(pdf, "set_alpha") else None
    pdf.rect(pdf.margin_l, inch(1.20), pdf.live_w, inch(3.10), style="F")
    if hasattr(pdf, "set_alpha"):
        pdf.set_alpha(1.0)

    pdf.set_xy(pdf.margin_l, inch(1.45))
    pdf.set_text_color(*pdf.c_text)
    pdf.f_head(40, True)
    pdf.multi_cell(pdf.live_w, inch(0.45), safe_text(brand, pdf._latin_only))

    sub = (hero.get("deck_subtitle", "") or "").strip() or "Messaging Rules"
    pdf.set_xy(pdf.margin_l, inch(3.55))
    pdf.set_text_color(*pdf.c_muted)
    pdf.f_body(14, False)
    pdf.multi_cell(pdf.live_w, inch(0.28), safe_text(sub, pdf._latin_only))
    pdf._suppress_footer = False

    # How to use
    pdf.add_page(orientation="L")
    pdf.page_bg()
    pdf.title_bar("How to use this", "An operational language ruleset for writing, approving, and policing messaging under time pressure.")
    pdf.panel(
        "Operating principle",
        "If copy conflicts with this document, the document wins. If you feel the urge to sound nicer, softer, or broader, stop and re-read the bans.",
        accent=True,
    )
    pdf.panel(
        "Scope",
        "Use this for marketing, product pages, sales, social posts, support, and internal briefs. Keep it open while writing. Use it to reject drafts fast.",
    )
    pdf.panel(
        "Regeneration trigger",
        "Regenerate only when the product meaning changes, the audience changes, or the market consistently misfiles you.",
    )

    # Executive summary
    ex = schema.get("executive_summary", {}) or {}
    decisions = [d for d in (ex.get("decisions", []) or []) if (d or "").strip()]
    pdf.add_page(orientation="L")
    pdf.page_bg()
    pdf.title_bar("Executive summary", "The decisions that keep messaging consistent.")
    pdf.rules_block("Decisions", decisions[:10], start_index=1)

    # Messaging rules
    mr = schema.get("messaging_rules", {}) or {}
    pdf.add_page(orientation="L")
    pdf.page_bg()
    pdf.title_bar("Messaging rules", "What language is allowed, what is forbidden, and what proof is required.")

    pdf.panel("What we sell", (mr.get("what_we_sell", "") or "").strip(), accent=True)

    doctrine = [x for x in (mr.get("doctrine", []) or []) if (x or "").strip()]
    allowed = [x for x in (mr.get("allowed_framing_patterns", []) or []) if (x or "").strip()]
    forbidden = [x for x in (mr.get("forbidden_framing_patterns", []) or []) if (x or "").strip()]
    non_neg = [x for x in (mr.get("non_negotiables", []) or []) if (x or "").strip()]

    if doctrine:
        pdf.rules_block("Doctrine", doctrine[:10], start_index=1)

    if allowed or forbidden:
        left_body = "\n".join([f"{i+1}. {s}" for i, s in enumerate(allowed[:6])]) if allowed else "None defined."
        right_body = "\n".join([f"{i+1}. {s}" for i, s in enumerate(forbidden[:6])]) if forbidden else "None defined."
        pdf.two_col_panels("Allowed framing patterns", left_body, "Forbidden framing patterns", right_body)

    banned_words = [x for x in (mr.get("banned_words", []) or []) if (x or "").strip()]
    proof = (mr.get("proof_standard", "") or "").strip()

    if banned_words or proof:
        left_body = ", ".join(banned_words[:18]) if banned_words else "None defined."
        right_body = proof if proof else "Define what evidence you respect and what does not count."
        pdf.two_col_panels("Banned words", left_body, "Proof standard", right_body)

    if non_neg:
        pdf.rules_block("Non negotiables", non_neg[:10], start_index=1)

    # Voice rules
    vr = schema.get("voice_rules", {}) or {}
    pdf.add_page(orientation="L")
    pdf.page_bg()
    pdf.title_bar("Voice rules", "Behavioral constraints that prevent drift.")

    must = [x for x in (vr.get("must_sound_like", []) or []) if (x or "").strip()]
    must_not = [x for x in (vr.get("must_not_sound_like", []) or []) if (x or "").strip()]
    rules = [x for x in (vr.get("rules", []) or []) if (x or "").strip()]

    if must or must_not:
        left_body = "\n".join([f"{i+1}. {s}" for i, s in enumerate(must[:6])]) if must else "None defined."
        right_body = "\n".join([f"{i+1}. {s}" for i, s in enumerate(must_not[:6])]) if must_not else "None defined."
        pdf.two_col_panels("Must sound like", left_body, "Must not sound like", right_body)

    if rules:
        pdf.rules_block("Rules", rules[:12], start_index=1)

    # Examples
    exa = schema.get("examples", {}) or {}
    pdf.add_page(orientation="L")
    pdf.page_bg()
    pdf.title_bar("Examples", "Ready patterns and rewrites that demonstrate the rules.")

    sales = (exa.get("sales_sentence", "") or "").strip()
    if sales:
        pdf.panel("Sales sentence", sales, accent=True)

    headlines = [x for x in (exa.get("headlines", []) or []) if (x or "").strip()]
    posts = [x for x in (exa.get("social_posts", []) or []) if (x or "").strip()]
    if headlines or posts:
        left_body = "\n".join([f"{i+1}. {s}" for i, s in enumerate(headlines[:6])]) if headlines else "None defined."
        right_body = "\n".join([f"{i+1}. {s}" for i, s in enumerate(posts[:4])]) if posts else "None defined."
        pdf.two_col_panels("Headlines", left_body, "Social posts", right_body)

    ba = exa.get("before_after", []) or []
    cleaned_ba = []
    for item in ba[:6]:
        rule = (item.get("rule", "") or "").strip()
        before = (item.get("before", "") or "").strip()
        after = (item.get("after", "") or "").strip()
        if rule and before and after:
            cleaned_ba.append((rule, before, after))

    if cleaned_ba:
        pdf.ensure_space(inch(0.50))
        pdf.set_text_color(*pdf.c_text)
        pdf.f_body(12, True)
        pdf.cell(0, inch(0.26), safe_text("Before and after", pdf._latin_only), ln=1)
        pdf.ln(inch(0.10))

        idx = 1
        for rule, before, after in cleaned_ba:
            pdf.panel(f"Rewrite {idx}: {rule}", f"Before:\n{before}\n\nAfter:\n{after}", accent=(idx == 1))
            idx += 1

    # Guardrails
    gr = schema.get("guardrails", {}) or {}
    pdf.add_page(orientation="L")
    pdf.page_bg()
    pdf.title_bar("Guardrails", "How this gets ruined. What to reject quickly.")

    fm = [x for x in (gr.get("failure_modes", []) or []) if (x or "").strip()]
    rf = [x for x in (gr.get("red_flags", []) or []) if (x or "").strip()]
    acl = [x for x in (gr.get("approval_checklist", []) or []) if (x or "").strip()]

    if fm:
        pdf.rules_block("Failure modes", fm[:10], start_index=1)
    if rf:
        pdf.rules_block("Red flags in copy", rf[:10], start_index=1)
    if acl:
        pdf.rules_block("Approval checklist", acl[:12], start_index=1)

    # Appendix
    ap = schema.get("appendix", {}) or {}
    pdf.add_page(orientation="L")
    pdf.page_bg()
    pdf.title_bar("Appendix", "Optional suggestions for color and typography.")

    colors = ap.get("color_suggestions", []) or []
    if colors:
        parts = []
        for c in colors[:4]:
            name = (c.get("name", "") or "").strip()
            hx = (c.get("hex", "") or "").strip()
            reason = (c.get("reason", "") or "").strip()
            if name and hx and reason:
                parts.append(f"{name} {_rgb_to_hex(_hex_to_rgb(hx, (0,0,0)))}\n{reason}")
        if parts:
            pdf.panel("Color suggestions", "\n\n".join(parts))

    typo = ap.get("typography_suggestions", {}) or {}
    p = (typo.get("primary", "") or "").strip()
    s = (typo.get("secondary", "") or "").strip()
    r = (typo.get("rationale", "") or "").strip()
    if p or s or r:
        pdf.panel("Typography suggestions", f"Primary: {p or 'Not specified'}\nSecondary: {s or 'Not specified'}\n\n{r or ''}".strip())

    out = pdf.output(dest="S")
    pdf_bytes = bytes(out) if isinstance(out, (bytes, bytearray)) else str(out).encode("latin-1", "replace")

    # Cleanup temp images
    for pth in temp_files:
        try:
            os.unlink(pth)
        except Exception:
            pass

    return pdf_bytes


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


def validate_step(step: dict) -> tuple[bool, str]:
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


# =========================================================
# Views
# =========================================================
def landing_view():
    st.markdown('<div class="eyebrow">Operational language</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle">Messaging Rules</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="heroSub">A focused interview that turns intent into enforceable language rules. Not a brand book. A system for writing and approving copy under pressure.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2], gap="large")
    with col1:
        st.subheader("What this creates")
        st.write("A ruleset that prevents drift, stops vague language, and makes copy review fast.")
        st.write("It derives constraints, framing patterns, and rewrite examples from your input.")
        st.write("It is designed to be used, not admired.")
    with col2:
        st.subheader("Delivery")
        st.write("Clean PDF ruleset")
        st.write("Derived examples and rewrite patterns")
        st.write("Guardrails and approval checklist")
        st.caption("5 generations per purchase concept.")

    with st.expander("Advanced settings", expanded=False):
        st.session_state.provider = st.selectbox("Provider", options=["gemini", "openai"], index=0 if st.session_state.provider == "gemini" else 1)
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.gemini_key = st.text_input("Gemini API key", type="password", value=st.session_state.gemini_key)
        with c2:
            st.session_state.openai_key = st.text_input("OpenAI API key", type="password", value=st.session_state.openai_key)
        st.session_state.openai_model = st.text_input("OpenAI model", value=st.session_state.openai_model)

        st.session_state.include_images = st.checkbox("Include images (off by default)", value=st.session_state.include_images)
        if st.session_state.include_images:
            st.session_state.unsplash_key = st.text_input("Unsplash access key", type="password", value=st.session_state.unsplash_key)
            st.caption("Images are optional. If Unsplash is missing, the PDF stays text only.")

    st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
    if st.button("Start interview"):
        st.session_state.step_index = 0
        go("wizard")
    st.markdown("</div>", unsafe_allow_html=True)


def wizard_view():
    all_steps = steps()
    st.session_state.step_index = max(0, min(st.session_state.step_index, len(all_steps) - 1))
    step = all_steps[st.session_state.step_index]

    render_progress(st.session_state.step_index, all_steps)
    st.write("")

    if step["type"] == "intro":
        st.subheader("How this works")
        st.caption("Answer 10 questions. The system produces derived rules, patterns, and examples. It will not copy your answers back to you.")
        st.write("")
        st.write("Write like you mean it. Sharp answers create sharp rules.")
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
    st.markdown('<div class="eyebrow">Confirmation</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Generate Messaging Rules</div>', unsafe_allow_html=True)

    remaining = max(st.session_state.gen_max - st.session_state.gen_used, 0)
    st.caption(f"Generations remaining: {remaining} of {st.session_state.gen_max}")

    with st.expander("Review your inputs", expanded=False):
        for q in QUESTIONS:
            ans = st.session_state.answers.get(q.key)
            if not ans:
                continue
            st.markdown(f"**{q.title}**")
            st.write(ans)
            st.markdown("")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back to interview"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        if st.button("Generate PDF", disabled=(remaining <= 0)):
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)


def generate_view():
    st.markdown('<div class="eyebrow">Generating</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Building your ruleset</div>', unsafe_allow_html=True)
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
            stage.write("Deriving rules")
            time.sleep(0.05)

            if st.session_state.provider == "openai":
                if not (st.session_state.openai_key or "").strip():
                    raise RuntimeError("Missing OpenAI API key.")
                schema, model_used = generate_with_openai(
                    prompt,
                    api_key=(st.session_state.openai_key or "").strip(),
                    model=(st.session_state.openai_model or "gpt-4.1-mini").strip(),
                )
            else:
                if not (st.session_state.gemini_key or "").strip():
                    raise RuntimeError("Missing Gemini API key.")
                schema, model_used = generate_with_gemini(
                    prompt,
                    api_key=(st.session_state.gemini_key or "").strip(),
                    timeout_s=35,
                )

            stage.write("Rendering PDF")
            time.sleep(0.05)

            pdf_bytes = render_pdf(
                schema,
                include_images=bool(st.session_state.include_images),
                unsplash_key=(st.session_state.unsplash_key or "").strip(),
            )

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
    st.markdown('<div class="eyebrow">Ready</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Download your ruleset</div>', unsafe_allow_html=True)

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

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Start new"):
            reset_app(keep_keys=True)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Generate again", disabled=(remaining <= 0)):
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Preview JSON", expanded=False):
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
