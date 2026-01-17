import json
import os
import re
import tempfile
import time
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

import concurrent.futures
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

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")


try:
    from PIL import Image  # noqa
except Exception:
    Image = None


# =========================
# Session state
# =========================
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
        "provider": "gemini",   # gemini or openai
        "gemini_key": "",
        "openai_key": "",
        "openai_model": "gpt-4.1-mini",

        # Images
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
    gemini_key = st.session_state.gemini_key
    openai_key = st.session_state.openai_key
    openai_model = st.session_state.openai_model
    unsplash_key = st.session_state.unsplash_key
    provider = st.session_state.provider
    include_images = st.session_state.include_images

    st.session_state.clear()
    ss_init()

    if keep_keys:
        st.session_state.gemini_key = gemini_key
        st.session_state.openai_key = openai_key
        st.session_state.openai_model = openai_model
        st.session_state.unsplash_key = unsplash_key
        st.session_state.provider = provider
        st.session_state.include_images = include_images


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

.block-container { max-width: 1180px; padding-top: 6.5rem !important; padding-bottom: 3.0rem; }

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
# Intake
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
    qtype: str
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
    Question("q1", "foundation", "Brand name", "The anchor. Everything else follows.", "text", "brand_name",
             placeholder="Example: Oura"),
    Question("q2", "foundation", "Define the brand in one sentence", "If this is vague, the rest becomes noise.", "textarea", "one_sentence",
             placeholder="We help ... by ..."),
    Question("q3", "foundation", "Why does this deserve to exist", "Not an origin story. The reason this matters.", "textarea", "why_exist",
             placeholder="Because ..."),
    Question("q4", "foundation", "What is the misunderstood problem you fix", "The lazy assumption you reject.", "textarea", "misunderstood_problem",
             placeholder="Most people think ... but ..."),
    Question("q5", "foundation", "What do you sell in reality", "Not the product. The outcome people pay for.", "textarea", "real_outcome",
             placeholder="We sell ..."),
    Question("q6", "foundation", "Your hard no", "The boundary that keeps the brand clean.", "textarea", "hard_no",
             placeholder="We will never ..."),

    Question("q7", "audience", "Describe one core customer you would recognize instantly", "Write one real person, not a segment.", "textarea", "core_customer",
             placeholder="They are ... They care about ..."),
    Question("q8", "audience", "What do they want but rarely say out loud", "This lever is where competitors usually fail.", "textarea", "secret_want",
             placeholder="Secretly they want ..."),
    Question("q9", "audience", "What stops them from buying", "Write the objection in their words.", "textarea", "primary_objection",
             placeholder="I am not sure because ..."),
    Question("q10", "audience", "What convinces them", "Proof they trust, not claims you like.", "textarea", "trust_trigger",
             placeholder="They trust ..."),
    Question("q11", "audience", "What misconception about your category must be broken", "The myth you refuse to repeat.", "textarea", "category_myth",
             placeholder="People assume ..."),
    Question("q12", "audience", "Worst experience they could have with you", "Define what must never happen.", "textarea", "worst_experience",
             placeholder="They must never feel ..."),

    Question("q13", "positioning", "What brand do you refuse to resemble", "Your anti model clarifies you fast.", "textarea", "anti_brand",
             placeholder="We refuse to feel like ..."),
    Question("q14", "positioning", "Finish: They are the brand that ...", "Write the truth, not a slogan.", "textarea", "positioning_sentence",
             placeholder="They are the brand that ..."),
    Question("q15", "positioning", "Your unfair advantage", "Hard to copy, even with money.", "textarea", "unfair_advantage",
             placeholder="We have ... that others cannot ..."),
    Question("q16", "positioning", "Wrong category people put you in", "Where people misfile you.", "text", "wrong_category",
             placeholder="Example: productivity app"),
    Question("q17", "positioning", "Category you actually own", "The simplest category that makes you understood.", "text", "right_category",
             placeholder="Example: recovery tech"),
    Question("q18", "positioning", "Pick an animal for your posture and energy", "Useful shorthand. Not cute.", "cards", "animal",
             options=["Fox", "Hawk", "Panther", "Owl", "Dolphin", "Wolf", "Bear", "Raven", "Falcon", "Stallion", "Other"]),

    Question("q19", "voice", "Three words you must sound like", "If you choose friendly, you have chosen nothing.", "text", "tone_words",
             placeholder="Example: precise, calm, bold"),
    Question("q20", "voice", "Three banned words", "If you use these, the brand becomes generic.", "text", "banned_words",
             placeholder="Example: innovative, seamless, disruptive"),
    Question("q21", "voice", "Your signature belief", "The opinion that creates gravity.", "textarea", "signature_belief",
             placeholder="We believe ..."),
    Question("q22", "voice", "One close sentence sales can use", "If this is unclear, the brand is unclear.", "textarea", "close_sentence",
             placeholder="The simplest truth is ..."),
    Question("q23", "voice", "What a satisfied customer would say", "Write it like a real person talking.", "textarea", "customer_quote",
             placeholder="Honestly, I ..."),
    Question("q24", "voice", "Choose your voice energy", "Choose energy, not adjectives.", "cards", "voice_energy",
             options=["Calm", "Confident", "Bold", "Sharp", "Warm", "Clinical"]),

    Question("q25", "visual", "Taste references and why", "Name them fast. One word why is enough.", "textarea", "taste_refs",
             placeholder="Brand: why\nBrand: why"),
    Question("q26", "visual", "Select vibes to avoid", "What would instantly make you look wrong.", "checks", "avoid_vibes",
             options=["Corporate", "Startup hype", "Luxury cliche", "Playful cartoon", "Sterile tech", "Lifestyle fluff", "Trend chasing"]),
    Question("q27", "visual", "If the brand were a place, what place is it", "Sets layout and atmosphere.", "cards", "brand_place",
             options=["Gallery", "High end hotel", "Workshop", "Library", "Clinic", "Studio", "Control room", "Other"]),
    Question("q28", "visual", "What should people feel before they understand", "First impression matters more than features.", "cards", "first_impression",
             options=["Calm", "Controlled", "Excited", "Safe", "Powerful", "Curious"]),
    Question("q29", "visual", "What must never appear in your visuals", "Hard constraints save time later.", "textarea", "never_visuals",
             placeholder="Never use ..."),
    Question("q30", "visual", "What are you afraid this becomes if done wrong", "Name the failure mode.", "textarea", "fear",
             placeholder="If we get this wrong, it becomes ..."),
]


