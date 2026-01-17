import json
import os
import re
import tempfile
import time
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

import streamlit as st
from fpdf import FPDF

try:
    import requests
except Exception:
    requests = None

try:
    import google.generativeai as genai
except Exception:
    genai = None

# OpenAI is optional. Only imported if provider is OpenAI.
# pip install openai


st.set_page_config(page_title="Messaging Rules Generator", layout="wide", page_icon="◼")


# =========================
# Session state
# =========================
def ss_init():
    defaults = {
        "view": "landing",
        "step_index": 0,
        "answers": {},
        "provider": "gemini",  # gemini or openai
        "gemini_key": "",
        "openai_key": "",
        "openai_model": "gpt-4.1-mini",
        "unsplash_key": "",
        "include_images": False,  # default OFF
        "gen_used": 0,
        "gen_max": 5,
        "last_json": None,
        "pdf_bytes": None,
        "model_used": "",
        "error": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # secrets
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
  max-width: 900px;
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


# =========================
# Intake (Messaging Rules, 10 questions)
# =========================
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
    Question("q1", "Brand name", "Short, memorable. The anchor for everything.", "text", "brand_name",
             placeholder="Example: MindOS"),
    Question("q2", "What do you actually sell", "Not the product. The outcome, leverage, or control people pay for.", "textarea", "sell",
             placeholder="We sell ___ so that ___ no longer has to ___."),
    Question("q3", "The belief you assert as fact", "Doctrine. The sentence you treat as true even when people disagree.", "textarea", "belief",
             placeholder="We believe ___ is true, even when it is uncomfortable."),
    Question("q4", "The misunderstood problem you fix", "The lazy assumption you reject.", "textarea", "misunderstood",
             placeholder="Most people think ___, but the real problem is ___."),
    Question("q5", "Who this is absolutely for", "Describe one recognisable person. Not a segment.", "textarea", "for_who",
             placeholder="They are the kind of person who ___ and is frustrated by ___."),
    Question("q6", "What this is not", "The anti model. What you refuse to resemble.", "textarea", "not_this",
             placeholder="We refuse to feel like ___."),
    Question("q7", "What language is banned", "Words, tones, and implications that instantly corrupt the brand.", "textarea", "banned_language",
             placeholder="We never say, imply, or sound like ___."),
    Question("q8", "What proof is required before claims are trusted", "The evidence standard you respect.", "textarea", "proof_standard",
             placeholder="We only earn trust through ___."),
    Question("q9", "One sentence sales is allowed to use", "If sales can only say one sentence, this is it.", "textarea", "sales_sentence",
             placeholder="If you are ___ and want ___, this exists for you."),
    Question("q10", "The failure mode if this is done wrong", "Name the cringe version. The thing your rules prevent.", "textarea", "failure_mode",
             placeholder="If we get this wrong, it becomes ___."),
]


def wizard_steps() -> list[dict]:
    steps: list[dict] = []
    for q in QUESTIONS:
        steps.append({"type": "question", "qid": q.id})
    return steps


def get_question(qid: str) -> Question:
    for q in QUESTIONS:
        if q.id == qid:
            return q
    raise KeyError(qid)


# =========================
# LLM providers
# =========================
class LLMProvider(Protocol):
    name: str

    def generate_json(self, prompt: str, timeout_s: int = 35) -> tuple[dict, str]:
        ...


PREFERRED_GEMINI_CONTAINS = [
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini",
]


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


def validate_required_keys(data: dict) -> None:
    required = [
        "meta",
        "hero",
        "executive_summary",
        "messaging_rules",
        "voice_rules",
        "examples",
        "guardrails",
        "usage",
        "appendix",
    ]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"JSON missing required keys: {missing}")


@dataclass
class GeminiProvider:
    api_key: str
    name: str = "gemini"

    def _list_generation_models(self) -> list[str]:
        if genai is None:
            return []
        out: list[str] = []
        try:
            for m in genai.list_models():
                mn = getattr(m, "name", "") or ""
                methods = getattr(m, "supported_generation_methods", None) or []
                if mn and "generateContent" in methods:
                    out.append(mn)
        except Exception:
            return []
        return out

    def _choose_models_to_try(self) -> list[str]:
        avail = self._list_generation_models()
        if not avail:
            return PREFERRED_GEMINI_CONTAINS[:]
        chosen: list[str] = []
        for p in PREFERRED_GEMINI_CONTAINS:
            for n in avail:
                if p in n and n not in chosen:
                    chosen.append(n)
        for n in avail:
            if n not in chosen:
                chosen.append(n)
        return chosen

    def generate_json(self, prompt: str, timeout_s: int = 35) -> tuple[dict, str]:
        if genai is None:
            raise RuntimeError("google.generativeai is not installed.")
        import concurrent.futures

        genai.configure(api_key=self.api_key)

        last_err: Exception | None = None
        for model_name in self._choose_models_to_try():
            try:
                model = genai.GenerativeModel(model_name)
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(model.generate_content, prompt)
                    resp = fut.result(timeout=timeout_s)
                raw = (getattr(resp, "text", "") or "").strip()
                data = json.loads(extract_json_object(raw))
                validate_required_keys(data)
                return data, model_name
            except concurrent.futures.TimeoutError:
                last_err = RuntimeError(f"Timeout after {timeout_s} seconds.")
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Gemini generation failed: {last_err}")


