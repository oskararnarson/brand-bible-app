import time
import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import concurrent.futures


st.set_page_config(page_title="Brand Bible Generator", layout="wide", page_icon="◼")


def ss_init():
    defaults = {
        "view": "landing",
        "company": "",
        "industry": "",
        "api_key": "",
        "result_text": "",
        "model_used": "",
        "last_error": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.api_key:
        st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "") or ""


def reset_app_state(keep_api_key: bool = True):
    api_key = st.session_state.get("api_key", "")
    st.session_state.view = "landing"
    st.session_state.company = ""
    st.session_state.industry = ""
    st.session_state.result_text = ""
    st.session_state.model_used = ""
    st.session_state.last_error = ""
    if not keep_api_key:
        st.session_state.api_key = ""
        st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "") or ""
    else:
        st.session_state.api_key = api_key or (st.secrets.get("GEMINI_API_KEY", "") or "")


def go(view: str):
    st.session_state.view = view
    st.rerun()


def inject_css():
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial; }
.block-container { max-width: 1100px; padding-top: 2.4rem; padding-bottom: 3.2rem; }

h1, h2, h3 { letter-spacing: -0.02em; }
.smallNote { font-size: 12px; opacity: 0.75; }

div.stButton > button {
  border-radius: 14px;
  font-weight: 800;
  height: 46px;
  padding: 0 18px;
}

div.stTextInput input {
  border-radius: 12px;
}
</style>
""",
        unsafe_allow_html=True,
    )


def pdf_bytes(text: str) -> bytes:
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


def build_prompt(company: str, industry: str) -> str:
    company = company.strip()
    industry = industry.strip()
    return (
        "You are a senior brand strategist and editorial designer.\n\n"
        f"Brand: {company}\n"
        f"Industry: {industry}\n\n"
        "Write a brand bible in markdown with:\n"
        "1) Executive summary\n"
        "2) Positioning\n"
        "3) Messaging system (key messages and proof points)\n"
        "4) Voice rules (do say and do not say, with 6 example sentences)\n"
        "5) Visual direction (palette logic, typography intent, imagery rules, what to avoid)\n\n"
        "Be concrete. No fluff. No invented awards. If uncertain, present options.\n"
    )


def available_model_names() -> list[str]:
    models = []
    try:
        for m in genai.list_models():
            name = getattr(m, "name", "") or ""
            methods = getattr(m, "supported_generation_methods", None) or []
            if name and "generateContent" in methods:
                models.append(name)
    except Exception:
        return []
    return models


def choose_models_to_try() -> list[str]:
    preferred = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0",
        "gemini",
    ]

    avail = available_model_names()
    if not avail:
        return preferred

    chosen = []
    for p in preferred:
        for n in avail:
            if p in n and n not in chosen:
                chosen.append(n)

    for n in avail:
        if n not in chosen:
            chosen.append(n)

    return chosen


def gemini_generate_text(prompt: str, timeout_s: int = 35) -> tuple[str, str]:
    models_to_try = choose_models_to_try()
    last_err = None

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(model.generate_content, prompt)
                resp = fut.result(timeout=timeout_s)

            text = (getattr(resp, "text", "") or "").strip()
            if not text:
                raise RuntimeError("Empty response text.")
            return text, model_name

        except concurrent.futures.TimeoutError as e:
            last_err = RuntimeError(f"Timeout after {timeout_s} seconds.")
        except Exception as e:
            last_err = e

    raise RuntimeError(f"Generation failed. Last error: {last_err}")


def landing_view():
    st.title("Brand Bible Generator")
    st.caption("Streamlit + Gemini + PDF output")

    col1, col2 = st.columns([2, 1], gap="large")
    with col1:
        st.subheader("Make your brand bible feel designed")
        st.write(
            "A short workflow that produces a usable PDF. "
            "No HTML should appear as text. API key should work reliably."
        )
        st.write("")

        if st.button("Start"):
            go("inputs")

        st.write("")
        st.markdown('<div class="smallNote">Tip: set GEMINI_API_KEY in secrets.toml to avoid typing it.</div>', unsafe_allow_html=True)

    with col2:
        st.info(
            "Flow\n\n"
            "1) Inputs\n"
            "2) Generate\n"
            "3) Download PDF"
        )


def inputs_view():
    st.title("Brand inputs")

    st.text_input("Brand name", key="company", placeholder="Example: Oura")
    st.text_input("Industry", key="industry", placeholder="Example: Health tech")
    st.text_input("Gemini API key", key="api_key", type="password", placeholder="Paste your key")

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Back"):
            go("landing")
    with c2:
        if st.button("Generate brand bible"):
            if not st.session_state.company.strip():
                st.error("Brand name is required.")
                return
            if not st.session_state.api_key.strip():
                st.error("API key is required.")
                return
            go("generate")


def generate_view():
    st.title("Generating")

    api_key = (st.session_state.api_key or "").strip()
    if not api_key:
        st.error("Missing API key.")
        if st.button("Back to inputs"):
            go("inputs")
        return

    genai.configure(api_key=api_key)

    prompt = build_prompt(st.session_state.company, st.session_state.industry)

    st.session_state.last_error = ""
    st.session_state.result_text = ""
    st.session_state.model_used = ""

    with st.spinner("Working..."):
        try:
            t0 = time.time()
            text, model_used = gemini_generate_text(prompt, timeout_s=35)
            _ = time.time() - t0
            st.session_state.result_text = text
            st.session_state.model_used = model_used
            go("done")
        except Exception as e:
            st.session_state.last_error = str(e)

    st.error(st.session_state.last_error or "Generation failed.")
    if st.button("Back to inputs"):
        go("inputs")


def done_view():
    st.title("Ready")

    if not st.session_state.result_text:
        st.error("No output found.")
        if st.button("Back to inputs"):
            go("inputs")
        return

    with st.expander("Preview", expanded=False):
        st.markdown(st.session_state.result_text)

    pdf = pdf_bytes(st.session_state.result_text)
    company = (st.session_state.company or "Brand").strip() or "Brand"
    filename = f"{company}_Brand_Bible.pdf"

    st.download_button(
        "Download PDF",
        data=pdf,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True,
    )

    if st.session_state.model_used:
        st.caption(f"Model used: {st.session_state.model_used}")

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Start over"):
            reset_app_state(keep_api_key=True)
            st.rerun()
    with c2:
        if st.button("Change API key"):
            st.session_state.api_key = ""
            st.session_state.result_text = ""
            st.session_state.model_used = ""
            go("inputs")


def main():
    ss_init()
    inject_css()

    view = st.session_state.view
    if view == "landing":
        landing_view()
    elif view == "inputs":
        inputs_view()
    elif view == "generate":
        generate_view()
    else:
        done_view()


if __name__ == "__main__":
    main()