def wizard_steps() -> list[dict]:
    steps: list[dict] = []
    for sec in SECTIONS:
        steps.append({"type": "section", "section_id": sec.id})
        for q in QUESTIONS:
            if q.section_id == sec.id:
                steps.append({"type": "question", "qid": q.id})
    return steps


def get_question(qid: str) -> Question:
    for q in QUESTIONS:
        if q.id == qid:
            return q
    raise KeyError(qid)


def get_section(sid: str) -> Section:
    for s in SECTIONS:
        if s.id == sid:
            return s
    return SECTIONS[0]


# =========================
# Shared JSON helpers
# =========================
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


def validate_schema_keys(data: dict) -> None:
    required = [
        "meta", "colors", "typography", "hero",
        "executive_summary", "positioning", "audience",
        "messaging", "voice", "visual_direction",
        "guardrails", "usage"
    ]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"JSON missing required keys: {missing}")


# =========================
# Prompt and schema (Decision Spec oriented)
# =========================
FONT_POOL = [
    "Inter", "Sora", "Manrope", "DM Sans", "Plus Jakarta Sans", "Space Grotesk",
    "IBM Plex Sans", "Work Sans", "Outfit", "Urbanist", "Public Sans", "Rubik",
    "Source Sans 3", "Noto Sans", "Noto Serif", "Lora", "Merriweather", "Libre Baskerville",
    "Fraunces", "Cormorant Garamond", "Spectral", "Crimson Pro", "EB Garamond",
    "Montserrat", "Raleway", "Karla", "Figtree", "Nunito Sans", "Hanken Grotesk",
    "Archivo", "Barlow", "Overpass", "Mulish", "Cabin", "Titillium Web"
]


def build_prompt(answers: dict, version_str: str) -> str:
    brand = (answers.get("brand_name", "") or "").strip()
    answers_json = json.dumps(answers, ensure_ascii=False, indent=2)

    schema = (
        "{\n"
        '  "meta": { "brand_name": "", "version": "", "date_utc": "" },\n'
        '  "colors": {\n'
        '    "primary_hex": "", "accent_hex": "", "neutral_hex": "", "background_hex": "",\n'
        '    "primary_reason": "", "accent_reason": "", "neutral_reason": "", "background_reason": ""\n'
        "  },\n"
        '  "typography": {\n'
        '    "primary_font": "", "secondary_font": "",\n'
        '    "primary_use": "", "secondary_use": "",\n'
        '    "rationale": ""\n'
        "  },\n"
        '  "hero": { "headline": "", "subhead": "", "deck_subtitle": "" },\n'
        '  "executive_summary": { "decisions": [""] },\n'
        '  "positioning": { "positioning_statement": "", "category": "", "anti_position": "" },\n'
        '  "audience": { "core_customer": "", "core_tension": "", "primary_objection": "", "trust_trigger": "" },\n'
        '  "messaging": { "core_message": "", "key_messages": [ { "message": "", "proof": "" } ] },\n'
        '  "voice": { "principles": [""], "do_say": [""], "do_not_say": [""], "examples": { "before": "", "after": "" } },\n'
        '  "visual_direction": {\n'
        '     "intent": "",\n'
        '     "feels_like": [""],\n'
        '     "never_feels_like": [""],\n'
        '     "hard_bans": [""],\n'
        '     "acceptance_test": [""]\n'
        "  },\n"
        '  "guardrails": { "failure_modes": [""] },\n'
        '  "usage": { "how_to_use": [""] }\n'
        "}\n"
    )

    prompt = (
        "You are a senior brand strategist.\n"
        "Write a Decision Spec, not a brand book.\n"
        "Decide. Do not decorate.\n"
        "Prefer rules, constraints, and tests.\n"
        "Be concise and practical.\n"
        "Avoid cliches and startup hype.\n"
        "Return ONLY valid JSON that matches the schema exactly.\n"
        "No markdown. No commentary. No extra keys.\n\n"
        "COLOR RULES\n"
        "Return real hex colors.\n"
        "Each color must include a one sentence reason that connects to the brand.\n"
        "No generic reasons.\n\n"
        "TYPOGRAPHY RULES\n"
        "Pick fonts that fit the brand.\n"
        "Choose from this pool when possible:\n"
        f"{', '.join(FONT_POOL)}\n"
        "Explain the choice briefly in typography.rationale.\n"
        "Define primary_use and secondary_use.\n\n"
        "HERO RULES\n"
        "hero.headline is 6 to 12 words.\n"
        "hero.subhead is 1 sentence.\n"
        "hero.deck_subtitle must be short.\n\n"
        "JSON SCHEMA\n"
        f"{schema}\n"
        "INPUT\n"
        f"Brand name: {brand}\n"
        f"Version: {version_str}\n"
        f"Date UTC: {utc_date_str()}\n\n"
        "Intake answers JSON:\n"
        f"{answers_json}\n\n"
        "Return JSON only.\n"
    )
    return prompt


# =========================
# Providers
# =========================
PREFERRED_GEMINI_MODEL_CONTAINS = [
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini",
]


def list_generation_models_gemini() -> list[str]:
    if genai is None:
        return []
    out: list[str] = []
    try:
        for m in genai.list_models():
            name = getattr(m, "name", "") or ""
            methods = getattr(m, "supported_generation_methods", None) or []
            if name and "generateContent" in methods:
                out.append(name)
    except Exception:
        return []
    return out


def choose_models_to_try_gemini() -> list[str]:
    avail = list_generation_models_gemini()
    if not avail:
        return PREFERRED_GEMINI_MODEL_CONTAINS[:]
    chosen: list[str] = []
    for p in PREFERRED_GEMINI_MODEL_CONTAINS:
        for n in avail:
            if p in n and n not in chosen:
                chosen.append(n)
    for n in avail:
        if n not in chosen:
            chosen.append(n)
    return chosen


def generate_schema_gemini(prompt: str, api_key: str, timeout_s: int = 35) -> Tuple[dict, str]:
    if genai is None:
        raise RuntimeError("google.generativeai is not installed.")
    genai.configure(api_key=api_key)

    models_to_try = choose_models_to_try_gemini()
    last_err: Exception | None = None

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(model.generate_content, prompt)
                resp = fut.result(timeout=timeout_s)
            raw = (getattr(resp, "text", "") or "").strip()
            data = json.loads(extract_json_object(raw))
            validate_schema_keys(data)
            return data, model_name
        except concurrent.futures.TimeoutError:
            last_err = RuntimeError(f"Timeout after {timeout_s} seconds.")
        except Exception as e:
            last_err = e

    raise RuntimeError(f"Gemini generation failed: {last_err}")