@dataclass
class OpenAIProvider:
    api_key: str
    model: str = "gpt-4.1-mini"
    name: str = "openai"

    def generate_json(self, prompt: str, timeout_s: int = 35) -> tuple[dict, str]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        # Lower temperature for schema compliance.
        resp = client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.2,
            max_output_tokens=2200,
        )
        raw = (resp.output_text or "").strip()
        data = json.loads(extract_json_object(raw))
        validate_required_keys(data)
        return data, self.model


def make_provider() -> LLMProvider:
    prov = (st.session_state.provider or "gemini").strip().lower()
    if prov == "openai":
        key = (st.session_state.openai_key or "").strip()
        if not key:
            raise ValueError("Missing OpenAI API key.")
        model = (st.session_state.openai_model or "gpt-4.1-mini").strip()
        return OpenAIProvider(api_key=key, model=model)

    key = (st.session_state.gemini_key or "").strip()
    if not key:
        raise ValueError("Missing Gemini API key.")
    return GeminiProvider(api_key=key)


# =========================
# Prompt (Messaging Rules)
# =========================
FONT_POOL = [
    "Inter", "Sora", "Manrope", "IBM Plex Sans", "Work Sans", "Public Sans", "Source Sans 3"
]


def build_prompt(answers: dict, version_str: str) -> str:
    brand = (answers.get("brand_name", "") or "").strip()
    date_utc = utc_date_str()
    answers_json = json.dumps(answers, ensure_ascii=False, indent=2)

    schema = (
        "{\n"
        '  "meta": { "brand_name": "", "version": "", "date_utc": "" },\n'
        '  "hero": { "title": "", "subtitle": "" },\n'
        '  "executive_summary": { "non_negotiables": [""] },\n'
        '  "messaging_rules": {\n'
        '    "what_we_sell": "",\n'
        '    "doctrine": [""],\n'
        '    "allowed_framing_patterns": [""],\n'
        '    "forbidden_framing_patterns": [""],\n'
        '    "banned_words": [""],\n'
        '    "proof_standard": [""]\n'
        "  },\n"
        '  "voice_rules": {\n'
        '    "must_sound_like": [""],\n'
        '    "must_not_sound_like": [""],\n'
        '    "rules": [""],\n'
        '    "do_say": [""],\n'
        '    "do_not_say": [""]\n'
        "  },\n"
        '  "examples": {\n'
        '    "sales_sentence": "",\n'
        '    "headlines": [""],\n'
        '    "social_posts": [""],\n'
        '    "before_after": [ { "before": "", "after": "", "rule": "" } ]\n'
        "  },\n"
        '  "guardrails": {\n'
        '    "failure_modes": [""],\n'
        '    "red_flags_in_copy": [""],\n'
        '    "approval_checklist": [""]\n'
        "  },\n"
        '  "usage": {\n'
        '    "how_to_use": [""],\n'
        '    "when_to_regenerate": [""],\n'
        '    "how_to_brief_writers": [""]\n'
        "  },\n"
        '  "appendix": {\n'
        '    "color_suggestions": [ { "name": "", "hex": "", "reason": "" } ],\n'
        '    "typography_suggestions": { "primary": "", "secondary": "", "rationale": "" }\n'
        "  }\n"
        "}\n"
    )

    # Important: enforce derived output, not echoes.
    prompt = (
        "You are a senior brand strategist.\n"
        "You create operational messaging rules, not a brand book.\n"
        "You decide. You do not describe.\n\n"
        "Hard constraints:\n"
        "1) Do not copy the user's phrasing verbatim unless it is a short keyword.\n"
        "2) Convert intent into enforceable rules, constraints, and tests.\n"
        "3) If an answer is vague, resolve it decisively. Do not hedge.\n"
        "4) Avoid cliches and startup hype. No therapy language.\n"
        "5) Return ONLY valid JSON matching the schema exactly.\n"
        "6) No markdown. No commentary. No extra keys.\n\n"
        "Typography suggestions:\n"
        "Pick from this pool when possible: " + ", ".join(FONT_POOL) + "\n\n"
        "Output requirements:\n"
        "- executive_summary.non_negotiables must be short, sharp, and enforceable.\n"
        "- messaging_rules.allowed_framing_patterns and forbidden_framing_patterns must be concrete patterns.\n"
        "- voice_rules.rules must be behavioral rules, not adjectives.\n"
        "- examples.before_after must include a rule label that explains the change.\n"
        "- guardrails.approval_checklist must be usable under time pressure.\n\n"
        "JSON SCHEMA:\n"
        f"{schema}\n"
        "INPUT:\n"
        f"Brand name: {brand}\n"
        f"Version: {version_str}\n"
        f"Date UTC: {date_utc}\n\n"
        "Intake answers JSON:\n"
        f"{answers_json}\n\n"
        "Return JSON only.\n"
    )
    return prompt


