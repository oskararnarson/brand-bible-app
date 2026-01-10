import json
import os
import re
import struct
import tempfile
import time
import zlib
import random
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import concurrent.futures
import streamlit as st
import google.generativeai as genai
from fpdf import FPDF

try:
    import requests
except Exception:
    requests = None


st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")


from pathlib import Path

try:
    from PIL import Image
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
        "api_key": "",
        "gen_used": 0,
        "gen_max": 5,
        "last_json": None,
        "pdf_bytes": None,
        "model_used": "",
        "error": "",
        "plate_paths": {},
        "asset_paths": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.api_key:
        st.session_state.api_key = (st.secrets.get("GEMINI_API_KEY", "") or "").strip()


def go(view: str):
    st.session_state.view = view
    st.rerun()


def reset_app(keep_api_key: bool = True):
    api_key = st.session_state.api_key
    plate_paths = st.session_state.plate_paths
    asset_paths = st.session_state.asset_paths
    st.session_state.clear()
    ss_init()
    st.session_state.plate_paths = plate_paths
    st.session_state.asset_paths = asset_paths
    if keep_api_key:
        st.session_state.api_key = api_key


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

.block-container { max-width: 1180px; padding-top: 7rem !important; padding-bottom: 3.2rem; }

:root{
  --bg:#0b0d11;
  --fg:rgba(235,240,255,0.92);
  --muted:rgba(235,240,255,0.70);
  --muted2:rgba(235,240,255,0.55);
  --card:rgba(255,255,255,0.06);
  --card2:rgba(255,255,255,0.04);
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

@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.fadeIn { animation: fadeIn 220ms ease-out; }
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
             options=["Gallery", "High end hotel", "Workshop", "Library", "Clinic", "Studio", "Other"]),
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
# Gemini
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
        '  "visual_direction": { "intent": "", "feels_like": [""], "never_feels_like": [""], "imagery_keywords": [""] },\n'
        '  "guardrails": { "failure_modes": [""] },\n'
        '  "usage": { "how_to_use": [""] }\n'
        "}\n"
    )

    font_pool = [
        "Inter", "Manrope", "Plus Jakarta Sans", "Space Grotesk", "DM Sans",
        "IBM Plex Sans", "Work Sans", "Sora", "Urbanist", "Outfit",
        "Montserrat", "Raleway", "Source Sans 3", "Public Sans", "Rubik",
        "Merriweather", "Lora", "Fraunces", "Cormorant Garamond", "Libre Baskerville"
    ]

    prompt = (
        "You are a senior brand strategist and design director.\n"
        "You decide. You do not describe.\n"
        "Be opinionated, concise, and practical.\n"
        "Avoid cliches and startup hype.\n"
        "Return ONLY valid JSON that matches the schema exactly.\n"
        "No markdown. No commentary. No extra keys.\n\n"
        "COLOR RULES\n"
        "Return real hex colors.\n"
        "Each color must include a one sentence reason that connects to the brand.\n"
        "No generic reasons.\n\n"
        "TYPOGRAPHY RULES\n"
        "Pick fonts that fit the brand.\n"
        "Do not always pick Inter.\n"
        "Choose from this pool when possible:\n"
        f"{', '.join(font_pool)}\n"
        "Explain the choice briefly in typography.rationale.\n"
        "Define primary_use and secondary_use.\n\n"
        "HERO RULES\n"
        "hero.headline is 6 to 12 words.\n"
        "hero.subhead is 1 sentence.\n"
        "hero.deck_subtitle must be short and premium.\n\n"
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


def generate_schema(prompt: str, timeout_s: int = 35) -> tuple[dict, str]:
    models_to_try = choose_models_to_try()
    last_err: Exception | None = None
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(model.generate_content, prompt)
                resp = fut.result(timeout=timeout_s)
            raw = (getattr(resp, "text", "") or "").strip()
            data = json.loads(extract_json_object(raw))
            # Keep unicode intact. We will only sanitize later if we are forced into core fonts.
            data = data

            required = ["meta", "colors", "typography", "hero", "executive_summary", "positioning",
                        "audience", "messaging", "voice", "visual_direction", "guardrails", "usage"]
            for k in required:
                if k not in data:
                    raise ValueError("JSON missing required keys.")
            return data, model_name
        except concurrent.futures.TimeoutError:
            last_err = RuntimeError(f"Timeout after {timeout_s} seconds.")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Generation failed: {last_err}")


# =========================
# Assets: curated photos
# =========================
PHOTO_BASE = {
    "calm": [
        "minimal workspace natural light",
        "museum interior minimal",
        "concrete architecture detail",
        "stone texture close up",
        "quiet library interior",
        "soft shadow wall texture",
        "architectural corridor symmetry",
        "abstract light gradient texture",
    ],
    "bold": [
        "brutalist architecture dramatic light",
        "high contrast portrait low key",
        "night city street neon reflection",
        "steel structure detail",
        "stark shadow silhouette",
        "industrial corridor moody",
        "architectural facade high contrast",
        "dark abstract texture",
    ],
    "precision": [
        "grid pattern macro",
        "lab interior clean",
        "white studio product close up",
        "industrial detail minimal",
        "typography poster close up",
        "architectural lines symmetry",
        "blueprint technical drawing",
        "precision instrument close up",
    ],
    "warm": [
        "warm sunlight texture",
        "hands craft detail",
        "cozy modern interior minimal",
        "golden hour portrait",
        "wood texture close up",
        "warm shadow wall",
        "ceramic material detail",
        "soft warm editorial",
    ],
}


def pick_photo_theme(answers: dict, schema: dict) -> str:
    energy = (answers.get("voice_energy", "") or "").strip()
    impression = (answers.get("first_impression", "") or "").strip()
    animal = (answers.get("animal", "") or "").strip()
    intent = ((schema.get("visual_direction", {}) or {}).get("intent", "") or "").lower()

    if "clinical" in energy.lower() or "precision" in intent or impression == "Controlled":
        return "precision"
    if energy in ["Bold", "Sharp"] or animal in ["Panther", "Falcon", "Hawk"] or impression == "Powerful":
        return "bold"
    if energy == "Warm" or "warm" in intent or impression in ["Safe", "Curious"]:
        return "warm"
    return "calm"


def _download_to_temp(url: str, key: str) -> str | None:
    if key in st.session_state.asset_paths and os.path.exists(st.session_state.asset_paths[key]):
        return st.session_state.asset_paths[key]

    if requests is None:
        return None

    try:
        headers = {"User-Agent": "BrandBibleGenerator/1.0"}
        r = requests.get(url, timeout=18, headers=headers, allow_redirects=True)
        if r.status_code != 200 or not r.content:
            return None
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        f.write(r.content)
        f.flush()
        f.close()
        st.session_state.asset_paths[key] = f.name
        return f.name
    except Exception:
        return None


def _file_sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 128), b""):
            h.update(chunk)
    return h.hexdigest()