def generate_schema_openai(prompt: str, api_key: str, model: str, timeout_s: int = 35) -> Tuple[dict, str]:
    if OpenAI is None:
        raise RuntimeError("openai is not installed. Run: pip install openai")
    client = OpenAI(api_key=api_key)

    resp = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.2,
        max_output_tokens=2000,
    )
    raw = (resp.output_text or "").strip()
    data = json.loads(extract_json_object(raw))
    validate_schema_keys(data)
    return data, model


def generate_schema(prompt: str, provider: str, gemini_key: str, openai_key: str, openai_model: str, timeout_s: int = 35) -> Tuple[dict, str]:
    provider = (provider or "").strip().lower()
    if provider == "openai":
        if not openai_key:
            raise RuntimeError("Missing OpenAI API key.")
        return generate_schema_openai(prompt, openai_key, openai_model, timeout_s=timeout_s)

    if not gemini_key:
        raise RuntimeError("Missing Gemini API key.")
    return generate_schema_gemini(prompt, gemini_key, timeout_s=timeout_s)


# =========================
# Unsplash images (optional)
# =========================
UNSPLASH_API = "https://api.unsplash.com"


def _unsplash_headers(access_key: str) -> dict:
    return {
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1",
        "User-Agent": "BrandBibleGenerator/1.0",
    }


def _download_image_to_temp(url: str) -> Optional[str]:
    if requests is None:
        return None
    try:
        r = requests.get(url, timeout=18, headers={"User-Agent": "BrandBibleGenerator/1.0"}, allow_redirects=True)
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


def unsplash_random_images(access_key: str, queries: list[str], count: int, orientation: str = "landscape") -> list[str]:
    if not access_key or requests is None:
        return []
    if not queries:
        return []

    rng = random.Random(time.time_ns())
    out: list[str] = []
    tried = 0

    while len(out) < count and tried < count * 6:
        tried += 1
        q = rng.choice(queries)
        params = {
            "query": q,
            "orientation": orientation,
            "content_filter": "high",
            "count": 1,
        }
        try:
            r = requests.get(
                f"{UNSPLASH_API}/photos/random",
                headers=_unsplash_headers(access_key),
                params=params,
                timeout=18,
            )
            if r.status_code != 200:
                continue
            js = r.json()
            if isinstance(js, list) and js:
                js = js[0]
            urls = (js or {}).get("urls", {}) or {}
            url = urls.get("regular") or urls.get("full") or urls.get("raw")
            if not url:
                continue
            p = _download_image_to_temp(url)
            if not p:
                continue
            out.append(p)
        except Exception:
            continue

    return out


def build_image_queries(answers: dict, schema: dict) -> list[str]:
    vis = schema.get("visual_direction", {}) or {}
    kws = vis.get("imagery_keywords", []) or []
    kws = [str(x).strip() for x in kws if str(x).strip()]

    place = (answers.get("brand_place", "") or "").strip()
    impression = (answers.get("first_impression", "") or "").strip()
    energy = (answers.get("voice_energy", "") or "").strip()
    animal = (answers.get("animal", "") or "").strip()
    never = (answers.get("never_visuals", "") or "").lower()

    base = [
        "instrument panel close up",
        "control room interior",
        "industrial interface detail",
        "precision engineering detail",
        "brutalist architecture lines",
        "concrete geometry minimal",
        "technical schematic texture",
        "grid pattern minimal",
        "architectural corridor symmetry",
        "workshop tools minimal",
        "server room aisle",
        "industrial lab clean",
        "black metal surface texture",
        "steel structure detail",
        "empty interior no people",
        "architecture no people",
    ]

    if place:
        base.append(f"{place.lower()} interior minimal")
        base.append(f"{place.lower()} detail minimal")

    if impression and impression.lower() == "controlled":
        base.append("controlled environment interior")
        base.append("orderly industrial space")

    if energy and energy.lower() in ["sharp", "bold", "clinical"]:
        base.append("high contrast minimal architecture")
        base.append("monochrome industrial detail")

    if animal and animal.lower() in ["panther", "hawk", "falcon"]:
        base.append("dark minimal architecture")
        base.append("shadow geometry minimal")

    for k in kws[:10]:
        base.append(k)

    if "nature" in never:
        base.append("industrial interior not nature")
    if "neon" in never or "cyberpunk" in never:
        base.append("clean minimal not neon")
    if "meditation" in never or "yoga" in never:
        base.append("technical environment not wellness")
    if "faces" in never or "portrait" in never or "people" in never:
        base.append("no people")

    out: list[str] = []
    seen = set()
    for q in base:
        qn = " ".join(q.split()).strip().lower()
        if not qn or qn in seen:
            continue
        seen.add(qn)
        out.append(qn)
    return out


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
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2026", "...")
    t = t.replace("\u00A0", " ")
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


class BrandPDF(FPDF):
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
            self.set_font("Helvetica", "", size)

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


def _full_bleed_image(pdf: BrandPDF, img_path: str):
    pdf.add_page(orientation="L")
    pdf.image(img_path, x=0, y=0, w=pdf.w, h=pdf.h, keep_aspect_ratio=False)


def _full_bleed_color(pdf: BrandPDF, rgb: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(*rgb)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")


def _panel(pdf: BrandPDF, x: float, y: float, w: float, h: float, fill: tuple[int, int, int]):
    pdf.set_fill_color(*fill)
    pdf.rect(x, y, w, h, style="F")


def _title_rule(pdf: BrandPDF, x: float, y: float, w: float, accent: tuple[int, int, int]):
    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.2)
    pdf.line(x, y, x + w, y)


def page_title(pdf: BrandPDF, title: str, accent: tuple[int, int, int]):
    L = pdf.layout
    x = L.x(0)
    y = L.y0()
    pdf.set_text_color(*pdf.c_text)
    pdf.f_head("B", 22)
    pdf.set_xy(x, y)
    pdf.cell(0, inch(0.28), safe_text(title, pdf._latin_only))
    _title_rule(pdf, x, y + inch(0.40), inch(1.55), accent)
    pdf.set_xy(x, y + inch(0.62))