# =========================
# Optional Unsplash cover image (default off)
# =========================
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


def unsplash_cover_image(access_key: str, query: str) -> Optional[str]:
    if not access_key or requests is None:
        return None
    try:
        params = {
            "query": query,
            "orientation": "landscape",
            "content_filter": "high",
            "count": 1,
        }
        r = requests.get(
            f"{UNSPLASH_API}/photos/random",
            headers=_unsplash_headers(access_key),
            params=params,
            timeout=18,
        )
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


def cover_query_from_output(data: dict) -> str:
    # Keep this extremely constrained to avoid semantic contamination.
    # Abstract, architectural, instrument-like visuals only.
    brand = ((data.get("meta", {}) or {}).get("brand_name", "") or "").strip()
    return f"{brand} abstract minimal architecture no people"


# =========================
# PDF helpers and layout
# =========================
IN_TO_MM = 25.4


def inch(x: float) -> float:
    return x * IN_TO_MM


def safe_text(s: Any, latin_only: bool = False) -> str:
    if s is None:
        return ""
    t = str(s)
    # Replace typographic punctuation that can break fonts.
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2026", "...")
    t = t.replace("\u00A0", " ")
    # Never use en dash or em dash in output.
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    if latin_only:
        t = t.replace("\u2022", "*").replace("\u00B7", "*").replace("\u25CF", "*").replace("\u25AA", "*")
        t = t.encode("latin-1", "replace").decode("latin-1")
    return t


def safe_multicell(pdf: FPDF, w: float, h: float, txt: str):
    if w is None or w <= 6:
        raise RuntimeError(f"Invalid text width: {w}")
    pdf.multi_cell(w, h, txt)


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