def build_image_queries(theme: str, answers: dict, schema: dict) -> list[str]:
    base = list(PHOTO_BASE.get(theme, PHOTO_BASE["calm"]))

    vis = schema.get("visual_direction", {}) or {}
    kws = vis.get("imagery_keywords", []) or []
    kws = [str(x).strip() for x in kws if str(x).strip()]

    place = (answers.get("brand_place", "") or "").strip()
    avoid = answers.get("avoid_vibes", []) or []
    avoid = [str(x).strip() for x in avoid if str(x).strip()]

    if place:
        base.append(f"{place.lower()} interior minimal")
        base.append(f"{place.lower()} material detail")
    for k in kws[:10]:
        base.append(k)

    for a in avoid:
        if a == "Lifestyle fluff":
            base.append("no lifestyle staged interior")
        if a == "Luxury cliche":
            base.append("modern understated not luxury")
        if a == "Startup hype":
            base.append("editorial minimal not startup")

    out: list[str] = []
    seen = set()
    for q in base:
        qn = " ".join(q.split()).strip().lower()
        if not qn or qn in seen:
            continue
        seen.add(qn)
        out.append(qn)

    return out


def get_curated_images(theme: str, answers: dict, schema: dict, count: int, seed: int) -> list[str]:
    queries = build_image_queries(theme, answers, schema)
    rng = random.Random(seed)
    rng.shuffle(queries)

    paths: list[str] = []
    used_hashes: set[str] = set()

    tries = 0
    while len(paths) < count and tries < max(30, count * 8):
        tries += 1
        if not queries:
            break
        qraw = queries[tries % len(queries)]
        q = qraw.replace(" ", ",")
        sig = rng.randint(1, 2_000_000_000)
        url = f"https://source.unsplash.com/2400x1600/?{q}&sig={sig}"
        key = f"unsplash_run_{seed}_{sig}_{abs(hash(url))}"
        p = _download_to_temp(url, key=key)
        if not p:
            continue
        try:
            if os.path.getsize(p) < 40_000:
                continue
            sh = _file_sha1(p)
            if sh in used_hashes:
                continue
            used_hashes.add(sh)
            paths.append(p)
        except Exception:
            continue

    return paths


# =========================
# Plates
# =========================
def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    crc_bytes = struct.pack(">I", crc & 0xFFFFFFFF)
    return length + chunk_type + data + crc_bytes


def _make_plate_png_bytes(w: int, h: int, c1: tuple[int, int, int], c2: tuple[int, int, int], bg: tuple[int, int, int]) -> bytes:
    seed = (c1[0] << 16) + (c1[1] << 8) + c1[2] + (c2[0] << 8) + c2[1] + (bg[2] << 4)
    x = seed & 0xFFFFFFFF

    def rnd() -> int:
        nonlocal x
        x = (1664525 * x + 1013904223) & 0xFFFFFFFF
        return x

    scanlines = bytearray()
    for y in range(h):
        scanlines.append(0)
        t = y / max(h - 1, 1)
        for px in range(w):
            u = px / max(w - 1, 1)
            k = (u * 0.62 + t * 0.38)
            r = int(c1[0] * (1 - k) + c2[0] * k)
            g = int(c1[1] * (1 - k) + c2[1] * k)
            b = int(c1[2] * (1 - k) + c2[2] * k)

            n = (rnd() >> 24) - 128
            n = int(n * 0.10)

            dx = (u - 0.5)
            dy = (t - 0.5)
            v = 1.0 - min(0.55, (dx * dx + dy * dy) * 1.25)

            r = int((r + bg[0]) * 0.5 * v + r * 0.5)
            g = int((g + bg[1]) * 0.5 * v + g * 0.5)
            b = int((b + bg[2]) * 0.5 * v + b * 0.5)

            r = max(0, min(255, r + n))
            g = max(0, min(255, g + n))
            b = max(0, min(255, b + n))

            scanlines.extend((r, g, b))

    raw = bytes(scanlines)
    compressed = zlib.compress(raw, level=7)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return signature + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", compressed) + _png_chunk(b"IEND", b"")


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


def _write_temp_png(png_bytes: bytes, key: str) -> str:
    if key in st.session_state.plate_paths and os.path.exists(st.session_state.plate_paths[key]):
        return st.session_state.plate_paths[key]
    f = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{key}.png")
    f.write(png_bytes)
    f.flush()
    f.close()
    st.session_state.plate_paths[key] = f.name
    return f.name



# =========================
# Helper function
# =========================

def safe_multicell(pdf: FPDF, w: float, h: float, txt: str):
    """
    Guard against zero or negative widths.
    """
    if w is None or w <= 2:
        raise RuntimeError(f"Invalid text width: {w}")
    pdf.multi_cell(w, h, txt)


# =========================
# Layout system (US Letter landscape)
# =========================
IN_TO_MM = 25.4

def inch(x: float) -> float:
    return x * IN_TO_MM

class Layout:
    """
    Premium minimalist studio deck layout contract.
    All positioning should be derived from this object.
    """
    def __init__(self):
        # US Letter landscape in mm
        self.page_w = inch(11.0)
        self.page_h = inch(8.5)

        # Margins in inches, converted to mm
        self.margin_l = inch(0.90)
        self.margin_r = inch(0.90)
        self.margin_t = inch(0.75)
        self.margin_b = inch(0.75)

        # Grid
        self.cols = 12
        self.gutter = inch(0.20)

        # Baseline rhythm
        self.base = inch(0.15)

        # Derived widths
        self.live_w = self.page_w - self.margin_l - self.margin_r
        self.live_h = self.page_h - self.margin_t - self.margin_b
        self.col_w = (self.live_w - (self.cols - 1) * self.gutter) / self.cols

    def x(self, col_index: int) -> float:
        # 0-based column index
        return self.margin_l + col_index * (self.col_w + self.gutter)

    def w(self, col_span: int) -> float:
        # number of columns to span
        if col_span <= 0:
            return 0.0
        return col_span * self.col_w + (col_span - 1) * self.gutter

    def snap_y(self, y: float) -> float:
        # snap to baseline rhythm
        if self.base <= 0:
            return y
        return round(y / self.base) * self.base