def cover_page(pdf: BrandPDF, brand: str, subtitle: str, photo_path: Optional[str], fallback_rgb: tuple[int, int, int]):
    pdf._suppress_footer = True
    if photo_path:
        _full_bleed_image(pdf, photo_path)
    else:
        _full_bleed_color(pdf, fallback_rgb)

    L = pdf.layout
    x = L.x(0)
    y = inch(1.30)
    w = L.w(7)
    h = inch(3.95)

    _panel(pdf, x, y, w, h, (10, 12, 16))

    pdf.set_text_color(255, 255, 255)
    pdf.f_head("B", 46)
    pdf.set_xy(x + inch(0.38), y + inch(0.58))
    safe_multicell(pdf, w - inch(0.76), inch(0.42), safe_text(brand, pdf._latin_only))

    pdf.f_body("R", 13)
    pdf.set_xy(x + inch(0.38), y + inch(2.85))
    safe_multicell(pdf, w - inch(0.76), inch(0.26), safe_text(subtitle, pdf._latin_only))
    pdf._suppress_footer = False


def intro_page(pdf: BrandPDF, brand: str, date_utc: str, image_path: Optional[str], accent: tuple[int, int, int], bg_rgb: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")

    L = pdf.layout
    left_x = L.x(0)
    top_y = L.y0()
    left_w = L.w(6)

    right_x = L.x(7)
    right_w = L.w(5)
    img_h = inch(5.35)

    pdf.set_text_color(*pdf.c_text)
    pdf.f_head("B", 24)
    pdf.set_xy(left_x, top_y)
    pdf.cell(0, inch(0.28), safe_text("How to use this", pdf._latin_only))
    _title_rule(pdf, left_x, top_y + inch(0.40), inch(1.55), accent)

    pdf.set_text_color(60, 66, 76)
    pdf.f_body("R", 11)
    pdf.set_xy(left_x, top_y + inch(0.72))
    t = (
        "This is a decision system.\n"
        "Use it to keep voice, visuals, and messaging consistent.\n\n"
        "Use this when writing copy, selecting visuals, designing pages, or approving work.\n"
        "If a decision conflicts with this document, the document wins.\n\n"
        f"Generated for {brand} on {date_utc}."
    )
    safe_multicell(pdf, left_w, inch(0.22), safe_text(t, pdf._latin_only))

    if image_path:
        pdf.image(image_path, x=right_x, y=top_y, w=right_w, h=img_h, keep_aspect_ratio=False)
    else:
        pdf.set_fill_color(*bg_rgb)
        pdf.rect(right_x, top_y, right_w, img_h, style="F")

    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.0)
    pdf.rect(right_x, top_y, right_w, img_h)


