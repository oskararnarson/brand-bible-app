import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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
        "provider": "openai",  # openai or gemini
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
# CSS (cleaner UI, less "template")
# =========================================================
def inject_css():
    st.markdown(
        """
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

.block-container { max-width: 1040px; padding-top: 5.0rem !important; padding-bottom: 3.0rem; }

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
    radial-gradient(1100px 700px at 20% 30%, rgba(0,120,255,0.16), rgba(0,0,0,0) 60%),
    radial-gradient(900px 600px at 80% 20%, rgba(255,255,255,0.06), rgba(0,0,0,0) 55%),
    #0b0d11;
}

.eyebrow{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted2);
  margin-bottom: 12px;
}

.heroTitle{
  font-size: 56px;
  line-height: 1.02;
  font-weight: 950;
  margin: 0 0 12px 0;
}

.heroSub{
  font-size: 16px;
  line-height: 1.8;
  color: var(--muted);
  margin-bottom: 16px;
  max-width: 860px;
}

hr.soft{
  border:none;
  height:1px;
  background: rgba(255,255,255,0.08);
  margin: 18px 0;
}

.card{
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 18px;
  padding: 16px 16px;
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
# Intake (10 questions)
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
    Question("q5", "Who this is absolutely for", "Describe one recognizable person, not a segment.", "textarea", "core_customer",
             placeholder="They are the kind of person who ___. They are frustrated by ___."),
    Question("q6", "What this is not", "The anti model. What you refuse to resemble.", "textarea", "anti_model",
             placeholder="We refuse to feel like ___."),
    Question("q7", "What language is banned", "Words, tones, or implications that corrupt the brand.", "textarea", "banned_language",
             placeholder="Never say or imply ___. Never sound like ___."),
    Question("q8", "What proof is required before claims are trusted", "Your evidence standard.", "textarea", "proof_standard",
             placeholder="We earn trust through ___."),
    Question("q9", "One sentence sales is allowed to use", "If this fails, everything fails.", "textarea", "sales_sentence",
             placeholder="If you are ___ and want ___, this exists for you."),
    Question("q10", "Failure mode if done wrong", "The hollow version that looks like a costume.", "textarea", "failure_mode",
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
# Provider and prompt
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
        "You are a senior strategist writing an operational messaging ruleset.\n"
        "Write constraints, tests, and patterns.\n"
        "Do not echo user answers verbatim.\n"
        "Be decisive and specific.\n"
        "No hype. No cliches. No buzzwords.\n"
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


def generate_with_openai(prompt: str, api_key: str, model: str) -> tuple[dict, str]:
    if OpenAI is None:
        raise RuntimeError("openai package not installed.")
    client = OpenAI(api_key=api_key)

    resp = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.25,
        max_output_tokens=2400,
    )
    raw = (getattr(resp, "output_text", "") or "").strip()
    data = json.loads(extract_json_object(raw))
    required = ["meta", "hero", "executive_summary", "messaging_rules", "voice_rules", "examples", "guardrails", "appendix"]
    for k in required:
        if k not in data:
            raise ValueError("JSON missing required keys.")
    return data, model


def _gemini_list_generate_models() -> list[str]:
    if genai is None:
        return []
    out = []
    try:
        for m in genai.list_models():
            name = getattr(m, "name", "") or ""
            methods = getattr(m, "supported_generation_methods", []) or []
            if name and "generateContent" in methods:
                out.append(name)
    except Exception:
        return []
    return out


def generate_with_gemini(prompt: str, api_key: str, timeout_s: int = 35) -> tuple[dict, str]:
    if genai is None:
        raise RuntimeError("google-generativeai not installed.")
    genai.configure(api_key=api_key)

    models = _gemini_list_generate_models()
    if not models:
        raise RuntimeError("No Gemini models available for generateContent.")

    preferred = []
    for p in ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]:
        for m in models:
            if p in m and m not in preferred:
                preferred.append(m)
    for m in models:
        if m not in preferred:
            preferred.append(m)

    last_err = None
    for model_name in preferred:
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


# =========================================================
# Optional images (off by default)
# =========================================================
UNSPLASH_API = "https://api.unsplash.com"


def _unsplash_headers(access_key: str) -> dict:
    return {
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1",
        "User-Agent": "MessagingRulesGenerator/2.0",
    }


def _download_image_to_temp(url: str) -> Optional[str]:
    if requests is None:
        return None
    try:
        r = requests.get(url, timeout=18, headers={"User-Agent": "MessagingRulesGenerator/2.0"}, allow_redirects=True)
        if r.status_code != 200 or not r.content:
            return None
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        f.write(r.content)
        f.flush()
        f.close()
        if os.path.getsize(f.name) < 60_000:
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
# PDF rendering (phenomenal deck, no bullets, no overlaps)
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


class Grid:
    def __init__(self, page_w: float, margin_l: float, margin_r: float, cols: int = 12, gutter: float = inch(0.16)):
        self.page_w = page_w
        self.margin_l = margin_l
        self.margin_r = margin_r
        self.cols = cols
        self.gutter = gutter
        self.live_w = self.page_w - self.margin_l - self.margin_r
        self.col_w = (self.live_w - (self.cols - 1) * self.gutter) / self.cols

    def x(self, col: int) -> float:
        return self.margin_l + col * (self.col_w + self.gutter)

    def w(self, span: int) -> float:
        if span <= 0:
            return 0.0
        return span * self.col_w + (span - 1) * self.gutter


class DeckPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.page_w = inch(11.0)
        self.page_h = inch(8.5)

        self.margin_l = inch(0.78)
        self.margin_r = inch(0.78)
        self.margin_t = inch(0.70)
        self.margin_b = inch(0.62)

        self.grid = Grid(self.page_w, self.margin_l, self.margin_r, cols=12, gutter=inch(0.16))

        self.brand_name = ""
        self._latin_only = False
        self._suppress_footer = False

        # Minimal luxury palette
        self.c_bg = (255, 255, 255)
        self.c_ink = (16, 18, 24)
        self.c_muted = (92, 98, 112)
        self.c_hair = (224, 228, 235)
        self.c_panel = (246, 247, 249)
        self.c_accent = (28, 125, 255)

    def set_brand_fonts(self):
        # Reliable built in fonts. Add custom fonts only after layout is stable.
        self._latin_only = False

    def f_h(self, size: float, bold: bool = True):
        self.set_font("Helvetica", "B" if bold else "", size)

    def f_b(self, size: float, bold: bool = False):
        self.set_font("Helvetica", "B" if bold else "", size)

    def footer(self):
        if self._suppress_footer:
            return
        self.set_y(-self.margin_b + inch(0.18))
        self.set_text_color(*self.c_muted)
        self.f_b(8, False)
        self.set_x(self.margin_l)
        self.cell(0, inch(0.16), safe_text(self.brand_name, self._latin_only), align="L")
        self.set_x(self.page_w - self.margin_r - inch(0.35))
        self.cell(inch(0.35), inch(0.16), str(self.page_no()), align="R")

    def page_bg(self):
        self.set_fill_color(*self.c_bg)
        self.rect(0, 0, self.w, self.h, style="F")

    def new_page(self):
        self.add_page(orientation="L")
        self.page_bg()

    def y_max(self) -> float:
        return self.h - self.margin_b

    def ensure_space(self, h_needed: float):
        if self.get_y() + h_needed > self.y_max():
            self.new_page()

    def hairline(self, x: float, y: float, w: float):
        self.set_draw_color(*self.c_hair)
        self.set_line_width(0.5)
        self.line(x, y, x + w, y)

    def measure_lines(self, w: float, text: str, line_h: float) -> int:
        txt = safe_text(text, self._latin_only)
        if not txt.strip():
            return 1
        try:
            lines = self.multi_cell(w, line_h, txt, split_only=True)
            return max(len(lines), 1)
        except Exception:
            # fallback approximation
            approx_chars = int(max(w, 1) * 2.1)
            return max(1, (len(txt) // max(approx_chars, 40)) + 1)

    def cover(self, brand: str, subtitle: str, meta_line: str, cover_img: Optional[str] = None):
        self._suppress_footer = True
        self.new_page()

        if cover_img:
            try:
                self.image(cover_img, x=0, y=0, w=self.w, h=self.h)
            except Exception:
                pass

        # left text column with strong whitespace, no box
        x = self.grid.x(0)
        w = self.grid.w(7)
        y = self.margin_t + inch(0.25)

        # subtle accent bar
        self.set_fill_color(*self.c_accent)
        self.rect(x, y + inch(0.05), inch(0.06), inch(2.55), style="F")

        self.set_xy(x + inch(0.20), y)
        self.set_text_color(*self.c_ink)
        self.f_h(54, True)
        self.multi_cell(w, inch(0.55), safe_text(brand, self._latin_only))

        self.ln(inch(0.10))
        self.set_x(x + inch(0.20))
        self.set_text_color(*self.c_muted)
        self.f_b(14, False)
        self.multi_cell(w, inch(0.30), safe_text(subtitle, self._latin_only))

        self.set_y(self.h - self.margin_b - inch(0.55))
        self.set_x(x + inch(0.20))
        self.set_text_color(*self.c_muted)
        self.f_b(10, False)
        self.cell(0, inch(0.24), safe_text(meta_line, self._latin_only), ln=0)

        self._suppress_footer = False

    def section_opener(self, title: str, line: str):
        self.new_page()
        x = self.grid.x(0)
        w = self.grid.w(12)

        self.set_xy(x, self.margin_t + inch(0.85))
        self.set_text_color(*self.c_ink)
        self.f_h(40, True)
        self.multi_cell(w, inch(0.50), safe_text(title, self._latin_only))

        self.set_x(x)
        self.set_text_color(*self.c_muted)
        self.f_b(14, False)
        self.multi_cell(self.grid.w(8), inch(0.32), safe_text(line, self._latin_only))

        self.ln(inch(0.30))
        self.hairline(x, self.get_y(), self.grid.w(6))

    def top_header(self, kicker: str, title: str, sub: Optional[str] = None):
        x = self.grid.x(0)
        self.set_xy(x, self.margin_t)

        self.set_text_color(*self.c_muted)
        self.f_b(9, True)
        self.cell(0, inch(0.18), safe_text(kicker.upper(), self._latin_only), ln=1)

        self.set_text_color(*self.c_ink)
        self.f_h(24, True)
        self.cell(0, inch(0.32), safe_text(title, self._latin_only), ln=1)

        if sub:
            self.set_text_color(*self.c_muted)
            self.f_b(11, False)
            self.multi_cell(self.grid.w(9), inch(0.24), safe_text(sub, self._latin_only))

        self.ln(inch(0.08))
        self.hairline(x, self.get_y(), self.grid.w(12))
        self.ln(inch(0.18))

    def panel(self, title: str, body: str, span: int = 12, accent: bool = False):
        x = self.grid.x(0)
        w = self.grid.w(span)
        pad = inch(0.18)
        line_h = inch(0.22)

        title_h = inch(0.22)
        body_lines = self.measure_lines(w - pad * 2, body, line_h)
        h = pad + title_h + inch(0.08) + body_lines * line_h + pad

        self.ensure_space(h)
        y = self.get_y()

        self.set_fill_color(*self.c_panel)
        self.rect(x, y, w, h, style="F")
        self.set_draw_color(*self.c_hair)
        self.set_line_width(0.6)
        self.rect(x, y, w, h)

        if accent:
            self.set_fill_color(*self.c_accent)
            self.rect(x, y, inch(0.06), h, style="F")

        self.set_xy(x + pad, y + pad)
        self.set_text_color(*self.c_ink)
        self.f_b(11, True)
        self.cell(w - pad * 2, title_h, safe_text(title, self._latin_only), ln=1)

        self.set_text_color(*self.c_ink)
        self.f_b(11, False)
        self.multi_cell(w - pad * 2, line_h, safe_text(body, self._latin_only))

        self.set_y(y + h + inch(0.16))

    def rule_cards(self, title: str, rules: list[str], columns: int = 2, max_rules: int = 10, start_index: int = 1):
        x0 = self.grid.x(0)
        self.set_text_color(*self.c_ink)
        self.f_b(12, True)
        self.cell(0, inch(0.26), safe_text(title, self._latin_only), ln=1)
        self.ln(inch(0.06))

        rules_clean = [r.strip() for r in (rules or []) if (r or "").strip()][:max_rules]
        if not rules_clean:
            self.set_text_color(*self.c_muted)
            self.f_b(11, False)
            self.multi_cell(self.grid.w(10), inch(0.24), "No rules provided.")
            self.ln(inch(0.10))
            return

        gap = inch(0.16)
        col_w = (self.grid.w(12) - gap * (columns - 1)) / columns
        pad = inch(0.14)
        line_h = inch(0.22)

        # Fixed card height rhythm
        # Measure each card height and flow across columns with safe paging
        col_y = [self.get_y()] * columns
        base_y = self.get_y()

        for i, text in enumerate(rules_clean, start=start_index):
            c = (i - start_index) % columns
            x = x0 + c * (col_w + gap)

            # measure
            num_w = inch(0.32)
            lines = self.measure_lines(col_w - pad * 2 - num_w, text, line_h)
            h = pad + max(lines, 1) * line_h + pad

            # if card would overflow page, start new page and reset columns
            if max(col_y) + h > self.y_max():
                self.new_page()
                self.top_header("Messaging Rules", "Rules", "Constraints that keep language consistent.")
                x0 = self.grid.x(0)
                col_y = [self.get_y()] * columns
                base_y = self.get_y()

            y = col_y[c]

            # draw
            self.set_fill_color(*self.c_panel)
            self.rect(x, y, col_w, h, style="F")
            self.set_draw_color(*self.c_hair)
            self.set_line_width(0.6)
            self.rect(x, y, col_w, h)

            # accent for first card on page
            if i == start_index:
                self.set_fill_color(*self.c_accent)
                self.rect(x, y, inch(0.06), h, style="F")

            # number
            self.set_xy(x + pad, y + pad - inch(0.02))
            self.set_text_color(*self.c_accent)
            self.f_b(11, True)
            self.cell(num_w, line_h, str(i))

            # text
            self.set_xy(x + pad + num_w, y + pad)
            self.set_text_color(*self.c_ink)
            self.f_b(11, False)
            self.multi_cell(col_w - pad * 2 - num_w, line_h, safe_text(text, self._latin_only))

            col_y[c] = y + h + gap

        self.set_y(max(col_y) + inch(0.06))

    def two_column_lists(self, left_title: str, left_items: list[str], right_title: str, right_items: list[str], max_items: int = 8):
        gap = inch(0.18)
        x = self.grid.x(0)
        w = self.grid.w(12)
        col_w = (w - gap) / 2
        pad = inch(0.16)
        line_h = inch(0.22)

        left = [s.strip() for s in (left_items or []) if (s or "").strip()][:max_items]
        right = [s.strip() for s in (right_items or []) if (s or "").strip()][:max_items]

        def body_text(items: list[str]) -> str:
            if not items:
                return "None defined."
            return "\n".join([f"{i+1}. {t}" for i, t in enumerate(items)])

        l_body = body_text(left)
        r_body = body_text(right)

        l_lines = self.measure_lines(col_w - pad * 2, l_body, line_h)
        r_lines = self.measure_lines(col_w - pad * 2, r_body, line_h)
        title_h = inch(0.22)
        h = pad + title_h + inch(0.08) + max(l_lines, r_lines) * line_h + pad

        self.ensure_space(h)
        y = self.get_y()

        # left panel
        self.set_fill_color(*self.c_panel)
        self.rect(x, y, col_w, h, style="F")
        self.set_draw_color(*self.c_hair)
        self.rect(x, y, col_w, h)

        self.set_xy(x + pad, y + pad)
        self.set_text_color(*self.c_ink)
        self.f_b(11, True)
        self.cell(col_w - pad * 2, title_h, safe_text(left_title, self._latin_only), ln=1)
        self.set_text_color(*self.c_ink)
        self.f_b(11, False)
        self.multi_cell(col_w - pad * 2, line_h, safe_text(l_body, self._latin_only))

        # right panel
        rx = x + col_w + gap
        self.set_fill_color(*self.c_panel)
        self.rect(rx, y, col_w, h, style="F")
        self.set_draw_color(*self.c_hair)
        self.rect(rx, y, col_w, h)

        self.set_xy(rx + pad, y + pad)
        self.set_text_color(*self.c_ink)
        self.f_b(11, True)
        self.cell(col_w - pad * 2, title_h, safe_text(right_title, self._latin_only), ln=1)
        self.set_text_color(*self.c_ink)
        self.f_b(11, False)
        self.multi_cell(col_w - pad * 2, line_h, safe_text(r_body, self._latin_only))

        self.set_y(y + h + inch(0.16))

    def before_after_cards(self, items: list[dict], max_items: int = 5):
        cleaned = []
        for it in (items or [])[:max_items]:
            rule = (it.get("rule", "") or "").strip()
            before = (it.get("before", "") or "").strip()
            after = (it.get("after", "") or "").strip()
            if rule and before and after:
                cleaned.append((rule, before, after))

        if not cleaned:
            return

        self.set_text_color(*self.c_ink)
        self.f_b(12, True)
        self.cell(0, inch(0.26), "Rewrites", ln=1)
        self.ln(inch(0.06))

        gap = inch(0.18)
        x = self.grid.x(0)
        w = self.grid.w(12)
        col_w = (w - gap) / 2
        pad = inch(0.16)
        line_h = inch(0.22)

        for idx, (rule, before, after) in enumerate(cleaned, start=1):
            title = f"{idx}. {rule}"

            left_body = "Before\n" + before
            right_body = "After\n" + after

            l_lines = self.measure_lines(col_w - pad * 2, left_body, line_h)
            r_lines = self.measure_lines(col_w - pad * 2, right_body, line_h)
            title_h = inch(0.22)
            h = pad + title_h + inch(0.10) + max(l_lines, r_lines) * line_h + pad

            self.ensure_space(h + inch(0.18))
            y = self.get_y()

            # title line
            self.set_text_color(*self.c_muted)
            self.f_b(9, True)
            self.cell(0, inch(0.18), safe_text(title.upper(), self._latin_only), ln=1)
            self.ln(inch(0.06))
            y = self.get_y()

            # left
            self.set_fill_color(*self.c_panel)
            self.rect(x, y, col_w, h, style="F")
            self.set_draw_color(*self.c_hair)
            self.rect(x, y, col_w, h)

            self.set_xy(x + pad, y + pad)
            self.set_text_color(*self.c_ink)
            self.f_b(11, False)
            self.multi_cell(col_w - pad * 2, line_h, safe_text(left_body, self._latin_only))

            # right with accent bar
            rx = x + col_w + gap
            self.set_fill_color(*self.c_panel)
            self.rect(rx, y, col_w, h, style="F")
            self.set_draw_color(*self.c_hair)
            self.rect(rx, y, col_w, h)
            self.set_fill_color(*self.c_accent)
            self.rect(rx, y, inch(0.06), h, style="F")

            self.set_xy(rx + pad, y + pad)
            self.set_text_color(*self.c_ink)
            self.f_b(11, False)
            self.multi_cell(col_w - pad * 2, line_h, safe_text(right_body, self._latin_only))

            self.set_y(y + h + inch(0.16))

    def checklist(self, title: str, items: list[str], columns: int = 2, max_items: int = 12):
        items_clean = [s.strip() for s in (items or []) if (s or "").strip()][:max_items]
        if not items_clean:
            return

        self.set_text_color(*self.c_ink)
        self.f_b(12, True)
        self.cell(0, inch(0.26), safe_text(title, self._latin_only), ln=1)
        self.ln(inch(0.06))

        gap = inch(0.16)
        x0 = self.grid.x(0)
        w = self.grid.w(12)
        col_w = (w - gap * (columns - 1)) / columns
        line_h = inch(0.22)
        pad_y = inch(0.06)

        # estimate block height
        rows = (len(items_clean) + columns - 1) // columns
        h_needed = rows * (line_h + pad_y) + inch(0.10)
        self.ensure_space(h_needed)

        base_y = self.get_y()
        for i, text in enumerate(items_clean):
            c = i % columns
            r = i // columns
            x = x0 + c * (col_w + gap)
            y = base_y + r * (line_h + pad_y)

            # checkbox
            box = inch(0.12)
            self.set_draw_color(*self.c_hair)
            self.rect(x, y + inch(0.04), box, box)
            self.set_xy(x + inch(0.18), y)
            self.set_text_color(*self.c_ink)
            self.f_b(11, False)
            self.multi_cell(col_w - inch(0.18), line_h, safe_text(text, self._latin_only))

        self.set_y(base_y + h_needed + inch(0.10))


def render_pdf(schema: dict, include_images: bool, unsplash_key: str) -> bytes:
    meta = schema.get("meta", {}) or {}
    hero = schema.get("hero", {}) or {}
    brand = (meta.get("brand_name", "") or "").strip() or "Brand"
    version = (meta.get("version", "") or "").strip() or "1"
    date_utc = (meta.get("date_utc", "") or "").strip() or utc_date_str()

    pdf = DeckPDF(orientation="L", unit="mm", format="letter")
    pdf.set_auto_page_break(auto=False, margin=pdf.margin_b)
    pdf.set_brand_fonts()
    pdf.brand_name = brand

    cover_img = None
    temp_files: list[str] = []
    if include_images and unsplash_key and requests is not None:
        cover_img = unsplash_one(unsplash_key, query="minimal architecture interior empty", orientation="landscape")
        if cover_img:
            temp_files.append(cover_img)

    deck_sub = (hero.get("deck_subtitle", "") or "").strip() or "Messaging Rules"
    meta_line = f"Version {version}   {date_utc}"
    pdf.cover(brand=brand, subtitle=deck_sub, meta_line=meta_line, cover_img=cover_img)

    # How to use (opener spread)
    pdf.section_opener("How to use this", "This is a decision system. It exists to speed up writing and approvals under pressure.")
    pdf.new_page()
    pdf.top_header("Messaging Rules", "Operating mode", "Use these rules to write, approve, and reject copy quickly.")
    pdf.panel(
        "Rule of precedence",
        "If copy conflicts with this document, the document wins. If you feel the urge to broaden, soften, or sound nicer, stop and re write until it passes the bans.",
        span=10,
        accent=True,
    )
    pdf.two_column_lists(
        "Use this for",
        [
            "Landing pages and product pages",
            "Sales pages and outreach",
            "Short form social posts",
            "Support templates",
            "Internal briefs and creative direction",
        ],
        "Do not use this for",
        [
            "Therapy language or comfort talk",
            "Category politics and jargon",
            "Vague inspiration content",
            "Identity statements that cannot be tested",
        ],
        max_items=6,
    )
    pdf.panel(
        "Regenerate trigger",
        "Regenerate only if the product meaning changes, the audience changes, or the market consistently misfiles you.",
        span=10,
        accent=False,
    )

    # Executive summary
    decisions = [d for d in ((schema.get("executive_summary", {}) or {}).get("decisions", []) or []) if (d or "").strip()]
    pdf.section_opener("Executive summary", "The decisions that keep messaging consistent when you are not in the room.")
    pdf.new_page()
    pdf.top_header("Messaging Rules", "Executive summary", "Decisions. Not descriptions.")
    pdf.rule_cards("Decisions", decisions, columns=2, max_rules=10, start_index=1)

    # Messaging rules
    mr = schema.get("messaging_rules", {}) or {}
    pdf.section_opener("Messaging rules", "Language constraints, framing patterns, bans, and proof standards.")
    pdf.new_page()
    pdf.top_header("Messaging Rules", "North star", "The smallest set of truths that everything else must obey.")
    pdf.panel("What we sell", (mr.get("what_we_sell", "") or "").strip(), span=12, accent=True)

    doctrine = [x for x in (mr.get("doctrine", []) or []) if (x or "").strip()]
    non_neg = [x for x in (mr.get("non_negotiables", []) or []) if (x or "").strip()]
    allowed = [x for x in (mr.get("allowed_framing_patterns", []) or []) if (x or "").strip()]
    forbidden = [x for x in (mr.get("forbidden_framing_patterns", []) or []) if (x or "").strip()]
    banned_words = [x for x in (mr.get("banned_words", []) or []) if (x or "").strip()]
    proof = (mr.get("proof_standard", "") or "").strip()

    if doctrine:
        pdf.rule_cards("Doctrine", doctrine, columns=2, max_rules=8, start_index=1)

    pdf.two_column_lists("Allowed framing", allowed, "Forbidden framing", forbidden, max_items=8)

    if banned_words or proof:
        left = [", ".join(banned_words[:24])] if banned_words else ["None defined."]
        right = [proof] if proof else ["Define what counts as evidence and what does not."]
        pdf.two_column_lists("Banned words", left, "Proof standard", right, max_items=1)

    if non_neg:
        pdf.rule_cards("Non negotiables", non_neg, columns=2, max_rules=10, start_index=1)

    # Voice rules
    vr = schema.get("voice_rules", {}) or {}
    must = [x for x in (vr.get("must_sound_like", []) or []) if (x or "").strip()]
    must_not = [x for x in (vr.get("must_not_sound_like", []) or []) if (x or "").strip()]
    rules = [x for x in (vr.get("rules", []) or []) if (x or "").strip()]

    pdf.section_opener("Voice rules", "Behavioral constraints that prevent drift and keep writing consistent.")
    pdf.new_page()
    pdf.top_header("Messaging Rules", "Voice", "A voice is a constraint system. Not a vibe.")
    pdf.two_column_lists("Must sound like", must, "Must not sound like", must_not, max_items=8)
    if rules:
        pdf.rule_cards("Voice rules", rules, columns=2, max_rules=10, start_index=1)

    # Examples
    exa = schema.get("examples", {}) or {}
    sales = (exa.get("sales_sentence", "") or "").strip()
    headlines = [x for x in (exa.get("headlines", []) or []) if (x or "").strip()]
    posts = [x for x in (exa.get("social_posts", []) or []) if (x or "").strip()]
    before_after = exa.get("before_after", []) or []

    pdf.section_opener("Examples", "Patterns you can deploy immediately. Rewrites that prove the rules.")
    pdf.new_page()
    pdf.top_header("Messaging Rules", "Examples", "Use these as templates. Rewrite until it passes the bans.")
    if sales:
        pdf.panel("Sales sentence", sales, span=12, accent=True)
    pdf.two_column_lists("Headlines", headlines, "Social posts", posts, max_items=6)
    pdf.before_after_cards(before_after, max_items=5)

    # Guardrails
    gr = schema.get("guardrails", {}) or {}
    fm = [x for x in (gr.get("failure_modes", []) or []) if (x or "").strip()]
    rf = [x for x in (gr.get("red_flags", []) or []) if (x or "").strip()]
    acl = [x for x in (gr.get("approval_checklist", []) or []) if (x or "").strip()]

    pdf.section_opener("Guardrails", "How this gets ruined. What to reject quickly.")
    pdf.new_page()
    pdf.top_header("Messaging Rules", "Guardrails", "The fastest way to protect trust is to reject drift early.")
    if fm:
        pdf.rule_cards("Failure modes", fm, columns=2, max_rules=8, start_index=1)
    if rf:
        pdf.rule_cards("Red flags in copy", rf, columns=2, max_rules=10, start_index=1)
    if acl:
        pdf.checklist("Approval checklist", acl, columns=2, max_items=12)

    # Appendix
    ap = schema.get("appendix", {}) or {}
    colors = ap.get("color_suggestions", []) or []
    typo = ap.get("typography_suggestions", {}) or {}

    if colors or typo:
        pdf.section_opener("Appendix", "Optional suggestions. Keep them secondary to the rules.")
        pdf.new_page()
        pdf.top_header("Messaging Rules", "Appendix", "Suggestions, not identity.")

        # Colors as a clean panel grid (text only)
        if colors:
            lines = []
            for c in colors[:4]:
                name = (c.get("name", "") or "").strip()
                hx = (c.get("hex", "") or "").strip()
                reason = (c.get("reason", "") or "").strip()
                if not (name and hx):
                    continue
                hx_norm = _rgb_to_hex(_hex_to_rgb(hx, (0, 0, 0)))
                if reason:
                    lines.append(f"{name}  {hx_norm}\n{reason}")
                else:
                    lines.append(f"{name}  {hx_norm}")
            if lines:
                pdf.panel("Color suggestions", "\n\n".join(lines), span=10, accent=False)

        # Typography
        p = (typo.get("primary", "") or "").strip()
        s = (typo.get("secondary", "") or "").strip()
        r = (typo.get("rationale", "") or "").strip()
        if p or s or r:
            body = f"Primary: {p or 'Not specified'}\nSecondary: {s or 'Not specified'}"
            if r:
                body = body + "\n\n" + r
            pdf.panel("Typography suggestions", body, span=10, accent=False)

    # Output bytes
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
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("What you get")
        st.write("A ruleset that prevents drift, stops vague language, and makes copy review fast.")
        st.write("Derived constraints, framing patterns, and rewrite examples.")
        st.write("Guardrails and an approval checklist.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Delivery")
        st.write("A designed PDF deck")
        st.write("Landscape pages")
        st.write("No filler visuals by default")
        st.caption("You can keep a 5 generations per purchase concept.")
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Advanced settings", expanded=False):
        st.session_state.provider = st.selectbox(
            "Provider",
            options=["openai", "gemini"],
            index=0 if st.session_state.provider == "openai" else 1,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.openai_key = st.text_input("OpenAI API key", type="password", value=st.session_state.openai_key)
            st.session_state.openai_model = st.text_input("OpenAI model", value=st.session_state.openai_model)
        with c2:
            st.session_state.gemini_key = st.text_input("Gemini API key", type="password", value=st.session_state.gemini_key)

        st.session_state.include_images = st.checkbox("Include cover image", value=st.session_state.include_images)
        if st.session_state.include_images:
            st.session_state.unsplash_key = st.text_input("Unsplash access key", type="password", value=st.session_state.unsplash_key)
            st.caption("Cover image is optional. If Unsplash is missing, PDF stays text only.")

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
        st.caption("Answer 10 questions. The system derives rules, patterns, and examples. It does not copy your answers back to you.")
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

            if st.session_state.provider == "gemini":
                if not (st.session_state.gemini_key or "").strip():
                    raise RuntimeError("Missing Gemini API key.")
                schema, model_used = generate_with_gemini(
                    prompt,
                    api_key=(st.session_state.gemini_key or "").strip(),
                    timeout_s=35,
                )
            else:
                if not (st.session_state.openai_key or "").strip():
                    raise RuntimeError("Missing OpenAI API key.")
                schema, model_used = generate_with_openai(
                    prompt,
                    api_key=(st.session_state.openai_key or "").strip(),
                    model=(st.session_state.openai_model or "gpt-4.1-mini").strip(),
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