def _luma(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_color_for_bg(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    return (255, 255, 255) if _luma(bg) < 145 else (18, 22, 30)


class Layout:
    def __init__(self):
        self.page_w = inch(11.0)
        self.page_h = inch(8.5)

        self.margin_l = inch(0.90)
        self.margin_r = inch(0.90)
        self.margin_t = inch(0.75)
        self.margin_b = inch(0.70)

        self.cols = 12
        self.gutter = inch(0.18)
        self.base = inch(0.14)

        self.live_w = self.page_w - self.margin_l - self.margin_r
        self.live_h = self.page_h - self.margin_t - self.margin_b
        self.col_w = (self.live_w - (self.cols - 1) * self.gutter) / self.cols

    def x(self, col: int) -> float:
        return self.margin_l + col * (self.col_w + self.gutter)

    def w(self, span: int) -> float:
        if span <= 0:
            return 0.0
        return span * self.col_w + (span - 1) * self.gutter

    def y0(self) -> float:
        return self.margin_t


FONT_DIR = Path("assets") / "fontpack"


class FontPack:
    def __init__(self):
        self.loaded = False
        self.head = "Head"
        self.body = "Body"
        self.body_m = "BodyM"


def register_fonts(pdf: FPDF) -> FontPack:
    pack = FontPack()
    head_sb = FONT_DIR / "Sora-SemiBold.ttf"
    head_b = FONT_DIR / "Sora-Bold.ttf"
    body_r = FONT_DIR / "Inter-Regular.ttf"
    body_m = FONT_DIR / "Inter-Medium.ttf"
    body_sb = FONT_DIR / "Inter-SemiBold.ttf"

    if not (head_sb.exists() and head_b.exists() and body_r.exists() and body_m.exists() and body_sb.exists()):
        return pack

    try:
        pdf.add_font(pack.head, "", str(head_sb), uni=True)
        pdf.add_font(pack.head, "B", str(head_b), uni=True)
        pdf.add_font(pack.body, "", str(body_r), uni=True)
        pdf.add_font(pack.body, "B", str(body_sb), uni=True)
        pdf.add_font(pack.body_m, "", str(body_m), uni=True)
        pack.loaded = True
        return pack
    except Exception:
        return pack


class RulesPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layout = Layout()
        self.fontpack = FontPack()
        self.brand_name = ""
        self.c_text = (18, 22, 30)
        self.c_muted = (112, 118, 128)
        self._latin_only = False
        self._suppress_footer = False

    def set_brand_fonts(self):
        self.fontpack = register_fonts(self)
        self._latin_only = (not self.fontpack.loaded)

    def f_head(self, weight: str, size: float):
        if self.fontpack.loaded:
            style = "B" if weight == "B" else ""
            self.set_font(self.fontpack.head, style, size)
        else:
            style = "B" if weight == "B" else ""
            self.set_font("Helvetica", style, size)

    def f_body(self, weight: str, size: float):
        if self.fontpack.loaded:
            if weight == "M":
                self.set_font(self.fontpack.body_m, "", size)
            elif weight == "B":
                self.set_font(self.fontpack.body, "B", size)
            else:
                self.set_font(self.fontpack.body, "", size)
        else:
            style = "B" if weight == "B" else ""
            self.set_font("Helvetica", style, size)

    def footer(self):
        if self._suppress_footer:
            return
        L = self.layout
        self.set_y(-L.margin_b + inch(0.22))
        self.f_body("R", 8)
        self.set_text_color(*self.c_muted)

        self.set_x(L.margin_l)
        self.cell(0, inch(0.18), safe_text(self.brand_name, self._latin_only), align="L")

        self.set_x(L.page_w - L.margin_r - inch(0.35))
        self.cell(inch(0.35), inch(0.18), str(self.page_no()), align="R")


def _full_bleed_color(pdf: RulesPDF, rgb: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(*rgb)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")


def _full_bleed_image(pdf: RulesPDF, img_path: str):
    pdf.add_page(orientation="L")
    pdf.image(img_path, x=0, y=0, w=pdf.w, h=pdf.h, keep_aspect_ratio=False)


def _panel(pdf: RulesPDF, x: float, y: float, w: float, h: float, fill: tuple[int, int, int]):
    pdf.set_fill_color(*fill)
    pdf.rect(x, y, w, h, style="F")


def _title_rule(pdf: RulesPDF, x: float, y: float, w: float, accent: tuple[int, int, int]):
    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.2)
    pdf.line(x, y, x + w, y)


def page_title(pdf: RulesPDF, title: str, accent: tuple[int, int, int]):
    L = pdf.layout
    x = L.x(0)
    y = L.y0()
    pdf.set_text_color(*pdf.c_text)
    pdf.f_head("B", 22)
    pdf.set_xy(x, y)
    pdf.cell(0, inch(0.28), safe_text(title, pdf._latin_only))
    _title_rule(pdf, x, y + inch(0.40), inch(1.55), accent)
    pdf.set_xy(x, y + inch(0.62))


def bullet_list(pdf: RulesPDF, items: list[str], x: float, w: float, line_h: float, max_items: int = 12):
    prefix = "• " if pdf.fontpack.loaded else "* "
    pdf.f_body("R", 11)
    pdf.set_text_color(35, 40, 50)
    n = 0
    for it in items or []:
        if n >= max_items:
            break
        s = (it or "").strip()
        if not s:
            continue
        pdf.set_x(x)
        safe_multicell(pdf, w, line_h, safe_text(prefix + s, pdf._latin_only))
        pdf.ln(inch(0.06))
        n += 1


def body_paras(pdf: RulesPDF, text: str, x: float, w: float):
    if not text:
        return
    pdf.f_body("R", 11)
    pdf.set_text_color(*pdf.c_text)
    for para in (text or "").split("\n"):
        p = para.strip()
        if not p:
            pdf.ln(inch(0.14))
            continue
        pdf.set_x(x)
        safe_multicell(pdf, w, inch(0.22), safe_text(p, pdf._latin_only))
        pdf.ln(inch(0.08))


def cover_page(pdf: RulesPDF, brand: str, subtitle: str, cover_img: Optional[str], primary_rgb: tuple[int, int, int], accent_rgb: tuple[int, int, int]):
    pdf._suppress_footer = True

    if cover_img:
        _full_bleed_image(pdf, cover_img)
    else:
        _full_bleed_color(pdf, primary_rgb)

    L = pdf.layout
    x = L.x(0)
    y = inch(1.15)
    w = L.w(7)
    h = inch(4.15)

    _panel(pdf, x, y, w, h, (10, 12, 16))

    pdf.set_text_color(255, 255, 255)
    pdf.f_head("B", 46)
    pdf.set_xy(x + inch(0.38), y + inch(0.58))
    safe_multicell(pdf, w - inch(0.76), inch(0.42), safe_text(brand, pdf._latin_only))

    pdf.f_body("R", 13)
    pdf.set_xy(x + inch(0.38), y + inch(2.95))
    safe_multicell(pdf, w - inch(0.76), inch(0.26), safe_text(subtitle, pdf._latin_only))

    _title_rule(pdf, x + inch(0.38), y + h - inch(0.42), inch(1.55), accent_rgb)

    pdf._suppress_footer = False


def how_to_use_page(pdf: RulesPDF, brand: str, date_utc: str, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")

    page_title(pdf, "How to use this", accent)
    L = pdf.layout
    x = L.x(0)
    w = L.w(8)

    text = (
        "This is an operational rule set for language.\n"
        "Use it to write, approve, and police messaging under time pressure.\n\n"
        "If copy conflicts with this document, the document wins.\n"
        "If you want to sound nicer, softer, or broader, stop and re-read the bans.\n\n"
        f"Generated for {brand} on {date_utc}."
    )
    pdf.set_text_color(60, 66, 76)
    pdf.f_body("R", 11)
    pdf.set_xy(x, pdf.get_y() + inch(0.10))
    safe_multicell(pdf, w, inch(0.22), safe_text(text, pdf._latin_only))


def executive_summary_page(pdf: RulesPDF, items: list[str], accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    page_title(pdf, "Executive summary", accent)

    L = pdf.layout
    x = L.x(0)
    w = L.w(9)
    bullet_list(pdf, items, x, w, inch(0.22), max_items=12)


def rules_page(pdf: RulesPDF, title: str, blocks: list[tuple[str, list[str]]], accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    page_title(pdf, title, accent)

    L = pdf.layout
    x = L.x(0)
    col_w = L.w(6)
    y0 = pdf.get_y() + inch(0.10)

    for i, (h, items) in enumerate(blocks):
        cx = x if i % 2 == 0 else L.x(6)
        cy = y0 if i < 2 else pdf.get_y() + inch(0.12)
        pdf.set_xy(cx, cy)
        pdf.set_text_color(*pdf.c_text)
        pdf.f_body("B", 12)
        pdf.cell(col_w, inch(0.22), safe_text(h, pdf._latin_only), ln=1)
        pdf.ln(inch(0.08))
        bullet_list(pdf, items, cx, col_w, inch(0.22), max_items=10)

        if i % 2 == 1:
            pdf.set_y(max(pdf.get_y(), cy) + inch(0.18))


def examples_page(pdf: RulesPDF, ex: dict, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    page_title(pdf, "Examples", accent)

    L = pdf.layout
    x = L.x(0)
    left_w = L.w(6)
    right_x = L.x(7)
    right_w = L.w(5)

    sales = (ex.get("sales_sentence", "") or "").strip()
    headlines = [s for s in (ex.get("headlines", []) or []) if (s or "").strip()][:8]
    posts = [s for s in (ex.get("social_posts", []) or []) if (s or "").strip()][:6]
    ba = (ex.get("before_after", []) or [])[:4]

    pdf.set_xy(x, pdf.get_y() + inch(0.10))
    pdf.set_text_color(*pdf.c_text)
    pdf.f_body("B", 12)
    pdf.cell(left_w, inch(0.22), safe_text("Sales sentence", pdf._latin_only), ln=1)
    pdf.ln(inch(0.08))
    pdf.f_body("R", 11)
    pdf.set_text_color(35, 40, 50)
    safe_multicell(pdf, left_w, inch(0.22), safe_text(sales, pdf._latin_only))
    pdf.ln(inch(0.16))

    pdf.set_text_color(*pdf.c_text)
    pdf.f_body("B", 12)
    pdf.cell(left_w, inch(0.22), safe_text("Headlines", pdf._latin_only), ln=1)
    pdf.ln(inch(0.08))
    bullet_list(pdf, headlines, x, left_w, inch(0.22), max_items=8)

    # Right column: posts
    pdf.set_xy(right_x, pdf.layout.y0() + inch(0.62))
    pdf.set_text_color(*pdf.c_text)
    pdf.f_body("B", 12)
    pdf.cell(right_w, inch(0.22), safe_text("Social posts", pdf._latin_only), ln=1)
    pdf.ln(inch(0.08))
    bullet_list(pdf, posts, right_x, right_w, inch(0.22), max_items=7)

    # Before/after blocks at bottom
    pdf.set_y(pdf.h - pdf.layout.margin_b - inch(2.55))
    pdf.set_x(x)
    pdf.set_text_color(*pdf.c_text)
    pdf.f_body("B", 12)
    pdf.cell(0, inch(0.22), safe_text("Before and after", pdf._latin_only), ln=1)
    pdf.ln(inch(0.08))

    for item in ba:
        before = (item.get("before", "") or "").strip()
        after = (item.get("after", "") or "").strip()
        rule = (item.get("rule", "") or "").strip()

        line = f"Rule: {rule}" if rule else "Rule: "
        pdf.f_body("B", 10)
        pdf.set_text_color(55, 60, 70)
        safe_multicell(pdf, L.w(12), inch(0.20), safe_text(line, pdf._latin_only))

        pdf.f_body("R", 10)
        pdf.set_text_color(35, 40, 50)
        safe_multicell(pdf, L.w(12), inch(0.20), safe_text("Before: " + before, pdf._latin_only))
        safe_multicell(pdf, L.w(12), inch(0.20), safe_text("After:  " + after, pdf._latin_only))
        pdf.ln(inch(0.10))


def guardrails_page(pdf: RulesPDF, guard: dict, accent: tuple[int, int, int]):
    fm = [s for s in (guard.get("failure_modes", []) or []) if (s or "").strip()]
    rf = [s for s in (guard.get("red_flags_in_copy", []) or []) if (s or "").strip()]
    ck = [s for s in (guard.get("approval_checklist", []) or []) if (s or "").strip()]

    rules_page(
        pdf,
        "Guardrails",
        [
            ("Failure modes", fm[:10]),
            ("Red flags in copy", rf[:10]),
            ("Approval checklist", ck[:10]),
        ],
        accent,
    )


def usage_page(pdf: RulesPDF, usage: dict, accent: tuple[int, int, int]):
    hu = [s for s in (usage.get("how_to_use", []) or []) if (s or "").strip()]
    wr = [s for s in (usage.get("when_to_regenerate", []) or []) if (s or "").strip()]
    bw = [s for s in (usage.get("how_to_brief_writers", []) or []) if (s or "").strip()]

    rules_page(
        pdf,
        "Usage",
        [
            ("How to use", hu[:10]),
            ("When to regenerate", wr[:10]),
            ("How to brief writers", bw[:10]),
        ],
        accent,
    )


def appendix_page(pdf: RulesPDF, app: dict, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    page_title(pdf, "Appendix", accent)

    L = pdf.layout
    x = L.x(0)
    w = L.w(12)

    colors = (app.get("color_suggestions", []) or [])[:6]
    typo = (app.get("typography_suggestions", {}) or {})

    pdf.set_xy(x, pdf.get_y() + inch(0.08))
    pdf.set_text_color(*pdf.c_text)
    pdf.f_body("B", 12)
    pdf.cell(0, inch(0.22), safe_text("Color suggestions", pdf._latin_only), ln=1)
    pdf.ln(inch(0.08))

    sw = inch(0.90)
    sh = inch(0.38)
    for c in colors:
        name = (c.get("name", "") or "").strip()
        hx = (c.get("hex", "") or "").strip()
        reason = (c.get("reason", "") or "").strip()
        rgb = _hex_to_rgb(hx, (220, 220, 220))

        pdf.set_fill_color(*rgb)
        pdf.rect(x, pdf.get_y(), sw, sh, style="F")

        pdf.set_xy(x + sw + inch(0.18), pdf.get_y() - inch(0.02))
        pdf.f_body("B", 11)
        pdf.set_text_color(*pdf.c_text)
        label = f"{name}  {_rgb_to_hex(rgb)}".strip()
        pdf.cell(0, inch(0.22), safe_text(label, pdf._latin_only), ln=1)

        pdf.f_body("R", 10)
        pdf.set_text_color(70, 75, 85)
        pdf.set_x(x + sw + inch(0.18))
        safe_multicell(pdf, w - sw - inch(0.18), inch(0.20), safe_text(reason, pdf._latin_only))
        pdf.ln(inch(0.16))

    pdf.ln(inch(0.22))
    pdf.f_body("B", 12)
    pdf.set_text_color(*pdf.c_text)
    pdf.cell(0, inch(0.22), safe_text("Typography suggestions", pdf._latin_only), ln=1)
    pdf.ln(inch(0.08))

    primary = (typo.get("primary", "") or "").strip()
    secondary = (typo.get("secondary", "") or "").strip()
    rationale = (typo.get("rationale", "") or "").strip()

    pdf.f_body("R", 11)
    pdf.set_text_color(55, 60, 70)
    safe_multicell(pdf, w, inch(0.22), safe_text(f"Primary: {primary}", pdf._latin_only))
    safe_multicell(pdf, w, inch(0.22), safe_text(f"Secondary: {secondary}", pdf._latin_only))
    pdf.ln(inch(0.08))
    safe_multicell(pdf, w, inch(0.22), safe_text(rationale, pdf._latin_only))


def back_cover(pdf: RulesPDF, brand: str, bg_rgb: tuple[int, int, int]):
    pdf._suppress_footer = True
    _full_bleed_color(pdf, bg_rgb)
    L = pdf.layout

    tc = text_color_for_bg(bg_rgb)
    pdf.set_text_color(*tc)
    pdf.f_head("B", 18)

    x = L.margin_l
    y = pdf.h - L.margin_b - inch(0.55)
    pdf.set_xy(x, y)
    pdf.cell(0, inch(0.24), safe_text(brand, pdf._latin_only))

    pdf.f_body("R", 11)
    pdf.set_xy(x, y + inch(0.22))
    pdf.cell(0, inch(0.22), safe_text("Messaging rules", pdf._latin_only))
    pdf._suppress_footer = False


def render_pdf(data: dict, include_images: bool, unsplash_key: str) -> bytes:
    meta = data.get("meta", {}) or {}
    hero = data.get("hero", {}) or {}
    appendix = data.get("appendix", {}) or {}

    brand = (meta.get("brand_name", "") or "").strip() or "Brand"
    date_utc = (meta.get("date_utc", "") or "").strip() or utc_date_str()

    # Use appendix colors if present, else default.
    colors = (appendix.get("color_suggestions", []) or [])
    primary_rgb = (18, 22, 30)
    accent_rgb = (28, 125, 255)
    if colors:
        # Try to pick the first suggestion as primary, second as accent.
        if len(colors) >= 1:
            primary_rgb = _hex_to_rgb((colors[0].get("hex", "") or ""), primary_rgb)
        if len(colors) >= 2:
            accent_rgb = _hex_to_rgb((colors[1].get("hex", "") or ""), accent_rgb)

    pdf = RulesPDF(orientation="L", unit="mm", format="letter")
    pdf.set_auto_page_break(auto=True, margin=pdf.layout.margin_b)
    pdf.set_brand_fonts()
    pdf.brand_name = brand

    cover_img = None
    tmp_files: list[str] = []

    if include_images:
        if requests is None:
            include_images = False
        if not unsplash_key:
            include_images = False

    if include_images:
        q = cover_query_from_output(data)
        cover_img = unsplash_cover_image(unsplash_key, q)
        if cover_img:
            tmp_files.append(cover_img)

    subtitle = (hero.get("subtitle", "") or "").strip() or "Operational language and control rules"
    cover_page(pdf, brand=brand, subtitle=subtitle, cover_img=cover_img, primary_rgb=primary_rgb, accent_rgb=accent_rgb)

    how_to_use_page(pdf, brand=brand, date_utc=date_utc, accent=accent_rgb)

    exec_sum = (data.get("executive_summary", {}) or {}).get("non_negotiables", []) or []
    executive_summary_page(pdf, [s for s in exec_sum if (s or "").strip()], accent_rgb)

    mr = data.get("messaging_rules", {}) or {}
    vr = data.get("voice_rules", {}) or {}
    ex = data.get("examples", {}) or {}
    guard = data.get("guardrails", {}) or {}
    usage = data.get("usage", {}) or {}

    rules_page(
        pdf,
        "Messaging rules",
        [
            ("What we sell", [mr.get("what_we_sell", "")]),
            ("Doctrine", [s for s in (mr.get("doctrine", []) or []) if (s or "").strip()][:10]),
            ("Allowed framing patterns", [s for s in (mr.get("allowed_framing_patterns", []) or []) if (s or "").strip()][:10]),
            ("Forbidden framing patterns", [s for s in (mr.get("forbidden_framing_patterns", []) or []) if (s or "").strip()][:10]),
            ("Banned words", [s for s in (mr.get("banned_words", []) or []) if (s or "").strip()][:12]),
            ("Proof standard", [s for s in (mr.get("proof_standard", []) or []) if (s or "").strip()][:10]),
        ],
        accent_rgb,
    )

    rules_page(
        pdf,
        "Voice rules",
        [
            ("Must sound like", [s for s in (vr.get("must_sound_like", []) or []) if (s or "").strip()][:10]),
            ("Must not sound like", [s for s in (vr.get("must_not_sound_like", []) or []) if (s or "").strip()][:10]),
            ("Rules", [s for s in (vr.get("rules", []) or []) if (s or "").strip()][:10]),
            ("Do say", [s for s in (vr.get("do_say", []) or []) if (s or "").strip()][:10]),
            ("Do not say", [s for s in (vr.get("do_not_say", []) or []) if (s or "").strip()][:10]),
        ],
        accent_rgb,
    )

    examples_page(pdf, ex, accent_rgb)
    guardrails_page(pdf, guard, accent_rgb)
    usage_page(pdf, usage, accent_rgb)
    appendix_page(pdf, appendix, accent_rgb)
    back_cover(pdf, brand, primary_rgb)

    out = pdf.output(dest="S")
    pdf_bytes = bytes(out) if isinstance(out, (bytes, bytearray)) else str(out).encode("latin-1", "replace")

    for p in tmp_files:
        try:
            os.unlink(p)
        except Exception:
            pass

    return pdf_bytes


# =========================
# UI helpers
# =========================
def render_progress(step_index: int, steps: list[dict]):
    total = len(steps)
    current = min(step_index + 1, total)
    st.progress(min(max(current / max(total, 1), 0.0), 1.0))
    st.caption(f"Question {current} of {total}")


def render_question(q: Question):
    key = f"ans_{q.key}"
    current = st.session_state.answers.get(q.key)

    if q.qtype == "text":
        val = st.text_input(q.title, value=current or "", placeholder=q.placeholder, key=key)
        st.session_state.answers[q.key] = (val or "").strip()

    elif q.qtype == "textarea":
        val = st.text_area(q.title, value=current or "", placeholder=q.placeholder, height=170, key=key)
        st.session_state.answers[q.key] = (val or "").strip()

    else:
        st.session_state.answers[q.key] = current


def validate_step(step: dict) -> tuple[bool, str]:
    q = get_question(step["qid"])
    val = st.session_state.answers.get(q.key)

    if not q.required:
        return True, ""

    if q.key == "brand_name":
        if not (val or "").strip():
            return False, "Brand name is required."
        return True, ""

    if not val or (isinstance(val, str) and not val.strip()):
        return False, "Write a short answer to continue."
    return True, ""


# =========================
# Views
# =========================
def landing_view():
    st.markdown('<div class="eyebrow">Messaging rules generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle">Stop bad messaging before it exists</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="heroSub">Answer 10 high leverage questions. Get an operational language rule set your team can use under pressure. No moodboards. No stock photo vibes by default.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="pills">
          <div class="pill">Operational rules</div>
          <div class="pill">Derived examples</div>
          <div class="pill">Guardrails and checklists</div>
          <div class="pill">Text first PDF</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2], gap="large")
    with col1:
        st.subheader("What you are buying")
        st.write("Not a questionnaire PDF.")
        st.write("A rule system that decides how the company is allowed to speak.")
        st.write("It outputs constraints, patterns, bans, and examples. It does not mirror your answers.")

    with col2:
        st.subheader("Output")
        st.write("Non negotiables")
        st.write("Messaging rules and banned language")
        st.write("Voice rules and before/after rewrites")
        st.write("Approval checklist for fast posting")

    with st.expander("Advanced settings", expanded=False):
        st.session_state.provider = st.selectbox(
            "LLM provider",
            options=["gemini", "openai"],
            index=0 if st.session_state.provider == "gemini" else 1,
        )

        if st.session_state.provider == "gemini":
            st.session_state.gemini_key = st.text_input(
                "Gemini API key",
                type="password",
                value=st.session_state.gemini_key,
            )
        else:
            st.session_state.openai_key = st.text_input(
                "OpenAI API key",
                type="password",
                value=st.session_state.openai_key,
            )
            st.session_state.openai_model = st.text_input(
                "OpenAI model",
                value=st.session_state.openai_model,
            )

        st.session_state.include_images = st.checkbox(
            "Include a single cover image (optional)",
            value=bool(st.session_state.include_images),
            help="Default off. If enabled, uses Unsplash for one abstract cover image.",
        )
        if st.session_state.include_images:
            st.session_state.unsplash_key = st.text_input(
                "Unsplash access key",
                type="password",
                value=st.session_state.unsplash_key,
            )
            if requests is None:
                st.warning("requests is not available, images will be disabled.")

    st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
    if st.button("Start the 10 question interview"):
        st.session_state.step_index = 0
        go("wizard")
    st.markdown("</div>", unsafe_allow_html=True)


def wizard_view():
    steps = wizard_steps()
    st.session_state.step_index = max(0, min(st.session_state.step_index, len(steps) - 1))
    step = steps[st.session_state.step_index]

    render_progress(st.session_state.step_index, steps)
    st.write("")

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
        label = "Next"
        if st.button(label):
            ok, msg = validate_step(step)
            if not ok:
                st.error(msg)
            else:
                if st.session_state.step_index >= len(steps) - 1:
                    go("confirm")
                else:
                    st.session_state.step_index += 1
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def confirm_view():
    st.markdown('<div class="eyebrow">Confirmation</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Ready to generate</div>', unsafe_allow_html=True)

    remaining = max(st.session_state.gen_max - st.session_state.gen_used, 0)
    st.caption(f"Generations remaining: {remaining} of {st.session_state.gen_max}")

    with st.expander("Review inputs", expanded=False):
        for q in QUESTIONS:
            ans = st.session_state.answers.get(q.key)
            if ans is None or ans == "":
                continue
            st.markdown(f"**{q.title}**")
            st.write(ans)
            st.markdown("")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        if st.button("Generate PDF", disabled=(remaining <= 0)):
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)


def generate_view():
    st.markdown('<div class="eyebrow">Generating</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Building your rule set</div>', unsafe_allow_html=True)
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    remaining = st.session_state.gen_max - st.session_state.gen_used
    if remaining <= 0:
        st.error("No generations remaining.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("done" if st.session_state.pdf_bytes else "confirm")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    brand = (st.session_state.answers.get("brand_name", "") or "").strip()
    if not brand:
        st.error("Brand name is required.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    stage = st.empty()

    try:
        with st.spinner("Working..."):
            stage.write("Defining rules")
            prompt = build_prompt(st.session_state.answers, version_str=str(st.session_state.gen_used + 1))

            provider = make_provider()
            data, model_used = provider.generate_json(prompt, timeout_s=45)

            stage.write("Building PDF")
            time.sleep(0.05)

            include_images = bool(st.session_state.include_images)
            unsplash_key = (st.session_state.unsplash_key or "").strip()
            pdf_bytes = render_pdf(data, include_images=include_images, unsplash_key=unsplash_key)

        st.session_state.last_json = data
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
    st.markdown('<div class="heroTitle" style="font-size:34px;">Download your PDF</div>', unsafe_allow_html=True)

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