def contents_page(pdf: BrandPDF, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    page_title(pdf, "Contents", accent)

    L = pdf.layout
    x = L.x(0)
    y = pdf.get_y()

    items = [
        ("Executive summary", 4),
        ("Positioning", 6),
        ("Audience", 8),
        ("Messaging", 10),
        ("Voice", 12),
        ("Visual direction", 15),
        ("Color palette", 18),
        ("Typography", 19),
        ("Guardrails", 20),
        ("How to use this", 21),
    ]

    pdf.f_body("R", 12)
    pdf.set_text_color(55, 60, 70)

    yy = y + inch(0.10)
    for title, page in items:
        pdf.set_xy(x, yy)
        pdf.cell(L.w(8), inch(0.26), safe_text(title, pdf._latin_only))
        pdf.set_xy(L.x(9), yy)
        pdf.cell(L.w(3), inch(0.26), str(page), align="R")
        yy += inch(0.34)


def section_photo_opener(pdf: BrandPDF, title: str, subtitle: str, image_path: Optional[str], accent: tuple[int, int, int], fallback_rgb: tuple[int, int, int]):
    if image_path:
        _full_bleed_image(pdf, image_path)
    else:
        _full_bleed_color(pdf, fallback_rgb)

    L = pdf.layout
    x = L.x(0)
    y = inch(2.05)
    w = L.w(7)
    h = inch(3.05)

    _panel(pdf, x, y, w, h, (10, 12, 16))
    pdf.set_text_color(255, 255, 255)
    pdf.f_head("B", 44)
    pdf.set_xy(x + inch(0.38), y + inch(0.58))
    safe_multicell(pdf, w - inch(0.76), inch(0.42), safe_text(title, pdf._latin_only))

    pdf.f_body("R", 14)
    pdf.set_xy(x + inch(0.38), y + inch(2.10))
    safe_multicell(pdf, w - inch(0.76), inch(0.26), safe_text(subtitle, pdf._latin_only))

    _title_rule(pdf, x + inch(0.38), y + h - inch(0.42), inch(1.55), accent)


def content_page_base(pdf: BrandPDF, title: str, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    page_title(pdf, title, accent)


def bullet_list(pdf: BrandPDF, items: list[str], x: float, w: float, line_h: float, max_items: int = 10):
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


def body_paras(pdf: BrandPDF, text: str, x: float, w: float):
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


def split_two_col(pdf: BrandPDF, left_title: str, left_items: list[str], right_title: str, right_items: list[str]):
    L = pdf.layout
    x1 = L.x(0)
    x2 = L.x(6)
    w = L.w(5)
    y0 = pdf.get_y()

    def col(x: float, title: str, items: list[str]) -> float:
        pdf.set_xy(x, y0)
        pdf.set_text_color(*pdf.c_text)
        pdf.f_body("B", 12)
        pdf.cell(w, inch(0.22), safe_text(title, pdf._latin_only), ln=1)
        pdf.ln(inch(0.10))
        bullet_list(pdf, items, x, w, inch(0.22), max_items=9)
        return pdf.get_y()

    y1 = col(x1, left_title, left_items)
    y2 = col(x2, right_title, right_items)
    pdf.set_y(max(y1, y2) + inch(0.10))


def messaging_page(pdf: BrandPDF, msg: dict, image_path: Optional[str], accent: tuple[int, int, int], fallback_rgb: tuple[int, int, int]):
    content_page_base(pdf, "Messaging", accent)

    L = pdf.layout
    left_x = L.x(0)
    left_w = L.w(7)
    right_x = L.x(8)
    right_w = L.w(4)
    top = pdf.get_y()

    core = (msg.get("core_message", "") or "").strip()
    if core:
        pdf.set_xy(left_x, top)
        pdf.f_body("R", 11)
        pdf.set_text_color(55, 60, 70)
        safe_multicell(pdf, left_w, inch(0.22), safe_text(core, pdf._latin_only))
        pdf.ln(inch(0.10))

    kms = (msg.get("key_messages", []) or [])[:6]
    key_msgs = []
    proofs = []
    for km in kms:
        m = (km.get("message", "") or "").strip()
        p = (km.get("proof", "") or "").strip()
        if m:
            key_msgs.append(m)
        if p:
            proofs.append(p)

    y_after = pdf.get_y()
    pdf.set_xy(left_x, y_after + inch(0.18))
    pdf.f_body("B", 12)
    pdf.set_text_color(*pdf.c_text)
    pdf.cell(left_w, inch(0.22), safe_text("Key messages", pdf._latin_only), ln=1)
    pdf.ln(inch(0.08))
    bullet_list(pdf, key_msgs, left_x, left_w, inch(0.22), max_items=7)

    py = y_after + inch(0.18)
    pdf.set_xy(right_x, py)
    pdf.f_body("B", 12)
    pdf.set_text_color(*pdf.c_text)
    pdf.cell(right_w, inch(0.22), safe_text("Proof", pdf._latin_only), ln=1)
    pdf.ln(inch(0.08))
    bullet_list(pdf, proofs, right_x, right_w, inch(0.22), max_items=7)

    img_y = max(pdf.get_y(), py + inch(2.10)) + inch(0.25)
    img_h = pdf.h - img_y - pdf.layout.margin_b - inch(0.20)

    if img_h > inch(1.4):
        if image_path:
            try:
                pdf.image(image_path, x=pdf.layout.margin_l, y=img_y, w=pdf.layout.live_w, h=img_h, keep_aspect_ratio=False)
            except Exception:
                pdf.set_fill_color(*fallback_rgb)
                pdf.rect(pdf.layout.margin_l, img_y, pdf.layout.live_w, img_h, style="F")
        else:
            pdf.set_fill_color(*fallback_rgb)
            pdf.rect(pdf.layout.margin_l, img_y, pdf.layout.live_w, img_h, style="F")

        pdf.set_draw_color(*accent)
        pdf.set_line_width(1.0)
        pdf.rect(pdf.layout.margin_l, img_y, pdf.layout.live_w, img_h)


def voice_rules_page(pdf: BrandPDF, voice: dict, accent: tuple[int, int, int]):
    content_page_base(pdf, "Voice rules", accent)
    L = pdf.layout
    x = L.x(0)

    principles = [x for x in (voice.get("principles", []) or []) if (x or "").strip()]
    do_say = [x for x in (voice.get("do_say", []) or []) if (x or "").strip()]
    do_not = [x for x in (voice.get("do_not_say", []) or []) if (x or "").strip()]

    pdf.set_text_color(*pdf.c_text)
    pdf.f_body("B", 12)
    pdf.set_xy(x, pdf.get_y() + inch(0.12))
    pdf.cell(0, inch(0.22), safe_text("Principles", pdf._latin_only), ln=1)
    pdf.ln(inch(0.06))
    bullet_list(pdf, principles, x, L.w(6), inch(0.22), max_items=7)

    pdf.ln(inch(0.12))
    split_two_col(pdf, "Do say", do_say, "Do not say", do_not)


def voice_example_page(pdf: BrandPDF, before: str, after: str, image_path: Optional[str], accent: tuple[int, int, int], fallback_rgb: tuple[int, int, int]):
    content_page_base(pdf, "Voice example", accent)
    L = pdf.layout
    left_x = L.x(0)
    left_w = L.w(6)
    right_x = L.x(7)
    right_w = L.w(5)
    top = pdf.get_y()

    pdf.set_xy(left_x, top + inch(0.10))
    pdf.f_body("B", 12)
    pdf.set_text_color(*pdf.c_text)
    pdf.cell(left_w, inch(0.22), safe_text("Before", pdf._latin_only), ln=1)
    pdf.ln(inch(0.06))
    bullet_list(pdf, [before], left_x, left_w, inch(0.22), max_items=2)

    pdf.ln(inch(0.18))
    pdf.set_x(left_x)
    pdf.f_body("B", 12)
    pdf.cell(left_w, inch(0.22), safe_text("After", pdf._latin_only), ln=1)
    pdf.ln(inch(0.06))
    bullet_list(pdf, [after], left_x, left_w, inch(0.22), max_items=2)

    img_y = top + inch(0.10)
    img_h = pdf.h - img_y - L.margin_b - inch(0.20)
    if image_path:
        try:
            pdf.image(image_path, x=right_x, y=img_y, w=right_w, h=img_h, keep_aspect_ratio=False)
        except Exception:
            pdf.set_fill_color(*fallback_rgb)
            pdf.rect(right_x, img_y, right_w, img_h, style="F")
    else:
        pdf.set_fill_color(*fallback_rgb)
        pdf.rect(right_x, img_y, right_w, img_h, style="F")

    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.0)
    pdf.rect(right_x, img_y, right_w, img_h)


def visual_direction_pages(pdf: BrandPDF, vis: dict, mood_paths: list[str], accent: tuple[int, int, int], fallback_rgb: tuple[int, int, int]):
    content_page_base(pdf, "Moodboard", accent)
    L = pdf.layout
    grid_top = pdf.get_y() + inch(0.10)
    gap = inch(0.12)

    cols = 3
    rows = 2
    cell_w = (L.live_w - gap * (cols - 1)) / cols
    cell_h = (pdf.h - grid_top - L.margin_b - gap * (rows - 1)) / rows

    idx = 0
    for r in range(rows):
        for c in range(cols):
            x = L.margin_l + c * (cell_w + gap)
            y = grid_top + r * (cell_h + gap)
            img = mood_paths[idx] if idx < len(mood_paths) else None
            idx += 1

            if img:
                try:
                    pdf.image(img, x=x, y=y, w=cell_w, h=cell_h, keep_aspect_ratio=False)
                except Exception:
                    pdf.set_fill_color(*fallback_rgb)
                    pdf.rect(x, y, cell_w, cell_h, style="F")
            else:
                pdf.set_fill_color(*fallback_rgb)
                pdf.rect(x, y, cell_w, cell_h, style="F")

            pdf.set_draw_color(*accent)
            pdf.set_line_width(1.0)
            pdf.rect(x, y, cell_w, cell_h)

    content_page_base(pdf, "Visual direction", accent)
    intent = (vis.get("intent", "") or "").strip()
    feels = [x for x in (vis.get("feels_like", []) or []) if (x or "").strip()]
    never = [x for x in (vis.get("never_feels_like", []) or []) if (x or "").strip()]
    hard_bans = [x for x in (vis.get("hard_bans", []) or []) if (x or "").strip()]
    tests = [x for x in (vis.get("acceptance_test", []) or []) if (x or "").strip()]

    x = L.x(0)
    w = L.w(7)
    if intent:
        body_paras(pdf, intent, x, w)
        pdf.ln(inch(0.10))

    split_two_col(pdf, "Feels like", feels[:9], "Never feels like", never[:9])

    pdf.ln(inch(0.18))
    split_two_col(pdf, "Hard bans", hard_bans[:9], "Acceptance test", tests[:9])


def color_palette_page(pdf: BrandPDF, colors: dict, accent: tuple[int, int, int]):
    content_page_base(pdf, "Color palette", accent)

    L = pdf.layout
    x = L.x(0)
    y = pdf.get_y() + inch(0.08)

    blocks = [
        ("Primary", colors.get("primary_hex", ""), colors.get("primary_reason", "")),
        ("Accent", colors.get("accent_hex", ""), colors.get("accent_reason", "")),
        ("Neutral", colors.get("neutral_hex", ""), colors.get("neutral_reason", "")),
        ("Background", colors.get("background_hex", ""), colors.get("background_reason", "")),
    ]

    sw = inch(1.10)
    sh = inch(0.48)
    gap_y = inch(0.70)

    pdf.set_xy(x, y)
    for name, hx, reason in blocks:
        rgb = _hex_to_rgb(hx, (220, 220, 220))
        pdf.set_fill_color(*rgb)
        pdf.rect(x, pdf.get_y(), sw, sh, style="F")

        pdf.set_text_color(*pdf.c_text)
        pdf.f_body("B", 12)
        pdf.set_xy(x + sw + inch(0.20), pdf.get_y() - inch(0.02))
        pdf.cell(0, inch(0.22), safe_text(f"{name}  {_rgb_to_hex(rgb)}", pdf._latin_only), ln=1)

        pdf.set_text_color(70, 75, 85)
        pdf.f_body("R", 10)
        pdf.set_x(x + sw + inch(0.20))
        safe_multicell(pdf, L.w(10) - sw, inch(0.20), safe_text((reason or "").strip(), pdf._latin_only))

        pdf.set_y(pdf.get_y() + gap_y)


def typography_page(pdf: BrandPDF, typography: dict, accent: tuple[int, int, int]):
    content_page_base(pdf, "Typography", accent)

    L = pdf.layout
    x = L.x(0)
    w = L.w(12)

    primary = (typography.get("primary_font", "") or "").strip() or "Primary"
    secondary = (typography.get("secondary_font", "") or "").strip() or "Secondary"
    pu = (typography.get("primary_use", "") or "").strip()
    su = (typography.get("secondary_use", "") or "").strip()
    rat = (typography.get("rationale", "") or "").strip()

    pdf.set_xy(x, pdf.get_y() + inch(0.10))
    pdf.f_body("B", 14)
    pdf.set_text_color(*pdf.c_text)
    pdf.cell(0, inch(0.26), safe_text(f"Primary: {primary}", pdf._latin_only), ln=1)

    pdf.f_body("R", 11)
    pdf.set_text_color(55, 60, 70)
    safe_multicell(pdf, w, inch(0.22), safe_text(pu or "Use for headlines, section titles, and key moments.", pdf._latin_only))
    pdf.ln(inch(0.18))

    pdf.f_body("B", 14)
    pdf.set_text_color(*pdf.c_text)
    pdf.cell(0, inch(0.26), safe_text(f"Secondary: {secondary}", pdf._latin_only), ln=1)

    pdf.f_body("R", 11)
    pdf.set_text_color(55, 60, 70)
    safe_multicell(pdf, w, inch(0.22), safe_text(su or "Use for body text, captions, and longer reading.", pdf._latin_only))

    if rat:
        pdf.ln(inch(0.22))
        pdf.f_body("R", 11)
        pdf.set_text_color(55, 60, 70)
        safe_multicell(pdf, w, inch(0.22), safe_text(rat, pdf._latin_only))

    pdf.ln(inch(0.38))
    pdf.f_head("B", 26)
    pdf.set_text_color(*pdf.c_text)
    pdf.cell(0, inch(0.36), safe_text("Headline example", pdf._latin_only), ln=1)
    pdf.ln(inch(0.06))

    pdf.f_body("R", 12)
    pdf.set_text_color(35, 40, 50)
    safe_multicell(pdf, L.w(7), inch(0.24), safe_text("Body text example. Short sentences. Clear meaning. No fluff.", pdf._latin_only))


def executive_summary_page(pdf: BrandPDF, decisions: list[str], accent: tuple[int, int, int]):
    content_page_base(pdf, "Executive summary", accent)
    L = pdf.layout
    x = L.x(0)
    w = L.w(8)
    bullet_list(pdf, [d for d in decisions if (d or "").strip()], x, w, inch(0.22), max_items=12)


def positioning_page(pdf: BrandPDF, pos: dict, accent: tuple[int, int, int]):
    content_page_base(pdf, "Positioning", accent)
    L = pdf.layout
    x = L.x(0)
    w = L.w(7)

    statement = (pos.get("positioning_statement", "") or "").strip()
    body_paras(pdf, statement, x, w)
    pdf.ln(inch(0.08))

    left = []
    cat = (pos.get("category", "") or "").strip()
    if cat:
        left.append(f"Category: {cat}")
    right = []
    anti = (pos.get("anti_position", "") or "").strip()
    if anti:
        right.append(anti)

    split_two_col(pdf, "What we are", left or ["Clear category ownership."], "What we are not", right or ["Vague, generic, and polite."])


def audience_page(pdf: BrandPDF, aud: dict, accent: tuple[int, int, int]):
    content_page_base(pdf, "Audience", accent)
    L = pdf.layout
    x = L.x(0)
    w = L.w(8)
    items = [
        (aud.get("core_customer", "") or "").strip(),
        (aud.get("core_tension", "") or "").strip(),
        (aud.get("primary_objection", "") or "").strip(),
        (aud.get("trust_trigger", "") or "").strip(),
    ]
    bullet_list(pdf, [i for i in items if i], x, w, inch(0.22), max_items=12)


def guardrails_page(pdf: BrandPDF, guard: dict, accent: tuple[int, int, int]):
    content_page_base(pdf, "Guardrails", accent)
    L = pdf.layout
    x = L.x(0)
    w = L.w(8)
    bullet_list(pdf, [x for x in (guard.get("failure_modes", []) or []) if (x or "").strip()], x, w, inch(0.22), max_items=14)


def usage_page(pdf: BrandPDF, usage: dict, accent: tuple[int, int, int]):
    content_page_base(pdf, "How to use this", accent)
    L = pdf.layout
    x = L.x(0)
    w = L.w(9)
    bullet_list(pdf, [x for x in (usage.get("how_to_use", []) or []) if (x or "").strip()], x, w, inch(0.22), max_items=16)


def back_cover(pdf: BrandPDF, brand: str, bg_rgb: tuple[int, int, int]):
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
    pdf.cell(0, inch(0.22), safe_text("Brand system", pdf._latin_only))
    pdf._suppress_footer = False


def render_pdf(schema: dict, answers: dict, include_images: bool, unsplash_key: str) -> bytes:
    meta = schema.get("meta", {}) or {}
    colors = schema.get("colors", {}) or {}
    hero = schema.get("hero", {}) or {}
    typo = schema.get("typography", {}) or {}

    brand = (meta.get("brand_name", "") or "").strip() or (answers.get("brand_name", "") or "").strip() or "Brand"

    primary = _hex_to_rgb(colors.get("primary_hex", ""), (18, 22, 30))
    accent = _hex_to_rgb(colors.get("accent_hex", ""), (28, 125, 255))
    background = _hex_to_rgb(colors.get("background_hex", ""), (245, 246, 248))

    pdf = BrandPDF(orientation="L", unit="mm", format="letter")
    pdf.set_auto_page_break(auto=True, margin=pdf.layout.margin_b)
    pdf.set_brand_fonts()
    pdf.brand_name = brand

    photos: list[str] = []
    if include_images:
        if not unsplash_key:
            raise RuntimeError("Images enabled but missing Unsplash key.")
        if requests is None:
            raise RuntimeError("Images enabled but requests is missing.")
        queries = build_image_queries(answers, schema)
        photos = unsplash_random_images(unsplash_key, queries, count=12, orientation="landscape")

    # Fixed mapping so sections do not reuse the same opener image
    def p(i: int) -> Optional[str]:
        return photos[i] if i < len(photos) else None

    hero_photo = p(0)
    intro_photo = p(1)

    opener_exec = p(2)
    opener_pos = p(3)
    opener_aud = p(4)
    opener_msg = p(5)
    opener_voice = p(6)
    opener_vis = p(7)
    opener_guard = p(8)
    opener_use = p(9)
    voice_example_img = p(10)
    mood = photos[6:12] if len(photos) >= 12 else photos[:6]

    deck_sub = (hero.get("deck_subtitle", "") or "").strip() or "Brand system. A decision spec for consistency."

    cover_page(pdf, brand=brand, subtitle=deck_sub, photo_path=hero_photo, fallback_rgb=primary)

    intro_page(pdf, brand=brand, date_utc=utc_date_str(), image_path=intro_photo, accent=accent, bg_rgb=background)

    contents_page(pdf, accent=accent)

    section_photo_opener(pdf, "Executive summary", "The decisions that keep the brand consistent.", opener_exec, accent, primary)
    decisions = ((schema.get("executive_summary", {}) or {}).get("decisions", []) or [])
    executive_summary_page(pdf, decisions, accent)

    section_photo_opener(pdf, "Positioning", "Where you stand, and what you refuse to be.", opener_pos, accent, primary)
    positioning_page(pdf, schema.get("positioning", {}) or {}, accent)

    section_photo_opener(pdf, "Audience", "One real person. One real tension.", opener_aud, accent, primary)
    audience_page(pdf, schema.get("audience", {}) or {}, accent)

    section_photo_opener(pdf, "Messaging", "Repeatable messages, backed by proof.", opener_msg, accent, primary)
    messaging_page(pdf, schema.get("messaging", {}) or {}, opener_msg, accent, background)

    section_photo_opener(pdf, "Voice", "Rules that stop bad copy before it exists.", opener_voice, accent, primary)
    voice = schema.get("voice", {}) or {}
    voice_rules_page(pdf, voice, accent)
    ex = voice.get("examples", {}) or {}
    before = (ex.get("before", "") or "").strip()
    after = (ex.get("after", "") or "").strip()
    if before and after:
        voice_example_page(pdf, before, after, voice_example_img, accent, background)

    section_photo_opener(pdf, "Visual direction", "Taste, constraints, and posture.", opener_vis, accent, primary)
    visual_direction_pages(pdf, schema.get("visual_direction", {}) or {}, mood, accent, background)

    color_palette_page(pdf, colors, accent)
    typography_page(pdf, typo, accent)

    section_photo_opener(pdf, "Guardrails", "How the brand gets ruined. Avoid these.", opener_guard, accent, primary)
    guardrails_page(pdf, schema.get("guardrails", {}) or {}, accent)

    section_photo_opener(pdf, "How to use this", "Open this when the team starts to drift.", opener_use, accent, primary)
    usage_page(pdf, schema.get("usage", {}) or {}, accent)

    back_cover(pdf, brand, primary)

    out = pdf.output(dest="S")
    pdf_bytes = bytes(out) if isinstance(out, (bytes, bytearray)) else str(out).encode("latin-1", "replace")

    for fp in photos:
        try:
            os.unlink(fp)
        except Exception:
            pass

    return pdf_bytes


# =========================
# UI helpers
# =========================
def render_progress(step_index: int, steps: list[dict]):
    total = len([s for s in steps if s["type"] == "question"])
    seen = 0
    for i in range(step_index + 1):
        if steps[i]["type"] == "question":
            seen += 1
    current_q = max(1, seen) if total else 0
    st.progress(min(max((step_index + 1) / max(len(steps), 1), 0.0), 1.0))
    st.caption(f"Question {current_q} of {total}")


def render_question(q: Question):
    key = f"ans_{q.key}"
    current = st.session_state.answers.get(q.key)

    if q.qtype == "text":
        val = st.text_input(q.title, value=current or "", placeholder=q.placeholder, key=key)
        st.session_state.answers[q.key] = (val or "").strip()

    elif q.qtype == "textarea":
        val = st.text_area(q.title, value=current or "", placeholder=q.placeholder, height=160, key=key)
        st.session_state.answers[q.key] = (val or "").strip()

    elif q.qtype == "cards":
        opts = q.options or []
        idx = opts.index(current) if current in opts else 0
        val = st.radio(q.title, options=opts, index=idx, key=key)
        st.session_state.answers[q.key] = val
        if val == "Other":
            other = st.text_input("Other", value=st.session_state.answers.get(q.key + "_other", ""), key=key + "_other")
            st.session_state.answers[q.key + "_other"] = (other or "").strip()

    elif q.qtype == "checks":
        opts = q.options or []
        cur_list = current if isinstance(current, list) else []
        chosen = []
        st.write(q.title)
        for opt in opts:
            if st.checkbox(opt, value=(opt in cur_list), key=f"{key}_{opt}"):
                chosen.append(opt)
        st.session_state.answers[q.key] = chosen

    else:
        st.session_state.answers[q.key] = current


def validate_step(step: dict) -> tuple[bool, str]:
    if step["type"] != "question":
        return True, ""
    q = get_question(step["qid"])
    val = st.session_state.answers.get(q.key)

    if not q.required:
        return True, ""

    if q.key == "brand_name":
        if not (val or "").strip():
            return False, "Brand name is required."
        return True, ""

    if q.qtype == "checks":
        if not isinstance(val, list) or len(val) == 0:
            return False, "Select at least one option."
        return True, ""

    if not val or (isinstance(val, str) and not val.strip()):
        return False, "Write a short answer to continue."
    return True, ""


# =========================
# Views
# =========================
def landing_view():
    st.markdown('<div class="eyebrow">Brand system generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle">Build a brand that stays consistent when you are not in the room</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="heroSub">A guided brand interview that turns strategy, voice, and constraints into a landscape PDF deck.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="pills">
          <div class="pill">Landscape deck</div>
          <div class="pill">Decision spec</div>
          <div class="pill">Rules and constraints</div>
          <div class="pill">Images optional</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2], gap="large")
    with col1:
        st.subheader("Why this matters")
        st.write("Most brands fail because nothing is defined.")
        st.write("A brand system is a decision spec.")
        st.write("With a system, teams decide faster and stay consistent without debating taste.")

    with col2:
        st.subheader("What you get")
        st.write("Positioning and category clarity")
        st.write("Messaging with proof points")
        st.write("Voice rules with example")
        st.write("Visual constraints with acceptance tests")
        st.caption("Includes 5 generations per purchase concept.")

    with st.expander("Advanced settings", expanded=False):
        st.session_state.provider = st.selectbox(
            "Provider",
            options=["gemini", "openai"],
            index=0 if st.session_state.provider == "gemini" else 1,
        )

        if st.session_state.provider == "gemini":
            st.session_state.gemini_key = st.text_input("Gemini API key", type="password", value=st.session_state.gemini_key)
        else:
            st.session_state.openai_key = st.text_input("OpenAI API key", type="password", value=st.session_state.openai_key)
            st.session_state.openai_model = st.text_input("OpenAI model", value=st.session_state.openai_model)

        st.session_state.include_images = st.checkbox("Include images (optional)", value=st.session_state.include_images)
        if st.session_state.include_images:
            st.session_state.unsplash_key = st.text_input("Unsplash access key", type="password", value=st.session_state.unsplash_key)

    st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
    if st.button("Start brand interview"):
        st.session_state.step_index = 0
        go("wizard")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.provider == "gemini" and not st.session_state.gemini_key:
        st.info("Set GEMINI_API_KEY in secrets.toml or enter it in Advanced settings.")
    if st.session_state.provider == "openai" and not st.session_state.openai_key:
        st.info("Set OPENAI_API_KEY in secrets.toml or enter it in Advanced settings.")
    if st.session_state.include_images and not st.session_state.unsplash_key:
        st.info("Images are enabled but Unsplash key is missing.")


