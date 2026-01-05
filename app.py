import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import concurrent.futures

st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")

# -----------------------------
# State
# -----------------------------
def ss(k, v):
    if k not in st.session_state:
        st.session_state[k] = v

ss("view", "landing")   # landing, inputs, generate, done
ss("company", "")
ss("industry", "")
ss("api_key", "")
ss("result", "")

# If you set secrets, auto fill
# Put this in .streamlit/secrets.toml:
# GEMINI_API_KEY="xxxxx"
if not st.session_state.api_key:
    st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "")

# -----------------------------
# CSS
# -----------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial; }
body {
  background:
    radial-gradient(1100px 700px at 20% 35%, rgba(0,120,255,0.18), rgba(0,0,0,0) 60%),
    radial-gradient(900px 600px at 80% 20%, rgba(255,255,255,0.06), rgba(0,0,0,0) 55%),
    #0b0d11;
  color: #e9edf5;
}

.block-container { max-width: 1100px; padding-top: 2.6rem; padding-bottom: 3.5rem; }

.shell {
  max-width: 980px;
  margin: 0 auto;
}

.glass {
  background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.03));
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 28px;
  box-shadow: 0 30px 120px rgba(0,0,0,0.55);
  backdrop-filter: blur(16px);
}

.card {
  padding: 34px;
}

.eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(235,240,255,0.62);
  margin-bottom: 10px;
}

.title {
  font-size: 54px;
  line-height: 1.05;
  letter-spacing: -0.03em;
  font-weight: 800;
  margin: 0 0 10px 0;
}

.sub {
  font-size: 16px;
  line-height: 1.7;
  color: rgba(235,240,255,0.72);
  margin-bottom: 18px;
  max-width: 760px;
}

.pills { display:flex; gap:10px; flex-wrap:wrap; margin-top: 14px; }
.pill {
  font-size: 12px;
  padding: 9px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  color: rgba(235,240,255,0.72);
}

.hr { height: 1px; background: rgba(255,255,255,0.08); margin: 18px 0 18px 0; }

label {
  font-size: 11px !important;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(235,240,255,0.55) !important;
  font-weight: 700 !important;
}

.stTextInput input {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  border-radius: 16px !important;
  color: rgba(235,240,255,0.90) !important;
}

.stTextInput input:focus {
  border: 1px solid rgba(28,125,255,0.75) !important;
  box-shadow: 0 0 0 5px rgba(28,125,255,0.18) !important;
}

.bigbtn div.stButton > button {
  width: 260px;
  height: 56px;
  border-radius: 999px;
  font-size: 18px;
  font-weight: 800;
  background: linear-gradient(180deg, #1c7dff, #0d5fe9) !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  box-shadow: 0 18px 50px rgba(0,110,255,0.35);
}

.bigbtn div.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 22px 66px rgba(0,110,255,0.45);
}

.centerRow { display:flex; justify-content:center; gap:14px; margin-top: 20px; }
.smallNote { font-size: 12px; color: rgba(235,240,255,0.55); margin-top: 10px; }

</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Helpers
# -----------------------------
def gemini_text(prompt: str, timeout_s: int = 35) -> str:
    model = genai.GenerativeModel("gemini-1.5-flash")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(model.generate_content, prompt)
        resp = fut.result(timeout=timeout_s)
    return (resp.text or "").strip()