# =========================
# Fonts (embedded TTF)
# =========================
FONT_DIR = Path("assets") / "fonts"

class FontPack:
    def __init__(self):
        self.loaded = False
        self.head = "Head"
        self.body = "Body"

def register_fonts(pdf: FPDF) -> FontPack:
    pack = FontPack()
    try:
        head_b = FONT_DIR / "Sora-Bold.ttf"
        head_sb = FONT_DIR / "Sora-SemiBold.ttf"

        body_r = FONT_DIR / "Inter-Regular.ttf"
        body_m = FONT_DIR / "Inter-Medium.ttf"
        body_sb = FONT_DIR / "Inter-SemiBold.ttf"

        if not (head_b.exists() and head_sb.exists() and body_r.exists() and body_m.exists() and body_sb.exists()):
            return pack

        # Head
        pdf.add_font(pack.head, "", str(head_sb), uni=True)
        pdf.add_font(pack.head, "B", str(head_b), uni=True)

        # Body regular and bold
        pdf.add_font(pack.body, "", str(body_r), uni=True)
        pdf.add_font(pack.body, "B", str(body_sb), uni=True)

        # Body medium as a separate family name
        pdf.add_font("BodyM", "", str(body_m), uni=True)

        pack.loaded = True
        return pack
    except Exception:
        return pack


# =========================
# PDF
# =========================
IN_TO_MM = 25.4

def inch(x: float) -> float:
    return x * IN_TO_MM


class Layout:
    """
    US Letter landscape grid.
    All PDF positioning should be derived from this.
    """
    def __init__(self):
        self.page_w = inch(11.0)
        self.page_h = inch(8.5)

        # Margins tuned for an expensive studio deck
        self.margin_l = inch(0.85)
        self.margin_r = inch(0.85)
        self.margin_t = inch(0.70)
        self.margin_b = inch(0.70)

        # 12 column grid
        self.cols = 12
        self.gutter = inch(0.18)

        # Baseline rhythm
        self.base = inch(0.14)

        self.live_w = self.page_w - self.margin_l - self.margin_r
        self.live_h = self.page_h - self.margin_t - self.margin_b
        self.col_w = (self.live_w - (self.cols - 1) * self.gutter) / self.cols

    def x(self, col_index: int) -> float:
        return self.margin_l + col_index * (self.col_w + self.gutter)

    def w(self, col_span: int) -> float:
        if col_span <= 0:
            return 0.0
        return col_span * self.col_w + (col_span - 1) * self.gutter

    def y(self, rows: float) -> float:
        return self.margin_t + rows * self.base

    def snap(self, y: float) -> float:
        if self.base <= 0:
            return y
        return round(y / self.base) * self.base


def safe_text(s: Any, latin_only: bool) -> str:
    if s is None:
        return ""
    s = str(s)

    # Normalize the usual suspects
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2026", "...")
    s = s.replace("\u2022", "-")
    s = s.replace("\u00B7", "-")
    s = s.replace("\u25CF", "-")
    s = s.replace("\u25AA", "-")

    if latin_only:
        return s.encode("latin-1", "replace").decode("latin-1")
    return s


def safe_multicell(pdf: FPDF, w: float, h: float, txt: str):
    if w is None or w <= 10:
        raise RuntimeError(f"Invalid text width: {w}")
    pdf.multi_cell(w, h, txt)


