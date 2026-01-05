import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from fpdf import FPDF
import concurrent.futures
import textwrap

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Brand Bible Generator",
    layout="wide",
)

# ------------------------------------------------------------------
# SESSION STATE
# ------------------------------------------------------------------
def ss(key, value):
    if key not in st.session_state:
        st.session_state[key] = value

ss("view", "landing")   # landing | wizard | generate | done
ss("company", "")
ss("industry", "")
ss("api_key", "")
ss("result", "")

# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------
def run_gemini(prompt: str) -> str:
    model = genai.GenerativeModel("gemini-1.5-flash")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(model.generate_content, prompt)
        resp = fut.result(timeout=30)
    return (resp.text or "").strip()

def make_pdf(text: str, name: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)

    for line in text.split("\n"):
        pdf.multi_cell(0, 6, line)

    return pdf.output(dest="S").encode("latin-1")

# ------------------------------------------------------------------
# LANDING (NO MARKDOWN, NO HTML LEAKS)
# ------------------------------------------------------------------
def render_landing():
    components.html(
        """
        <style>
          body { background:#0b0d11; color:white; font-family:Inter, sans-serif; }
          .wrap { max-width:900px; margin:80px auto; text-align:center; }
          h1 { font-size:56px; margin-bottom:16px; }
          p { color:#b5bdd6; font-size:18px; line-height:1.6; }
        </style>
        <div class="wrap">
          <h1>Make your brand bible feel designed.</h1>
          <p>
            A guided workflow that turns strategy, voice, and visual direction
            into a clean, client-ready PDF.
          </p>
        </div>
        """,
        height=420,
    )

    if st.button("Start"):
        st.session_state.view = "wizard"
        st.rerun()

# ------------------------------------------------------------------
# WIZARD
# ------------------------------------------------------------------
def render_wizard():
    st.header("Brand inputs")

    st.text_input("Brand name", key="company")
    st.text_input("Industry", key="industry")
    st.text_input("Gemini API key", key="api_key", type="password")

    if st.button("Generate brand bible"):
        if not st.session_state.company or not st.session_state.api_key:
            st.error("Brand name and API key are required.")
            return

        st.session_state.view = "generate"
        st.rerun()

# ------------------------------------------------------------------
# GENERATION
# ------------------------------------------------------------------
def render_generate():
    st.header("Generating…")
    st.caption("This will take ~10–20 seconds")

    if not st.session_state.api_key:
        st.error("Missing API key.")
        if st.button("Back"):
            st.session_state.view = "wizard"
            st.rerun()
        return

    genai.configure(api_key=st.session_state.api_key)

    prompt = f"""
    You are a senior brand strategist.

    Brand: {st.session_state.company}
    Industry: {st.session_state.industry}

    Create a short brand bible with:
    - Positioning
    - Messaging
    - Voice rules
    - Visual direction

    Be concrete. No fluff.
    """

    try:
        with st.spinner("Thinking…"):
            text = run_gemini(prompt)
            st.session_state.result = text
            st.session_state.view = "done"
            st.rerun()
    except Exception as e:
        st.error(str(e))
        if st.button("Back"):
            st.session_state.view = "wizard"
            st.rerun()

# ------------------------------------------------------------------
# DONE
# ------------------------------------------------------------------
def render_done():
    st.header("Your brand bible is ready")

    pdf = make_pdf(st.session_state.result, st.session_state.company)

    st.download_button(
        "Download PDF",
        data=pdf,
        file_name=f"{st.session_state.company}_Brand_Bible.pdf",
        mime="application/pdf",
    )

    if st.button("Start over"):
        st.session_state.clear()
        st.rerun()

# ------------------------------------------------------------------
# ROUTER
# ------------------------------------------------------------------
if st.session_state.view == "landing":
    render_landing()
elif st.session_state.view == "wizard":
    render_wizard()
elif st.session_state.view == "generate":
    render_generate()
elif st.session_state.view == "done":
    render_done()
