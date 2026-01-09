import json
import re
import time
import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

import streamlit as st

import google.generativeai as genai

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.lib import colors as rl_colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase.pdfmetrics import stringWidth

from PIL import Image, ImageDraw, ImageFilter


st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")


# -------------------------
# Core helpers
# -------------------------
def utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def clamp_str(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max(0, max_chars - 1)].rstrip() + "…"


def extract_json_object(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("{") and t.endswith("}"):
        return t
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if not m:
        raise ValueError("Model did not return JSON.")
    return m.group(0).strip()


def hex_to_rgb(hx: str, fallback: Tuple[int, int, int]) -> Tuple[int, int, int]:
    hx = (hx or "").strip().lstrip("#")
    if len(hx) != 6:
        return fallback
    try:
        r = int(hx[0:2], 16)
        g = int(hx[2:4], 16)
        b = int(hx[4:6], 16)
        return (r, g, b)
    except Exception:
        return fallback


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return "#{:02X}{:02X}{:02X}".format(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def luma(rgb: Tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_rgb_for_bg(bg: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return (255, 255, 255) if luma(bg) < 140 else (18, 22, 30)


def stable_int_hash(s: str) -> int:
    h = hashlib.sha256((s or "").encode("utf-8")).hexdigest()
    return int(h[:12], 16)


# -------------------------
# Gemini generation
# -------------------------
FONT_POOL = [
    "Inter", "Manrope", "Plus Jakarta Sans", "Space Grotesk", "DM Sans",
    "IBM Plex Sans", "Work Sans", "Sora", "Urbanist", "Outfit",
    "Montserrat", "Raleway", "Source Sans 3", "Public Sans", "Rubik",
    "Merriweather", "Lora", "Fraunces", "Cormorant Garamond", "Libre Baskerville"
]


def choose_models_to_try() -> List[str]:
    # Keep it simple and resilient
    return [
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.0-flash-exp",
    ]


def build_prompt(answers: Dict[str, Any], version_str: str) -> str:
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
        f"{', '.join(FONT_POOL)}\n"
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


def generate_schema(api_key: str, answers: Dict[str, Any], version_str: str, timeout_s: int = 35) -> Tuple[Dict[str, Any], str]:
    genai.configure(api_key=api_key)

    prompt = build_prompt(answers, version_str)
    models = choose_models_to_try()
    last_err: Optional[Exception] = None

    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt, request_options={"timeout": timeout_s})
            raw = (getattr(resp, "text", "") or "").strip()
            data = json.loads(extract_json_object(raw))

            required = [
                "meta", "colors", "typography", "hero", "executive_summary", "positioning",
                "audience", "messaging", "voice", "visual_direction", "guardrails", "usage"
            ]
            for k in required:
                if k not in data:
                    raise ValueError("JSON missing required keys.")

            data["meta"]["brand_name"] = data["meta"].get("brand_name") or (answers.get("brand_name") or "")
            data["meta"]["version"] = version_str
            data["meta"]["date_utc"] = utc_date_str()
            return data, model_name

        except Exception as e:
            last_err = e

    raise RuntimeError(f"Generation failed: {last_err}")


# -------------------------
# Curated image generation
# Procedural images, consistent per document, varied across runs
# -------------------------
def make_texture(seed: int, size: Tuple[int, int], palette: List[Tuple[int, int, int]]) -> Image.Image:
    rng = random.Random(seed)
    w, h = size
    base = Image.new("RGB", (w, h), palette[0])
    draw = ImageDraw.Draw(base)

    # Soft gradient layers
    for i in range(4):
        c = palette[rng.randrange(0, len(palette))]
        x0 = rng.randint(-w // 3, w)
        y0 = rng.randint(-h // 3, h)
        x1 = x0 + rng.randint(w // 2, w + w // 2)
        y1 = y0 + rng.randint(h // 2, h + h // 2)
        draw.ellipse([x0, y0, x1, y1], fill=c)

    # Fine grain
    noise = Image.effect_noise((w, h), rng.uniform(6.0, 14.0)).convert("L")
    noise = noise.point(lambda p: int(p * rng.uniform(0.6, 1.0)))
    base = Image.composite(base, Image.new("RGB", (w, h), palette[-1]), noise)

    # Blur for premium feel
    base = base.filter(ImageFilter.GaussianBlur(radius=rng.uniform(2.0, 6.0)))

    # Subtle line system
    draw = ImageDraw.Draw(base)
    line_c = palette[rng.randrange(0, len(palette))]
    line_c2 = tuple(int(x * 0.6) for x in line_c)
    step = rng.randint(42, 88)
    for x in range(-w, w * 2, step):
        y = rng.randint(-h // 2, h + h // 2)
        draw.line([(x, y), (x + w, y + rng.randint(-40, 40))], fill=line_c2, width=rng.randint(1, 2))

    return base


def generate_curated_images(seed: int, colors_rgb: Dict[str, Tuple[int, int, int]]) -> Dict[str, Image.Image]:
    primary = colors_rgb["primary"]
    accent = colors_rgb["accent"]
    neutral = colors_rgb["neutral"]
    background = colors_rgb["background"]

    palette = [primary, accent, neutral, background, (245, 245, 245)]
    # Ensure contrast: reorder a bit
    palette = sorted(palette, key=lambda c: luma(c))

    # Slots: keep them stable across document
    images = {
        "hero": make_texture(seed + 11, (2400, 1600), palette[::-1]),
        "support_1": make_texture(seed + 21, (2400, 1600), palette),
        "support_2": make_texture(seed + 31, (2400, 1600), palette[::-1]),
        "support_3": make_texture(seed + 41, (2400, 1600), palette),
        "support_4": make_texture(seed + 51, (2400, 1600), palette[::-1]),
    }
    return images


# -------------------------
# PDF layout engine (ReportLab)
# No overlap, fixed templates, controlled truncation
# -------------------------
PAGE_W, PAGE_H = landscape(A4)

MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 16 * mm
MARGIN_B = 14 * mm

CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R
CONTENT_H = PAGE_H - MARGIN_T - MARGIN_B

ACCENT_LINE_W = 70 * mm

STYLE_H1 = ParagraphStyle(
    "h1", fontName="Helvetica-Bold", fontSize=28, leading=32, textColor=rl_colors.HexColor("#12161E"), alignment=TA_LEFT
)
STYLE_H2 = ParagraphStyle(
    "h2", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=rl_colors.HexColor("#12161E"), alignment=TA_LEFT
)
STYLE_BODY = ParagraphStyle(
    "body", fontName="Helvetica", fontSize=11, leading=15, textColor=rl_colors.HexColor("#232832"), alignment=TA_LEFT
)
STYLE_MUTED = ParagraphStyle(
    "muted", fontName="Helvetica", fontSize=10, leading=14, textColor=rl_colors.HexColor("#505866"), alignment=TA_LEFT
)
STYLE_SMALL = ParagraphStyle(
    "small", fontName="Helvetica", fontSize=9, leading=12, textColor=rl_colors.HexColor("#6B7380"), alignment=TA_LEFT
)


def draw_page_number(c: canvas.Canvas, brand: str, page_no: int):
    # Page numbering starts after cover
    c.setFillColor(rl_colors.HexColor("#7C8696"))
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN_L, 8 * mm, brand)
    c.drawRightString(PAGE_W - MARGIN_R, 8 * mm, str(page_no))


def draw_accent_rule(c: canvas.Canvas, x: float, y: float, accent_rgb: Tuple[int, int, int], w: float = ACCENT_LINE_W):
    c.setStrokeColor(rl_colors.Color(accent_rgb[0] / 255, accent_rgb[1] / 255, accent_rgb[2] / 255))
    c.setLineWidth(1.5)
    c.line(x, y, x + w, y)


def ptext(c: canvas.Canvas, x: float, y: float, w: float, h: float, text: str, style: ParagraphStyle) -> float:
    # Fit paragraph into a box with truncation if needed
    text = (text or "").strip()
    if not text:
        return y

    para = Paragraph(text.replace("\n", "<br/>"), style)
    _, needed = para.wrap(w, h)
    if needed <= h:
        para.drawOn(c, x, y - needed)
        return y - needed

    # Truncate by characters until it fits
    lo = 0
    hi = len(text)
    best = ""
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = clamp_str(text, mid)
        para2 = Paragraph(candidate.replace("\n", "<br/>"), style)
        _, need2 = para2.wrap(w, h)
        if need2 <= h:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1

    para3 = Paragraph(best.replace("\n", "<br/>"), style)
    _, need3 = para3.wrap(w, h)
    para3.drawOn(c, x, y - need3)
    return y - need3


def bullet_lines(items: List[str], max_items: int) -> List[str]:
    out = []
    for it in items or []:
        s = (it or "").strip()
        if not s:
            continue
        out.append(s)
        if len(out) >= max_items:
            break
    return out


def draw_bullets(c: canvas.Canvas, x: float, y: float, w: float, h: float, items: List[str], max_items: int) -> float:
    lines = bullet_lines(items, max_items)
    if not lines:
        return y
    # We render bullets as separate paragraphs to keep wrapping reliable
    cur_y = y
    for s in lines:
        cur_y = ptext(c, x, cur_y, w, max(0.0, cur_y - (y - h)), f"• {s}", STYLE_BODY)
        cur_y -= 2
        if cur_y < (y - h) + 6:
            break
    return cur_y


def pil_to_temp_png(img: Image.Image) -> str:
    import tempfile
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img.save(f.name, "PNG", optimize=True)
    f.close()
    return f.name


def draw_image_cover(c: canvas.Canvas, img_path: str):
    c.drawImage(img_path, 0, 0, width=PAGE_W, height=PAGE_H, mask="auto")


def draw_cover(c: canvas.Canvas, brand: str, deck: str, img_path: str, primary_rgb: Tuple[int, int, int]):
    draw_image_cover(c, img_path)

    # Dark overlay panel
    panel_x = 16 * mm
    panel_y = 40 * mm
    panel_w = 190 * mm
    panel_h = 95 * mm

    c.setFillColor(rl_colors.Color(0.04, 0.05, 0.07, alpha=0.92))
    c.roundRect(panel_x, panel_y, panel_w, panel_h, 8, fill=1, stroke=0)

    tc = text_rgb_for_bg((10, 12, 16))
    c.setFillColor(rl_colors.Color(tc[0] / 255, tc[1] / 255, tc[2] / 255))

    c.setFont("Helvetica-Bold", 46)
    c.drawString(panel_x + 10 * mm, panel_y + panel_h - 26 * mm, brand)

    c.setFont("Helvetica", 13)
    # Keep deck short and premium
    deck = clamp_str(deck, 120)
    text_y = panel_y + 18 * mm
    ptext(c, panel_x + 10 * mm, text_y + 26 * mm, panel_w - 20 * mm, 26 * mm, deck, STYLE_MUTED)


def draw_title_page(c: canvas.Canvas, title: str, subtitle: str, bg_rgb: Tuple[int, int, int], accent_rgb: Tuple[int, int, int], page_no: int, brand: str):
    c.setFillColor(rl_colors.Color(bg_rgb[0] / 255, bg_rgb[1] / 255, bg_rgb[2] / 255))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    tc = text_rgb_for_bg(bg_rgb)
    c.setFillColor(rl_colors.Color(tc[0] / 255, tc[1] / 255, tc[2] / 255))
    c.setFont("Helvetica-Bold", 44)
    c.drawString(MARGIN_L, PAGE_H / 2 + 12 * mm, title)

    ptext(c, MARGIN_L, PAGE_H / 2 - 4 * mm, 200 * mm, 26 * mm, subtitle, ParagraphStyle(
        "sub", parent=STYLE_MUTED, fontSize=14, leading=18,
        textColor=rl_colors.Color(tc[0] / 255, tc[1] / 255, tc[2] / 255)
    ))

    draw_page_number(c, brand, page_no)


def draw_content_header(c: canvas.Canvas, title: str, accent_rgb: Tuple[int, int, int], page_no: int, brand: str):
    c.setFillColor(rl_colors.white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setFillColor(rl_colors.HexColor("#12161E"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(MARGIN_L, PAGE_H - MARGIN_T - 4 * mm, title)

    draw_accent_rule(c, MARGIN_L, PAGE_H - MARGIN_T - 10 * mm, accent_rgb, 70 * mm)
    draw_page_number(c, brand, page_no)


def draw_how_to_use(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int):
    draw_content_header(c, "How to use this", accent_rgb, page_no, brand)

    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm
    w = 150 * mm
    h = 110 * mm

    text = (
        "This document is a decision system.\n"
        "Use it to keep voice, visuals, and messaging consistent.\n\n"
        "Start here when writing copy, selecting imagery, designing pages, or approving work.\n"
        "If a decision conflicts with this document, the document wins.\n\n"
        f"Generated for {brand} on {utc_date_str()}."
    )
    ptext(c, x, top, w, h, text, STYLE_BODY)


def draw_exec_summary(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, decisions: List[str]):
    draw_content_header(c, "Executive summary", accent_rgb, page_no, brand)

    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm
    draw_bullets(c, x, top, 210 * mm, 120 * mm, decisions, max_items=6)


def draw_positioning(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, pos: Dict[str, Any]):
    draw_content_header(c, "Positioning", accent_rgb, page_no, brand)

    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm

    statement = (pos.get("positioning_statement") or "").strip()
    category = (pos.get("category") or "").strip()
    anti = (pos.get("anti_position") or "").strip()

    ptext(c, x, top, 210 * mm, 46 * mm, statement, STYLE_BODY)

    # Two columns, boxed, fixed
    col_w = (CONTENT_W - 10 * mm) / 2
    box_h = 70 * mm
    y_box_top = top - 58 * mm

    # Left
    c.setStrokeColor(rl_colors.HexColor("#E3E7EE"))
    c.roundRect(x, y_box_top - box_h, col_w, box_h, 6, fill=0, stroke=1)
    ptext(c, x + 6 * mm, y_box_top - 8 * mm, col_w - 12 * mm, 16 * mm, "What we are", STYLE_H2)
    left_lines = []
    if category:
        left_lines.append(f"Category: {category}")
    left_lines = left_lines or ["Clear category ownership."]
    draw_bullets(c, x + 6 * mm, y_box_top - 24 * mm, col_w - 12 * mm, box_h - 30 * mm, left_lines, max_items=5)

    # Right
    x2 = x + col_w + 10 * mm
    c.roundRect(x2, y_box_top - box_h, col_w, box_h, 6, fill=0, stroke=1)
    ptext(c, x2 + 6 * mm, y_box_top - 8 * mm, col_w - 12 * mm, 16 * mm, "What we are not", STYLE_H2)
    right_lines = [anti] if anti else ["Vague, polite, generic."]
    draw_bullets(c, x2 + 6 * mm, y_box_top - 24 * mm, col_w - 12 * mm, box_h - 30 * mm, right_lines, max_items=5)


def draw_audience(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, aud: Dict[str, Any]):
    draw_content_header(c, "Audience and insight", accent_rgb, page_no, brand)
    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm

    items = [
        (aud.get("core_customer") or "").strip(),
        (aud.get("core_tension") or "").strip(),
        (aud.get("primary_objection") or "").strip(),
        (aud.get("trust_trigger") or "").strip(),
    ]
    draw_bullets(c, x, top, 210 * mm, 120 * mm, items, max_items=6)


def draw_messaging(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, msg: Dict[str, Any]):
    draw_content_header(c, "Messaging", accent_rgb, page_no, brand)
    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm

    core = (msg.get("core_message") or "").strip()
    ptext(c, x, top, 210 * mm, 34 * mm, core, STYLE_BODY)

    kms = (msg.get("key_messages") or [])[:3]
    y = top - 42 * mm
    for km in kms:
        m = (km.get("message") or "").strip()
        proof = (km.get("proof") or "").strip()
        if not m:
            continue

        ptext(c, x, y, 210 * mm, 16 * mm, m, ParagraphStyle("kmh", parent=STYLE_BODY, fontName="Helvetica-Bold"))
        y -= 16 * mm
        if proof:
            ptext(c, x, y + 6 * mm, 210 * mm, 18 * mm, proof, STYLE_MUTED)
            y -= 18 * mm

        y -= 4 * mm
        if y < 40 * mm:
            break


def draw_voice_rules(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, voice: Dict[str, Any]):
    draw_content_header(c, "Voice rules", accent_rgb, page_no, brand)

    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm

    principles = (voice.get("principles") or [])[:6]
    draw_bullets(c, x, top, 120 * mm, 60 * mm, principles, max_items=6)

    col_w = (CONTENT_W - 10 * mm) / 2
    box_h = 68 * mm
    y_box_top = top - 70 * mm

    do_say = (voice.get("do_say") or [])[:7]
    dont = (voice.get("do_not_say") or [])[:7]

    c.setStrokeColor(rl_colors.HexColor("#E3E7EE"))
    c.roundRect(x, y_box_top - box_h, col_w, box_h, 6, fill=0, stroke=1)
    ptext(c, x + 6 * mm, y_box_top - 8 * mm, col_w - 12 * mm, 14 * mm, "Do say", STYLE_H2)
    draw_bullets(c, x + 6 * mm, y_box_top - 22 * mm, col_w - 12 * mm, box_h - 26 * mm, do_say, max_items=7)

    x2 = x + col_w + 10 * mm
    c.roundRect(x2, y_box_top - box_h, col_w, box_h, 6, fill=0, stroke=1)
    ptext(c, x2 + 6 * mm, y_box_top - 8 * mm, col_w - 12 * mm, 14 * mm, "Do not say", STYLE_H2)
    draw_bullets(c, x2 + 6 * mm, y_box_top - 22 * mm, col_w - 12 * mm, box_h - 26 * mm, dont, max_items=7)


def draw_voice_example(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, before: str, after: str):
    draw_content_header(c, "Voice example", accent_rgb, page_no, brand)

    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm
    col_w = (CONTENT_W - 10 * mm) / 2
    box_h = 110 * mm

    c.setStrokeColor(rl_colors.HexColor("#E3E7EE"))
    c.roundRect(x, top - box_h, col_w, box_h, 6, fill=0, stroke=1)
    ptext(c, x + 6 * mm, top - 8 * mm, col_w - 12 * mm, 14 * mm, "Before", STYLE_H2)
    ptext(c, x + 6 * mm, top - 24 * mm, col_w - 12 * mm, box_h - 30 * mm, before, STYLE_BODY)

    x2 = x + col_w + 10 * mm
    c.roundRect(x2, top - box_h, col_w, box_h, 6, fill=0, stroke=1)
    ptext(c, x2 + 6 * mm, top - 8 * mm, col_w - 12 * mm, 14 * mm, "After", STYLE_H2)
    ptext(c, x2 + 6 * mm, top - 24 * mm, col_w - 12 * mm, box_h - 30 * mm, after, STYLE_BODY)


def draw_visual_direction(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, vis: Dict[str, Any], img_paths: Dict[str, str]):
    draw_content_header(c, "Visual direction", accent_rgb, page_no, brand)

    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm

    intent = (vis.get("intent") or "").strip()
    ptext(c, x, top, 210 * mm, 34 * mm, intent, STYLE_BODY)

    # Mood grid uses the curated set, stable per document
    grid_x = x
    grid_y_top = top - 44 * mm
    grid_w = 210 * mm
    grid_h = 70 * mm

    cell_w = (grid_w - 6 * mm) / 2
    cell_h = (grid_h - 6 * mm) / 2

    cells = [
        ("support_1", 0, 0),
        ("support_2", 1, 0),
        ("support_3", 0, 1),
        ("support_4", 1, 1),
    ]
    for key, cx, cy in cells:
        px = grid_x + cx * (cell_w + 6 * mm)
        py = (grid_y_top - (cy + 1) * cell_h - cy * 6 * mm)
        c.drawImage(img_paths[key], px, py, width=cell_w, height=cell_h, mask="auto")

    feels = (vis.get("feels_like") or [])[:6]
    never = (vis.get("never_feels_like") or [])[:6]

    y2 = grid_y_top - grid_h - 10 * mm
    col_w = (CONTENT_W - 10 * mm) / 2
    box_h = 48 * mm

    c.setStrokeColor(rl_colors.HexColor("#E3E7EE"))
    c.roundRect(x, y2 - box_h, col_w, box_h, 6, fill=0, stroke=1)
    ptext(c, x + 6 * mm, y2 - 8 * mm, col_w - 12 * mm, 14 * mm, "Feels like", STYLE_H2)
    draw_bullets(c, x + 6 * mm, y2 - 22 * mm, col_w - 12 * mm, box_h - 26 * mm, feels, max_items=6)

    x2 = x + col_w + 10 * mm
    c.roundRect(x2, y2 - box_h, col_w, box_h, 6, fill=0, stroke=1)
    ptext(c, x2 + 6 * mm, y2 - 8 * mm, col_w - 12 * mm, 14 * mm, "Never feels like", STYLE_H2)
    draw_bullets(c, x2 + 6 * mm, y2 - 22 * mm, col_w - 12 * mm, box_h - 26 * mm, never, max_items=6)


def draw_color_palette(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, colors_obj: Dict[str, Any]):
    draw_content_header(c, "Color palette", accent_rgb, page_no, brand)

    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm

    blocks = [
        ("Primary", colors_obj.get("primary_hex"), colors_obj.get("primary_reason")),
        ("Accent", colors_obj.get("accent_hex"), colors_obj.get("accent_reason")),
        ("Neutral", colors_obj.get("neutral_hex"), colors_obj.get("neutral_reason")),
        ("Background", colors_obj.get("background_hex"), colors_obj.get("background_reason")),
    ]

    sw_w = 58 * mm
    sw_h = 16 * mm
    row_h = 28 * mm

    y = top
    for name, hx, reason in blocks:
        rgb = hex_to_rgb(hx or "", (220, 220, 220))
        c.setFillColor(rl_colors.Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255))
        c.roundRect(x, y - sw_h, sw_w, sw_h, 4, fill=1, stroke=0)

        c.setFillColor(rl_colors.HexColor("#12161E"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x + sw_w + 8 * mm, y - 6 * mm, f"{name}  {rgb_to_hex(rgb)}")

        ptext(c, x + sw_w + 8 * mm, y - 12 * mm, 140 * mm, 14 * mm, (reason or "").strip(), STYLE_MUTED)

        y -= row_h
        if y < 50 * mm:
            break


def draw_typography(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, typo: Dict[str, Any]):
    draw_content_header(c, "Typography", accent_rgb, page_no, brand)

    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm

    primary = (typo.get("primary_font") or "").strip()
    secondary = (typo.get("secondary_font") or "").strip()
    primary_use = (typo.get("primary_use") or "").strip()
    secondary_use = (typo.get("secondary_use") or "").strip()
    rationale = (typo.get("rationale") or "").strip()

    ptext(c, x, top, 210 * mm, 14 * mm, f"Primary: {primary}", ParagraphStyle("t1", parent=STYLE_BODY, fontName="Helvetica-Bold", fontSize=14, leading=18))
    ptext(c, x, top - 14 * mm, 210 * mm, 20 * mm, primary_use, STYLE_MUTED)

    ptext(c, x, top - 40 * mm, 210 * mm, 14 * mm, f"Secondary: {secondary}", ParagraphStyle("t2", parent=STYLE_BODY, fontName="Helvetica-Bold", fontSize=14, leading=18))
    ptext(c, x, top - 54 * mm, 210 * mm, 20 * mm, secondary_use, STYLE_MUTED)

    # Rationale box
    box_y = top - 88 * mm
    box_h = 48 * mm
    c.setStrokeColor(rl_colors.HexColor("#E3E7EE"))
    c.roundRect(x, box_y - box_h, 210 * mm, box_h, 6, fill=0, stroke=1)
    ptext(c, x + 6 * mm, box_y - 8 * mm, 198 * mm, 14 * mm, "Why this pairing", STYLE_H2)
    ptext(c, x + 6 * mm, box_y - 24 * mm, 198 * mm, box_h - 28 * mm, rationale, STYLE_BODY)


def draw_guardrails(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, guard: Dict[str, Any]):
    draw_content_header(c, "Guardrails", accent_rgb, page_no, brand)
    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm
    items = (guard.get("failure_modes") or [])[:10]
    draw_bullets(c, x, top, 210 * mm, 120 * mm, items, max_items=10)


def draw_usage(c: canvas.Canvas, brand: str, accent_rgb: Tuple[int, int, int], page_no: int, usage: Dict[str, Any]):
    draw_content_header(c, "How to use this", accent_rgb, page_no, brand)
    x = MARGIN_L
    top = PAGE_H - MARGIN_T - 18 * mm
    items = (usage.get("how_to_use") or [])[:10]
    draw_bullets(c, x, top, 210 * mm, 120 * mm, items, max_items=10)


def draw_closing(c: canvas.Canvas, brand: str, img_path: str, accent_rgb: Tuple[int, int, int], page_no: int, headline: str, subhead: str):
    draw_image_cover(c, img_path)

    panel_x = 16 * mm
    panel_y = 34 * mm
    panel_w = 220 * mm
    panel_h = 78 * mm

    c.setFillColor(rl_colors.Color(0.04, 0.05, 0.07, alpha=0.92))
    c.roundRect(panel_x, panel_y, panel_w, panel_h, 8, fill=1, stroke=0)

    c.setFillColor(rl_colors.white)
    c.setFont("Helvetica-Bold", 30)
    headline = clamp_str(headline, 80)
    c.drawString(panel_x + 10 * mm, panel_y + panel_h - 26 * mm, headline)

    ptext(c, panel_x + 10 * mm, panel_y + 22 * mm, panel_w - 20 * mm, 22 * mm, subhead, ParagraphStyle(
        "cs", parent=STYLE_MUTED, fontSize=13, leading=17, textColor=rl_colors.white
    ))

    draw_page_number(c, brand, page_no)


def build_pdf_bytes(schema: Dict[str, Any], run_seed: int) -> bytes:
    meta = schema.get("meta") or {}
    brand = (meta.get("brand_name") or "").strip() or "Brand"
    colors_obj = schema.get("colors") or {}
    typo = schema.get("typography") or {}
    hero = schema.get("hero") or {}

    primary_rgb = hex_to_rgb(colors_obj.get("primary_hex") or "", (26, 26, 26))
    accent_rgb = hex_to_rgb(colors_obj.get("accent_hex") or "", (110, 140, 130))
    neutral_rgb = hex_to_rgb(colors_obj.get("neutral_hex") or "", (245, 245, 240))
    background_rgb = hex_to_rgb(colors_obj.get("background_hex") or "", (232, 232, 227))

    colors_rgb = {
        "primary": primary_rgb,
        "accent": accent_rgb,
        "neutral": neutral_rgb,
        "background": background_rgb,
    }

    curated = generate_curated_images(run_seed, colors_rgb)
    img_paths = {k: pil_to_temp_png(v) for k, v in curated.items()}

    deck = (hero.get("deck_subtitle") or "").strip() or "Brand system. Practical. Consistent. Controlled."
    headline = (hero.get("headline") or "").strip() or "A brand system you can actually follow"
    subhead = (hero.get("subhead") or "").strip() or "Consistency is not a feeling. It is a set of rules."

    from io import BytesIO
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))

    # Page 1: Cover, no page number
    draw_cover(c, brand, deck, img_paths["hero"], primary_rgb)
    c.showPage()

    # Page numbering starts at 2
    page_no = 2

    # How to use
    draw_how_to_use(c, brand, accent_rgb, page_no)
    c.showPage()
    page_no += 1

    # Executive summary
    decisions = ((schema.get("executive_summary") or {}).get("decisions") or [])
    draw_exec_summary(c, brand, accent_rgb, page_no, decisions)
    c.showPage()
    page_no += 1

    # Positioning
    draw_positioning(c, brand, accent_rgb, page_no, schema.get("positioning") or {})
    c.showPage()
    page_no += 1

    # Audience
    draw_audience(c, brand, accent_rgb, page_no, schema.get("audience") or {})
    c.showPage()
    page_no += 1

    # Messaging
    draw_messaging(c, brand, accent_rgb, page_no, schema.get("messaging") or {})
    c.showPage()
    page_no += 1

    # Voice rules
    voice = schema.get("voice") or {}
    draw_voice_rules(c, brand, accent_rgb, page_no, voice)
    c.showPage()
    page_no += 1

    # Voice example
    ex = (voice.get("examples") or {})
    before = (ex.get("before") or "").strip()
    after = (ex.get("after") or "").strip()
    if before and after:
        draw_voice_example(c, brand, accent_rgb, page_no, before, after)
        c.showPage()
        page_no += 1

    # Visual direction
    draw_visual_direction(c, brand, accent_rgb, page_no, schema.get("visual_direction") or {}, img_paths)
    c.showPage()
    page_no += 1

    # Color palette
    draw_color_palette(c, brand, accent_rgb, page_no, colors_obj)
    c.showPage()
    page_no += 1

    # Typography
    draw_typography(c, brand, accent_rgb, page_no, typo)
    c.showPage()
    page_no += 1

    # Guardrails
    draw_guardrails(c, brand, accent_rgb, page_no, schema.get("guardrails") or {})
    c.showPage()
    page_no += 1

    # Usage page from schema, separate from the early how-to page
    draw_usage(c, brand, accent_rgb, page_no, schema.get("usage") or {})
    c.showPage()
    page_no += 1

    # Closing
    draw_closing(c, brand, img_paths["support_2"], accent_rgb, page_no, headline, subhead)
    c.showPage()

    c.save()
    return buf.getvalue()


# -------------------------
# UI
# -------------------------
@dataclass
class Field:
    key: str
    label: str
    kind: str
    required: bool = True
    options: Optional[List[str]] = None
    help: str = ""


FIELDS = [
    Field("brand_name", "Brand name", "text", True, help="Name as it appears publicly."),
    Field("industry", "Industry", "text", True, help="Example: advisory, fintech, architecture, wellness."),
    Field("offer", "What do you sell", "textarea", True, help="One clear description of your offer."),
    Field("audience", "Core audience", "textarea", True, help="Who pays you, and why."),
    Field("first_impression", "First impression", "select", True, options=["Controlled", "Powerful", "Warm", "Curious", "Minimal"]),
    Field("voice_energy", "Voice energy", "select", True, options=["Calm", "Bold", "Warm", "Sharp"]),
    Field("brand_place", "Place or context", "text", False, help="Optional. Example: clinic, studio, lab, boardroom."),
    Field("avoid_vibes", "Avoid vibes", "multiselect", False, options=["Startup hype", "Luxury cliche", "Lifestyle fluff", "Generic corporate", "Overly playful"]),
    Field("competitor_1", "Competitor 1", "text", False),
    Field("competitor_2", "Competitor 2", "text", False),
    Field("must_keep", "Must keep", "textarea", False, help="Any non negotiables, words, claims, constraints."),
]


def get_answers_from_form() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in FIELDS:
        if f.kind == "text":
            out[f.key] = (st.session_state.get(f.key) or "").strip()
        elif f.kind == "textarea":
            out[f.key] = (st.session_state.get(f.key) or "").strip()
        elif f.kind == "select":
            out[f.key] = st.session_state.get(f.key)
        elif f.kind == "multiselect":
            out[f.key] = st.session_state.get(f.key) or []
    return out


def validate_answers(a: Dict[str, Any]) -> Tuple[bool, str]:
    for f in FIELDS:
        if not f.required:
            continue
        v = a.get(f.key)
        if f.kind in ["text", "textarea"] and not (v or "").strip():
            return False, f"{f.label} is required."
        if f.kind == "select" and not v:
            return False, f"{f.label} is required."
    return True, ""


def main():
    st.title("Brand Bible Generator")

    with st.sidebar:
        st.subheader("Settings")
        api_key = st.text_input("Gemini API key", type="password", value=(st.secrets.get("GEMINI_API_KEY", "") or "").strip())
        st.caption("If empty, paste a valid key here.")

        version_str = st.text_input("Version label", value="v1")
        st.caption("Any string, used in the document metadata.")
        st.divider()
        st.caption("Output is different each time because a run seed is injected into the intake.")

    # Intake form
    st.subheader("Intake")
    c1, c2 = st.columns(2)

    for i, f in enumerate(FIELDS):
        col = c1 if i % 2 == 0 else c2
        with col:
            if f.kind == "text":
                st.text_input(f.label, key=f.key, help=f.help)
            elif f.kind == "textarea":
                st.text_area(f.label, key=f.key, height=110, help=f.help)
            elif f.kind == "select":
                st.selectbox(f.label, options=f.options or [], key=f.key, help=f.help)
            elif f.kind == "multiselect":
                st.multiselect(f.label, options=f.options or [], key=f.key, help=f.help)

    st.divider()
    generate = st.button("Generate brand bible PDF", type="primary")

    if not generate:
        return

    if not api_key:
        st.error("API key is required.")
        return

    answers = get_answers_from_form()
    ok, msg = validate_answers(answers)
    if not ok:
        st.error(msg)
        return

    # Run seed makes each generation different, but coherent within the document
    # It also forces the model decisions to change because it is included in the intake JSON
    run_seed = random.SystemRandom().randint(1, 2_000_000_000)
    answers["_run_seed"] = run_seed
    answers["_run_utc"] = utc_date_str()
    answers["_run_note"] = "Use this seed to vary decisions while staying consistent inside the document."

    with st.status("Generating schema with Gemini", expanded=False) as status:
        try:
            schema, model_used = generate_schema(api_key, answers, version_str, timeout_s=40)
            status.update(label=f"Schema ready, model: {model_used}", state="complete")
        except Exception as e:
            status.update(label="Generation failed", state="error")
            st.error(str(e))
            return

    with st.status("Building PDF", expanded=False) as status:
        try:
            pdf_bytes = build_pdf_bytes(schema, run_seed=run_seed)
            status.update(label="PDF ready", state="complete")
        except Exception as e:
            status.update(label="PDF build failed", state="error")
            st.error(str(e))
            return

    brand_name = (schema.get("meta") or {}).get("brand_name") or (answers.get("brand_name") or "brand")
    safe_name = re.sub(r"[^a-zA-Z0-9._ -]+", "", brand_name).strip() or "brand"
    filename = f"{safe_name}_brand_bible_{utc_date_str()}.pdf"

    st.success("Done.")
    st.download_button("Download PDF", data=pdf_bytes, file_name=filename, mime="application/pdf")

    with st.expander("Debug: schema JSON"):
        st.json(schema)


if __name__ == "__main__":
    main()