def wizard_view():
    steps = wizard_steps()
    st.session_state.step_index = max(0, min(st.session_state.step_index, len(steps) - 1))
    step = steps[st.session_state.step_index]

    render_progress(st.session_state.step_index, steps)
    st.write("")

    if step["type"] == "section":
        sec = get_section(step["section_id"])
        st.subheader(sec.title)
        st.caption(sec.line)
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
        label = "Continue" if step["type"] == "section" else "Next"
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
    st.markdown('<div class="heroTitle" style="font-size:34px;">Ready to generate the deck</div>', unsafe_allow_html=True)

    remaining = max(st.session_state.gen_max - st.session_state.gen_used, 0)
    st.caption(f"Generations remaining: {remaining} of {st.session_state.gen_max}")

    with st.expander("Review your inputs", expanded=False):
        for q in QUESTIONS:
            ans = st.session_state.answers.get(q.key)
            if ans is None or ans == "" or ans == []:
                continue
            st.markdown(f"**{q.title}**")
            if isinstance(ans, list):
                st.write(", ".join(ans))
            else:
                st.write(ans)
            st.markdown("")

    with st.expander("Generation settings", expanded=False):
        st.write(f"Provider: {st.session_state.provider}")
        st.write(f"Images: {'on' if st.session_state.include_images else 'off'}")
        if st.session_state.provider == "openai":
            st.write(f"OpenAI model: {st.session_state.openai_model}")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back to interview"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        if st.button("Generate deck", disabled=(remaining <= 0)):
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)