def pdf_bytes(text: str, company: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_font("Arial", size=11)

    safe = (
        text.replace("\u2018", "'")
            .replace("\u2019", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("\u2026", "...")
    )
    safe = safe.encode("latin-1", "replace").decode("latin-1")

    for line in safe.split("\n"):
        pdf.multi_cell(0, 6, line)

    return pdf.output(dest="S").encode("latin-1")

def go(view: str):
    st.session_state.view = view
    st.rerun()

# -----------------------------
# Views
# -----------------------------
def landing():
    st.markdown('<div class="shell"><div class="glass card">', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Brand system generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="title">Make your brand bible feel designed.</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub">A guided workflow that captures strategy, voice, and visual direction, then produces a clean PDF that a team can actually use.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="pills">
          <div class="pill">Editorial flow</div>
          <div class="pill">Blueprint first</div>
          <div class="pill">PDF output</div>
          <div class="pill">Concrete rules</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="centerRow bigbtn">', unsafe_allow_html=True)
    if st.button("Start"):
        go("inputs")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="smallNote">Tip: set GEMINI_API_KEY in secrets.toml to avoid typing it.</div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

def inputs():
    st.markdown('<div class="shell"><div class="glass card">', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Brand inputs</div>', unsafe_allow_html=True)
    st.markdown('<div class="title" style="font-size:34px;">Tell us the basics.</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">These three fields are enough for a first usable PDF. Add more later.</div>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.text_input("Brand name", key="company", placeholder="Example: Oura")
    st.text_input("Industry", key="industry", placeholder="Example: Health tech")
    st.text_input("Gemini API key", key="api_key", type="password", placeholder="Paste your key")

    st.markdown('<div class="centerRow bigbtn">', unsafe_allow_html=True)
    if st.button("Generate brand bible"):
        if not st.session_state.company.strip():
            st.error("Brand name is required.")
            st.stop()
        if not st.session_state.api_key.strip():
            st.error("API key is required.")
            st.stop()
        go("generate")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="centerRow">', unsafe_allow_html=True)
    if st.button("Back"):
        go("landing")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)

def generate():
    st.markdown('<div class="shell"><div class="glass card">', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Generating</div>', unsafe_allow_html=True)
    st.markdown('<div class="title" style="font-size:34px;">Synthesizing into a PDF.</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">If Gemini does not respond within the timeout, you get a clean error instead of hanging forever.</div>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    api_key = st.session_state.api_key.strip()
    if not api_key:
        st.error("Missing API key.")
        st.markdown('<div class="centerRow bigbtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("inputs")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    genai.configure(api_key=api_key)

    prompt = f"""
You are a senior brand strategist and editorial designer.

Brand: {st.session_state.company.strip()}
Industry: {st.session_state.industry.strip()}

Write a brand bible in markdown with:
1) Executive summary
2) Positioning
3) Messaging system (key messages and proof points)
4) Voice rules (do say and do not say, with 6 example sentences)
5) Visual direction (palette logic, typography intent, imagery rules, what to avoid)

Be concrete. No fluff. No invented awards. If uncertain, present options.
"""

    try:
        with st.spinner("Working..."):
            st.session_state.result = gemini_text(prompt, timeout_s=35)
        go("done")
    except Exception as e:
        st.error(f"Generation failed: {e}")
        st.markdown('<div class="centerRow bigbtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("inputs")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)

def done():
    st.markdown('<div class="shell"><div class="glass card">', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Ready</div>', unsafe_allow_html=True)
    st.markdown('<div class="title" style="font-size:34px;">Download your PDF.</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">You can iterate later, but first we confirm the pipeline works.</div>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    if not st.session_state.result:
        st.error("No output found.")
        st.markdown('<div class="centerRow bigbtn">', unsafe_allow_html=True)
        if st.button("Back"):
            go("inputs")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    data = pdf_bytes(st.session_state.result, st.session_state.company.strip() or "Brand")

    st.download_button(
        "Download PDF",
        data=data,
        file_name=f"{(st.session_state.company.strip() or 'Brand')}_Brand_Bible.pdf",
        mime="application/pdf",
    )

    st.markdown('<div class="centerRow bigbtn">', unsafe_allow_html=True)
    if st.button("Start over"):
        st.session_state.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)

# Router
if st.session_state.view == "landing":
    landing()
elif st.session_state.view == "inputs":
    inputs()
elif st.session_state.view == "generate":
    generate()
else:
    done()