def hex_to_rgb(h: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    hs = (h or "").strip()
    if hs.startswith("#"):
        hs = hs[1:]
    if len(hs) != 6:
        return fallback
    try:
        return (int(hs[0:2], 16), int(hs[2:4], 16), int(hs[4:6], 16))
    except Exception:
        return fallback


def luma(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_color_for_bg(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    return (255, 255, 255) if luma(bg) < 145 else (18, 22, 30)


# Fonts
from pathlib import Path
FONT_DIR = Path("assets") / "fontpack"

class FontPack:
    def __init__(self):
        self.loaded = False
        self.head = "Head"
        self.body = "Body"


def register_fonts(pdf: FPDF) -> FontPack:
    pack = FontPack()

    # You can swap these file names if you later change your font pack
    head_sb = FONT_DIR / "Sora-SemiBold.ttf"
    head_b = FONT_DIR / "Sora-Bold.ttf"
    body_r = FONT_DIR / "Inter-Regular.ttf"
    body_m = FONT_DIR / "Inter-Medium.ttf"
    body_sb = FONT_DIR / "Inter-SemiBold.ttf"

    if not (head_sb.exists() and head_b.exists() and body_r.exists() and body_m.exists() and body_sb.exists()):
        return pack

    try:
        # fpdf2 prefers uni=True
        pdf.add_font(pack.head, "", str(head_sb), uni=True)
        pdf.add_font(pack.head, "B", str(head_b), uni=True)

        pdf.add_font(pack.body, "", str(body_r), uni=True)
        pdf.add_font(pack.body, "B", str(body_sb), uni=True)
        pdf.add_font(pack.body, "I", str(body_r), uni=True)
        pdf.add_font(pack.body, "M", str(body_m), uni=True)

        pack.loaded = True
        return pack
    except TypeError:
        # Older fpdf signature
        try:
            pdf.add_font(pack.head, "", str(head_sb))
            pdf.add_font(pack.head, "B", str(head_b))

            pdf.add_font(pack.body, "", str(body_r))
            pdf.add_font(pack.body, "B", str(body_sb))
            pdf.add_font(pack.body, "I", str(body_r))
            pdf.add_font(pack.body, "M", str(body_m))

            pack.loaded = True
            return pack
        except Exception:
            return pack
    except Exception:
        return pack


class BrandPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.layout = Layout()
        self.fontpack = FontPack()
        self.brand_name = ""

        # Premium neutrals
        self.c_text = (18, 22, 30)
        self.c_muted = (98, 104, 114)
        self.c_rule = (224, 228, 234)

        self._latin_only = False

    def set_brand_fonts(self):
        self.fontpack = register_fonts(self)
        self._latin_only = (not self.fontpack.loaded)

    def f_head(self, style: str, size: float):
        if self.fontpack.loaded:
            self.set_font(self.fontpack.head, style, size)
        else:
            self.set_font("Helvetica", style, size)

    def f_body(self, style: str, size: float):
        if self.fontpack.loaded:
            fam = self.fontpack.body
            if style == "M":
                self.set_font(fam, "M", size)
            else:
                self.set_font(fam, style, size)
        else:
            self.set_font("Helvetica", style, size)

    def footer(self):
        L = self.layout
        self.set_y(-L.margin_b + inch(0.22))

        self.f_body("", 8)
        self.set_text_color(*self.c_muted)

        # Left: brand name
        self.set_x(L.margin_l)
        self.cell(0, inch(0.18), safe_text(self.brand_name, self._latin_only), align="L")

        # Right: page number
        self.set_x(L.page_w - L.margin_r - inch(0.35))
        self.cell(inch(0.35), inch(0.18), str(self.page_no()), align="R")


# Plates and imagery helpers already exist above in your file.
# We will use:
# full bleed photo when available
# otherwise we use generated plate png


def pdf_bg_solid(pdf: BrandPDF, rgb: tuple[int, int, int]):
    pdf.set_fill_color(*rgb)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")


def pdf_full_bleed_image(pdf: BrandPDF, img_path: str):
    pdf.image(img_path, x=0, y=0, w=pdf.w, h=pdf.h)


def pdf_rule(pdf: BrandPDF, x: float, y: float, w: float, accent: tuple[int, int, int]):
    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.2)
    pdf.line(x, y, x + w, y)


def component_header(pdf: BrandPDF, title: str, explain: str, accent: tuple[int, int, int]):
    L = pdf.layout
    x = L.margin_l
    y = L.margin_t

    pdf.set_text_color(*pdf.c_text)
    pdf.f_head("B", 22)
    pdf.set_xy(x, y)
    pdf.cell(0, inch(0.28), safe_text(title, pdf._latin_only))

    pdf_rule(pdf, x, y + inch(0.36), inch(1.10), accent)

    pdf.f_body("", 10.5)
    pdf.set_text_color(*pdf.c_muted)
    pdf.set_xy(x, y + inch(0.48))
    safe_multicell(pdf, L.w(7), L.base * 1.45, safe_text(explain, pdf._latin_only))

    pdf.set_y(y + inch(0.48) + inch(0.40))


def component_section_opener(pdf: BrandPDF, title: str, subtitle: str, bg_rgb: tuple[int, int, int], photo_path: str | None, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")

    if photo_path:
        try:
            pdf_full_bleed_image(pdf, photo_path)
        except Exception:
            pdf_bg_solid(pdf, bg_rgb)
    else:
        pdf_bg_solid(pdf, bg_rgb)

    # Overlay panel
    panel_x = inch(0.80)
    panel_y = inch(1.25)
    panel_w = inch(6.80)
    panel_h = inch(4.55)

    pdf.set_fill_color(10, 12, 16)
    pdf.rect(panel_x, panel_y, panel_w, panel_h, style="F")

    # Accent hairline
    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.2)
    pdf.line(panel_x + inch(0.35), panel_y + panel_h - inch(0.55), panel_x + inch(2.25), panel_y + panel_h - inch(0.55))

    # Text
    pdf.set_text_color(255, 255, 255)
    pdf.f_head("B", 44)
    pdf.set_xy(panel_x + inch(0.35), panel_y + inch(0.55))
    safe_multicell(pdf, panel_w - inch(0.70), inch(0.40), safe_text(title, pdf._latin_only))

    pdf.f_body("", 13)
    pdf.set_xy(panel_x + inch(0.35), panel_y + inch(2.10))
    safe_multicell(pdf, panel_w - inch(0.70), inch(0.26), safe_text(subtitle, pdf._latin_only))


def component_cover(pdf: BrandPDF, brand: str, deck_subtitle: str, photo_path: str | None, plate_path: str, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")

    if photo_path:
        try:
            pdf_full_bleed_image(pdf, photo_path)
        except Exception:
            pdf_full_bleed_image(pdf, plate_path)
    else:
        pdf_full_bleed_image(pdf, plate_path)

    # Dark panel
    panel_x = inch(0.80)
    panel_y = inch(1.25)
    panel_w = inch(7.20)
    panel_h = inch(4.70)

    pdf.set_fill_color(10, 12, 16)
    pdf.rect(panel_x, panel_y, panel_w, panel_h, style="F")

    # Monogram
    mono = (brand[:1] or "B").lower()
    pdf.set_text_color(255, 255, 255)
    pdf.f_head("B", 42)
    pdf.set_xy(panel_x + inch(0.35), panel_y + inch(0.50))
    pdf.cell(0, inch(0.50), safe_text(mono, pdf._latin_only))

    # Brand title
    pdf.f_head("B", 30)
    pdf.set_xy(panel_x + inch(0.35), panel_y + inch(2.25))
    safe_multicell(pdf, panel_w - inch(0.70), inch(0.36), safe_text(brand, pdf._latin_only))

    # Subtitle
    pdf.f_body("", 12)
    pdf.set_xy(panel_x + inch(0.35), panel_y + inch(3.65))
    safe_multicell(pdf, panel_w - inch(0.70), inch(0.24), safe_text(deck_subtitle, pdf._latin_only))

    # Accent rule
    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.2)
    pdf.line(panel_x + inch(0.35), panel_y + panel_h - inch(0.55), panel_x + inch(2.35), panel_y + panel_h - inch(0.55))


def component_intro(pdf: BrandPDF, brand: str, date_utc: str, image_path: str | None, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf_bg_solid(pdf, (255, 255, 255))

    L = pdf.layout
    left_x = L.margin_l
    top_y = L.margin_t

    component_header(
        pdf,
        "How to use this",
        "This is a decision system. Use it to keep voice, visuals, and messaging consistent across everyone who touches the brand.",
        accent
    )

    # Left copy block
    pdf.set_text_color(*pdf.c_text)
    pdf.f_body("", 11)

    text = (
        "Open this document when writing copy, selecting imagery, designing pages, or approving work.\n"
        "If a decision conflicts with this document, the document wins.\n\n"
        f"Generated for {brand} on {date_utc}."
    )
    pdf.set_x(left_x)
    safe_multicell(pdf, L.w(7), L.base * 1.55, safe_text(text, pdf._latin_only))

    # Right image
    img_x = L.x(8)
    img_y = top_y + inch(0.10)
    img_w = L.w(4)
    img_h = inch(4.70)

    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.0)
    pdf.rect(img_x, img_y, img_w, img_h)

    if image_path:
        try:
            pdf.image(image_path, x=img_x, y=img_y, w=img_w, h=img_h)
        except Exception:
            pass


def component_contents(pdf: BrandPDF, accent: tuple[int, int, int], items: list[tuple[str, str]]):
    pdf.add_page(orientation="L")
    pdf_bg_solid(pdf, (255, 255, 255))

    component_header(
        pdf,
        "Contents",
        "A fast map of the system. Each section is designed to be skimmed, then used during real decisions.",
        accent
    )

    L = pdf.layout
    x = L.margin_l
    y = pdf.get_y() + inch(0.10)

    pdf.f_body("M", 12)
    pdf.set_text_color(*pdf.c_text)

    for title, desc in items:
        pdf.set_xy(x, y)
        pdf.cell(L.w(4), inch(0.25), safe_text(title, pdf._latin_only))

        pdf.f_body("", 10.5)
        pdf.set_text_color(*pdf.c_muted)
        pdf.set_xy(L.x(4), y)
        safe_multicell(pdf, L.w(8), L.base * 1.35, safe_text(desc, pdf._latin_only))

        y += inch(0.45)

        pdf.f_body("M", 12)
        pdf.set_text_color(*pdf.c_text)


def component_body_page(pdf: BrandPDF, title: str, explain: str, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf_bg_solid(pdf, (255, 255, 255))
    component_header(pdf, title, explain, accent)


def component_paragraph(pdf: BrandPDF, col_span: int, text: str):
    if not text:
        return
    L = pdf.layout
    w = L.w(col_span)

    pdf.f_body("", 11)
    pdf.set_text_color(*pdf.c_text)

    for para in (text or "").split("\n"):
        p = para.strip()
        if not p:
            pdf.ln(L.base * 0.9)
            continue
        safe_multicell(pdf, w, L.base * 1.55, safe_text(p, pdf._latin_only))
        pdf.ln(L.base * 0.7)


def component_list(pdf: BrandPDF, col_span: int, items: list[str], max_items: int = 10):
    L = pdf.layout
    w = L.w(col_span)

    pdf.f_body("", 11)
    pdf.set_text_color(*pdf.c_text)

    shown = 0
    for it in items or []:
        if shown >= max_items:
            break
        s = (it or "").strip()
        if not s:
            continue
        line = f"- {s}"
        safe_multicell(pdf, w, L.base * 1.55, safe_text(line, pdf._latin_only))
        pdf.ln(L.base * 0.35)
        shown += 1


def component_two_col_lists(pdf: BrandPDF, left_title: str, left_items: list[str], right_title: str, right_items: list[str], accent: tuple[int, int, int]):
    L = pdf.layout
    x1 = L.margin_l
    x2 = L.x(6)
    w = L.w(5)

    y0 = pdf.get_y()

    def col(x: float, title: str, items: list[str]) -> float:
        pdf.set_xy(x, y0)
        pdf.f_body("M", 11.5)
        pdf.set_text_color(*pdf.c_text)
        pdf.cell(w, inch(0.22), safe_text(title, pdf._latin_only), ln=1)

        pdf_rule(pdf, x, pdf.get_y() + inch(0.03), inch(0.70), accent)
        pdf.ln(inch(0.12))

        pdf.f_body("", 10.8)
        pdf.set_text_color(*pdf.c_text)

        y = pdf.get_y()
        shown = 0
        for it in items or []:
            if shown >= 8:
                break
            s = (it or "").strip()
            if not s:
                continue
            pdf.set_xy(x, y)
            safe_multicell(pdf, w, L.base * 1.50, safe_text(f"- {s}", pdf._latin_only))
            y = pdf.get_y() + L.base * 0.35
            shown += 1

        return y

    y_left = col(x1, left_title, left_items)
    y_right = col(x2, right_title, right_items)

    pdf.set_y(max(y_left, y_right) + inch(0.10))


def component_palette_page(pdf: BrandPDF, colors: dict, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf_bg_solid(pdf, (255, 255, 255))

    component_header(
        pdf,
        "Color palette",
        "A small, strict palette. Use it repeatedly. Consistency creates the premium feel.",
        accent
    )

    L = pdf.layout
    x = L.margin_l
    y = pdf.get_y() + inch(0.10)

    blocks = [
        ("Primary", colors.get("primary_hex", ""), colors.get("primary_reason", "")),
        ("Accent", colors.get("accent_hex", ""), colors.get("accent_reason", "")),
        ("Neutral", colors.get("neutral_hex", ""), colors.get("neutral_reason", "")),
        ("Background", colors.get("background_hex", ""), colors.get("background_reason", "")),
    ]

    sw = inch(1.05)
    sh = inch(0.45)

    for name, hx, reason in blocks:
        rgb = hex_to_rgb(hx, (230, 230, 230))

        pdf.set_fill_color(*rgb)
        pdf.rect(x, y, sw, sh, style="F")

        pdf.f_body("M", 11)
        pdf.set_text_color(*pdf.c_text)
        pdf.set_xy(x + sw + inch(0.18), y)
        pdf.cell(0, inch(0.20), safe_text(f"{name}  {hx or ''}".strip(), pdf._latin_only))

        pdf.f_body("", 10.2)
        pdf.set_text_color(*pdf.c_muted)
        pdf.set_xy(x + sw + inch(0.18), y + inch(0.22))
        safe_multicell(pdf, L.w(7), L.base * 1.35, safe_text((reason or "").strip(), pdf._latin_only))

        y += inch(0.72)


def component_typography_page(pdf: BrandPDF, typography: dict, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf_bg_solid(pdf, (255, 255, 255))

    component_header(
        pdf,
        "Typography",
        "A defined hierarchy that forces clean rhythm across slides and pages.",
        accent
    )

    L = pdf.layout
    x = L.margin_l
    y = pdf.get_y() + inch(0.10)

    primary = (typography.get("primary_font", "") or "").strip()
    secondary = (typography.get("secondary_font", "") or "").strip()
    pu = (typography.get("primary_use", "") or "").strip()
    su = (typography.get("secondary_use", "") or "").strip()
    rat = (typography.get("rationale", "") or "").strip()

    pdf.f_body("M", 12)
    pdf.set_text_color(*pdf.c_text)
    pdf.set_xy(x, y)
    pdf.cell(0, inch(0.22), safe_text(f"Primary font: {primary or 'Not specified'}", pdf._latin_only))
    y += inch(0.30)

    pdf.f_body("", 10.5)
    pdf.set_text_color(*pdf.c_muted)
    pdf.set_xy(x, y)
    safe_multicell(pdf, L.w(8), L.base * 1.35, safe_text(pu or "Use for headlines, section titles, and key moments.", pdf._latin_only))
    y = pdf.get_y() + inch(0.18)

    pdf.f_body("M", 12)
    pdf.set_text_color(*pdf.c_text)
    pdf.set_xy(x, y)
    pdf.cell(0, inch(0.22), safe_text(f"Secondary font: {secondary or 'Not specified'}", pdf._latin_only))
    y += inch(0.30)

    pdf.f_body("", 10.5)
    pdf.set_text_color(*pdf.c_muted)
    pdf.set_xy(x, y)
    safe_multicell(pdf, L.w(8), L.base * 1.35, safe_text(su or "Use for body, captions, and longer reading.", pdf._latin_only))
    y = pdf.get_y() + inch(0.22)

    if rat:
        pdf.f_body("", 10.5)
        pdf.set_text_color(*pdf.c_muted)
        pdf.set_xy(x, y)
        safe_multicell(pdf, L.w(8), L.base * 1.35, safe_text(rat, pdf._latin_only))
        y = pdf.get_y() + inch(0.22)

    # Sample hierarchy (uses our embedded fonts if available)
    pdf.f_body("M", 11)
    pdf.set_text_color(*pdf.c_text)
    pdf.set_xy(x, y)
    pdf.cell(0, inch(0.22), safe_text("Sample hierarchy", pdf._latin_only))
    y += inch(0.28)

    pdf.f_head("B", 30)
    pdf.set_text_color(*pdf.c_text)
    pdf.set_xy(x, y)
    safe_multicell(pdf, L.w(7), inch(0.36), safe_text("Headline example", pdf._latin_only))
    y = pdf.get_y() + inch(0.10)

    pdf.f_body("", 11)
    pdf.set_text_color(*pdf.c_text)
    pdf.set_xy(x, y)
    safe_multicell(pdf, L.w(7), L.base * 1.55, safe_text("Body text example. Short sentences. Clear meaning. No fluff. This should feel like the brand.", pdf._latin_only))


def component_moodboard(pdf: BrandPDF, image_paths: list[str], accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")
    pdf_bg_solid(pdf, (255, 255, 255))

    component_header(
        pdf,
        "Moodboard",
        "Visual direction in images. Use this to steer photography, texture, lighting, and composition.",
        accent
    )

    if not image_paths:
        return

    L = pdf.layout
    x0 = L.margin_l
    y0 = pdf.get_y() + inch(0.10)

    gap = inch(0.10)
    cols = 3
    rows = 2

    cell_w = (L.live_w - gap * (cols - 1)) / cols
    cell_h = (L.page_h - y0 - L.margin_b - gap * (rows - 1))

    cell_h = cell_h / rows

    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(image_paths):
                return
            x = x0 + c * (cell_w + gap)
            y = y0 + r * (cell_h + gap)
            try:
                pdf.image(image_paths[idx], x=x, y=y, w=cell_w, h=cell_h)
            except Exception:
                pass
            idx += 1


def component_closing(pdf: BrandPDF, brand: str, headline: str, subhead: str, photo_path: str | None, plate_path: str, accent: tuple[int, int, int]):
    pdf.add_page(orientation="L")

    if photo_path:
        try:
            pdf_full_bleed_image(pdf, photo_path)
        except Exception:
            pdf_full_bleed_image(pdf, plate_path)
    else:
        pdf_full_bleed_image(pdf, plate_path)

    panel_x = inch(0.80)
    panel_y = inch(1.55)
    panel_w = inch(7.20)
    panel_h = inch(4.40)

    pdf.set_fill_color(10, 12, 16)
    pdf.rect(panel_x, panel_y, panel_w, panel_h, style="F")

    pdf.set_text_color(255, 255, 255)

    pdf.f_head("B", 26)
    pdf.set_xy(panel_x + inch(0.35), panel_y + inch(0.60))
    safe_multicell(pdf, panel_w - inch(0.70), inch(0.32), safe_text(brand, pdf._latin_only))

    pdf.f_head("B", 22)
    pdf.set_xy(panel_x + inch(0.35), panel_y + inch(1.85))
    safe_multicell(pdf, panel_w - inch(0.70), inch(0.30), safe_text(headline, pdf._latin_only))

    pdf.f_body("", 12)
    pdf.set_xy(panel_x + inch(0.35), panel_y + inch(3.00))
    safe_multicell(pdf, panel_w - inch(0.70), inch(0.24), safe_text(subhead, pdf._latin_only))

    pdf.set_draw_color(*accent)
    pdf.set_line_width(1.2)
    pdf.line(panel_x + inch(0.35), panel_y + panel_h - inch(0.55), panel_x + inch(2.35), panel_y + panel_h - inch(0.55))

def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    crc_bytes = struct.pack(">I", crc & 0xFFFFFFFF)
    return length + chunk_type + data + crc_bytes


def _make_plate_png_bytes(w: int, h: int, c1: tuple[int, int, int], c2: tuple[int, int, int], bg: tuple[int, int, int]) -> bytes:
    seed = (c1[0] << 16) + (c1[1] << 8) + c1[2] + (c2[0] << 8) + c2[1] + (bg[2] << 4)
    x = seed & 0xFFFFFFFF

    def rnd() -> int:
        nonlocal x
        x = (1664525 * x + 1013904223) & 0xFFFFFFFF
        return x

    scanlines = bytearray()
    for y in range(h):
        scanlines.append(0)
        t = y / max(h - 1, 1)
        for px in range(w):
            u = px / max(w - 1, 1)
            k = (u * 0.62 + t * 0.38)
            r = int(c1[0] * (1 - k) + c2[0] * k)
            g = int(c1[1] * (1 - k) + c2[1] * k)
            b = int(c1[2] * (1 - k) + c2[2] * k)

            n = (rnd() >> 24) - 128
            n = int(n * 0.10)

            dx = (u - 0.5)
            dy = (t - 0.5)
            v = 1.0 - min(0.55, (dx * dx + dy * dy) * 1.25)

            r = int((r + bg[0]) * 0.5 * v + r * 0.5)
            g = int((g + bg[1]) * 0.5 * v + g * 0.5)
            b = int((b + bg[2]) * 0.5 * v + b * 0.5)

            r = max(0, min(255, r + n))
            g = max(0, min(255, g + n))
            b = max(0, min(255, b + n))

            scanlines.extend((r, g, b))

    raw = bytes(scanlines)
    compressed = zlib.compress(raw, level=7)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return signature + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", compressed) + _png_chunk(b"IEND", b"")


def _write_temp_png(png_bytes: bytes, key: str) -> str:
    if key in st.session_state.plate_paths and os.path.exists(st.session_state.plate_paths[key]):
        return st.session_state.plate_paths[key]
    f = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{key}.png")
    f.write(png_bytes)
    f.flush()
    f.close()
    st.session_state.plate_paths[key] = f.name
    return f.name


def make_cover_plate(primary: tuple[int, int, int], accent: tuple[int, int, int], background: tuple[int, int, int]) -> str:
    png = _make_plate_png_bytes(1900, 1100, primary, accent, background)
    key = f"cover_{primary[0]}_{primary[1]}_{primary[2]}_{accent[0]}_{accent[1]}_{accent[2]}_{background[0]}_{background[1]}_{background[2]}"
    return _write_temp_png(png, key=key)


def render_pdf(schema: dict, answers: dict) -> bytes:
    meta = schema.get("meta", {}) or {}
    colors = schema.get("colors", {}) or {}
    hero = schema.get("hero", {}) or {}
    typography = schema.get("typography", {}) or {}

    brand = (meta.get("brand_name", "") or "").strip() or (answers.get("brand_name", "") or "").strip() or "Brand"

    primary = hex_to_rgb(colors.get("primary_hex", ""), (18, 22, 30))
    accent = hex_to_rgb(colors.get("accent_hex", ""), (28, 125, 255))
    background = hex_to_rgb(colors.get("background_hex", ""), (245, 246, 248))

    # Plate already generated by your existing helpers above
    cover_plate_path = make_cover_plate(primary, accent, background)

    pdf = BrandPDF(orientation="L", unit="mm", format=(Layout().page_w, Layout().page_h))
    pdf.set_auto_page_break(auto=True, margin=pdf.layout.margin_b)
    pdf.set_brand_fonts()
    pdf.brand_name = brand

    # Curated imagery from Unsplash (your existing functions above)
    seed = int(time.time_ns() & 0xFFFFFFFF)
    theme = pick_photo_theme(answers, schema)
    photos = get_curated_images(theme, answers, schema, count=10, seed=seed)

    cover_photo = photos[0] if len(photos) > 0 else None
    intro_photo = photos[1] if len(photos) > 1 else None
    pos_photo = photos[2] if len(photos) > 2 else None
    msg_photo = photos[3] if len(photos) > 3 else None
    vis_photo = photos[4] if len(photos) > 4 else None
    closing_photo = photos[5] if len(photos) > 5 else cover_photo
    mood = photos[4:10] if len(photos) >= 10 else photos[:6]

    deck_sub = (hero.get("deck_subtitle", "") or "").strip() or "Brand system: a practical guide to consistency"

    component_cover(pdf, brand=brand, deck_subtitle=deck_sub, photo_path=cover_photo, plate_path=cover_plate_path, accent=accent)
    component_intro(pdf, brand=brand, date_utc=utc_date_str(), image_path=intro_photo, accent=accent)

    component_contents(
        pdf,
        accent=accent,
        items=[
            ("Executive summary", "The decisions that keep the brand consistent."),
            ("Positioning", "Where you stand, and what you refuse to be."),
            ("Audience", "One real person, one real tension, one real objection."),
            ("Messaging", "Repeatable messages backed by proof."),
            ("Voice", "Rules that stop bad copy before it exists."),
            ("Visual direction", "Taste, constraints, and imagery posture."),
            ("Color palette", "A strict palette that makes everything look deliberate."),
            ("Typography", "Hierarchy that forces rhythm and clarity."),
            ("Guardrails", "How the brand gets ruined and how to avoid it."),
            ("How to use this", "How to apply the system in real work."),
        ]
    )

    # Executive summary
    component_section_opener(pdf, "Executive summary", "The decisions that keep the brand consistent.", primary, None, accent)
    component_body_page(pdf, "Executive summary", "The few decisions that matter most. Keep these stable and everything stays premium.", accent)
    decisions = ((schema.get("executive_summary", {}) or {}).get("decisions", []) or [])
    component_list(pdf, 7, [d for d in decisions if (d or "").strip()], max_items=10)

    # Positioning
    component_section_opener(pdf, "Positioning", "Where you stand, and what you refuse to be.", background, pos_photo, accent)
    component_body_page(pdf, "Positioning", "A clean position makes everything easier to write, design, and sell.", accent)
    pos = schema.get("positioning", {}) or {}
    component_paragraph(pdf, 7, (pos.get("positioning_statement", "") or "").strip())

    left_items = []
    cat = (pos.get("category", "") or "").strip()
    if cat:
        left_items.append(f"Category we own: {cat}")

    anti = (pos.get("anti_position", "") or "").strip()
    right_items = [anti] if anti else ["Vague, polite, generic."]

    component_two_col_lists(pdf, "What we are", left_items or ["Clear category ownership."], "What we are not", right_items, accent)

    # Audience
    component_section_opener(pdf, "Audience", "One real person. One real tension.", background, None, accent)
    component_body_page(pdf, "Audience and insight", "Define the person and the tension. This decides the tone and proof you need.", accent)
    aud = schema.get("audience", {}) or {}
    component_list(
        pdf,
        7,
        [
            (aud.get("core_customer", "") or "").strip(),
            (aud.get("core_tension", "") or "").strip(),
            (aud.get("primary_objection", "") or "").strip(),
            (aud.get("trust_trigger", "") or "").strip(),
        ],
        max_items=10
    )

    # Messaging
    component_section_opener(pdf, "Messaging", "Repeatable messages backed by proof.", background, msg_photo, accent)
    component_body_page(pdf, "Messaging", "Say the same few things repeatedly. Premium brands repeat, they do not ramble.", accent)
    msg = schema.get("messaging", {}) or {}
    component_paragraph(pdf, 7, (msg.get("core_message", "") or "").strip())

    kms = (msg.get("key_messages", []) or [])[:4]
    if kms:
        pdf.ln(inch(0.10))
        for km in kms:
            m = (km.get("message", "") or "").strip()
            p = (km.get("proof", "") or "").strip()
            if m:
                pdf.f_body("M", 11.5)
                pdf.set_text_color(*pdf.c_text)
                safe_multicell(pdf, pdf.layout.w(7), pdf.layout.base * 1.55, safe_text(m, pdf._latin_only))
            if p:
                pdf.f_body("", 10.5)
                pdf.set_text_color(*pdf.c_muted)
                safe_multicell(pdf, pdf.layout.w(7), pdf.layout.base * 1.45, safe_text(p, pdf._latin_only))
            pdf.ln(inch(0.12))

    # Voice
    component_section_opener(pdf, "Voice", "Rules that stop bad copy before it exists.", primary, None, accent)
    component_body_page(pdf, "Voice rules", "This section is your copy filter. Use it before anything is published.", accent)
    voice = schema.get("voice", {}) or {}
    component_list(pdf, 7, [x for x in (voice.get("principles", []) or []) if (x or "").strip()], max_items=8)

    component_two_col_lists(
        pdf,
        "Do say",
        [x for x in (voice.get("do_say", []) or []) if (x or "").strip()],
        "Do not say",
        [x for x in (voice.get("do_not_say", []) or []) if (x or "").strip()],
        accent
    )

    ex = voice.get("examples", {}) or {}
    before = (ex.get("before", "") or "").strip()
    after = (ex.get("after", "") or "").strip()
    if before and after:
        component_body_page(pdf, "Voice example", "A fast before and after to calibrate tone.", accent)
        component_two_col_lists(pdf, "Before", [before], "After", [after], accent)

    # Visual direction
    component_section_opener(pdf, "Visual direction", "Taste, constraints, and imagery posture.", background, vis_photo, accent)
    component_moodboard(pdf, mood, accent)
    component_body_page(pdf, "Visual direction", "Use this to judge photography, layout density, texture, and overall feel.", accent)

    vis = schema.get("visual_direction", {}) or {}
    component_paragraph(pdf, 7, (vis.get("intent", "") or "").strip())
    component_two_col_lists(
        pdf,
        "Feels like",
        [x for x in (vis.get("feels_like", []) or []) if (x or "").strip()],
        "Never feels like",
        [x for x in (vis.get("never_feels_like", []) or []) if (x or "").strip()],
        accent
    )

    # Palette and typography as separate pages (not combined)
    component_palette_page(pdf, colors, accent)
    component_typography_page(pdf, typography, accent)

    # Guardrails
    component_section_opener(pdf, "Guardrails", "How the brand gets ruined. Avoid these.", primary, None, accent)
    component_body_page(pdf, "Guardrails", "Failure modes to avoid. This is where consistency dies if ignored.", accent)
    guard = schema.get("guardrails", {}) or {}
    component_list(pdf, 7, [x for x in (guard.get("failure_modes", []) or []) if (x or "").strip()], max_items=12)

    # How to use
    component_section_opener(pdf, "How to use this", "Open this when the team starts to drift.", background, None, accent)
    component_body_page(pdf, "How to use this", "A short operating system for applying the document in real work.", accent)
    usage = schema.get("usage", {}) or {}
    component_list(pdf, 7, [x for x in (usage.get("how_to_use", []) or []) if (x or "").strip()], max_items=12)

    # Closing
    headline = (hero.get("headline", "") or "").strip() or "A brand system you can actually follow"
    subhead = (hero.get("subhead", "") or "").strip() or "Consistency is not a feeling. It is a set of rules."
    component_closing(pdf, brand=brand, headline=headline, subhead=subhead, photo_path=closing_photo, plate_path=cover_plate_path, accent=accent)

    out = pdf.output(dest="S")
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return str(out).encode("latin-1", "replace")



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
        '<div class="heroSub">A guided brand interview that turns strategy, voice, and visual direction into a premium landscape PDF deck with real design rhythm.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="pills">
          <div class="pill">Landscape deck</div>
          <div class="pill">Curated imagery</div>
          <div class="pill">Color and typography</div>
          <div class="pill">Rules, not fluff</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2], gap="large")
    with col1:
        st.subheader("Why a brand bible matters")
        st.write("Most brands fail because nothing is defined.")
        st.write("A brand bible is not a document. It is a decision system.")
        st.write("With a real system, teams decide faster, argue less, and stay consistent without trying.")

    with col2:
        st.subheader("What you get")
        st.write("Positioning and category clarity")
        st.write("Messaging system with proof points")
        st.write("Voice rules with examples")
        st.write("Visual direction and guardrails")
        st.caption("Includes 5 generations per purchase concept.")

    st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
    if st.button("Start brand interview"):
        st.session_state.step_index = 0
        go("wizard")
    st.markdown("</div>", unsafe_allow_html=True)

    if not st.session_state.api_key:
        st.info("Developer note: Set GEMINI_API_KEY in secrets.toml. This app also needs requests for curated imagery.")
        with st.expander("Developer settings"):
            st.session_state.api_key = st.text_input("Gemini API key", type="password", value=st.session_state.api_key)


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

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back to interview"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="bigBtn">', unsafe_allow_html=True)
        if st.button("Generate brand bible", disabled=(remaining <= 0)):
            go("generate")
        st.markdown("</div>", unsafe_allow_html=True)


def generate_view():
    st.markdown('<div class="eyebrow">Generating</div>', unsafe_allow_html=True)
    st.markdown('<div class="heroTitle" style="font-size:34px;">Building your brand deck</div>', unsafe_allow_html=True)
    st.markdown('<hr class="soft" />', unsafe_allow_html=True)

    api_key = (st.session_state.api_key or "").strip()
    if not api_key:
        st.error("Missing API key.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("landing")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    remaining = st.session_state.gen_max - st.session_state.gen_used
    if remaining <= 0:
        st.error("No generations remaining.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("done" if st.session_state.pdf_bytes else "confirm")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    genai.configure(api_key=api_key)

    brand = (st.session_state.answers.get("brand_name", "") or "").strip()
    if not brand:
        st.error("Brand name is required.")
        st.markdown('<div class="secondaryBtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("wizard")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    prompt = build_prompt(st.session_state.answers, version_str=str(st.session_state.gen_used + 1))
    stage = st.empty()

    try:
        with st.spinner("Working..."):
            stage.write("Defining strategy")
            time.sleep(0.06)
            schema, model_used = generate_schema(prompt, timeout_s=35)

            stage.write("Building deck design")
            time.sleep(0.06)
            pdf_bytes = render_pdf(schema, st.session_state.answers)

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
    st.markdown('<div class="heroTitle" style="font-size:34px;">Download your brand deck</div>', unsafe_allow_html=True)

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
            reset_app(keep_api_key=True)
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