def generate_view():
    st.markdown('<div class="eyebrow">Generating</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Building your deck</div>', unsafe_allow_html=True)
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

    provider = st.session_state.provider
    gemini_key = (st.session_state.gemini_key or "").strip()
    openai_key = (st.session_state.openai_key or "").strip()
    openai_model = (st.session_state.openai_model or "").strip() or "gpt-4.1-mini"
    include_images = bool(st.session_state.include_images)
    unsplash_key = (st.session_state.unsplash_key or "").strip()

    if provider == "gemini" and not gemini_key:
        st.error("Missing Gemini API key.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("landing")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if provider == "openai" and not openai_key:
        st.error("Missing OpenAI API key.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("landing")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if include_images:
        if not unsplash_key:
            st.error("Images are enabled but Unsplash key is missing.")
            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Back"):
                go("landing")
            st.markdown("</div>", unsafe_allow_html=True)
            return
        if requests is None:
            st.error("Images are enabled but requests is missing.")
            st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
            if st.button("Back"):
                go("landing")
            st.markdown("</div>", unsafe_allow_html=True)
            return

    prompt = build_prompt(st.session_state.answers, version_str=str(st.session_state.gen_used + 1))
    stage = st.empty()

    try:
        with st.spinner("Working..."):
            stage.write("Defining strategy")
            time.sleep(0.05)
            schema, model_used = generate_schema(
                prompt,
                provider=provider,
                gemini_key=gemini_key,
                openai_key=openai_key,
                openai_model=openai_model,
                timeout_s=40,
            )

            stage.write("Building PDF")
            time.sleep(0.05)
            pdf_bytes = render_pdf(schema, st.session_state.answers, include_images=include_images, unsplash_key=unsplash_key)

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
    st.markdown('<div class="heroTitle" style="font-size:34px;">Download your deck</div>', unsafe_allow_html=True)

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
    filename = f"{brand}_Brand_Bible_v{st.session_state.gen_used}.pdf"

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
        if st.button("Start new brand"):
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
