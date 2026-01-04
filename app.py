import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import requests
from bs4 import BeautifulSoup
import io
import time

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Brand Bible Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# MODERN SAAS CSS (CLEAN, USABLE, PROFESSIONAL)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* IMPORT INTER FONT (Standard for High-End Tech) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #111;
        background-color: #F5F7F9; /* Slight gray background for contrast */
    }

    /* REMOVE DEFAULT STREAMLIT PADDING */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* HIDE SIDEBAR & HEADER */
    section[data-testid="stSidebar"] { display: none !important; }
    header { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    
    /* HEADER STYLES */
    .main-header {
        background: white;
        padding: 1.5rem 2rem;
        border-bottom: 1px solid #E5E7EB;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .main-header h1 {
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.025em;
    }
    .status-badge {
        background: #DEF7EC;
        color: #03543F;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 500;
    }

    /* CARD CONTAINERS */
    .panel-container {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .panel-header {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #F3F4F6;
        color: #111;
    }

    /* INPUT FIELDS - CLEAN & VISIBLE */
    .stTextInput label, .stTextArea label, .stSelectbox label {
        font-size: 0.875rem;
        font-weight: 500;
        color: #374151;
    }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 6px !important;
        padding: 0.5rem 0.75rem !important;
        font-size: 0.95rem;
        color: #111;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
    }

    /* BUTTONS - STRIPE STYLE */
    div.stButton > button {
        background-color: #111827; /* Dark Gray/Black */
        color: white;
        border: 1px solid #111827;
        border-radius: 6px;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        font-size: 0.95rem;
        width: 100%;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #374151;
        border-color: #374151;
    }
    
    /* PREVIEW AREA */
    .preview-placeholder {
        background: #F9FAFB;
        border: 2px dashed #E5E7EB;
        border-radius: 8px;
        height: 300px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #9CA3AF;
        text-align: center;
        flex-direction: column;
    }

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# LOGIC
# -----------------------------------------------------------------------------

def sanitize_text_for_pdf(text):
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--', '\u2026': '...', '\u2022': '*',
        '—': '--', '’': "'", '“': '"', '”': '"'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def scrape_website_text(url):
    if not url: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for script in soup(["script", "style", "nav", "footer"]): script.extract()
        text = soup.get_text(separator=' ')
        return text[:4000]
    except Exception: return None

def create_pdf(content, company_name):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, f'{company_name} - Brand Bible', 0, 1, 'L')
            self.line(10, 20, 200, 20)
            self.ln(15)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, 'Generated by Brand Bible App', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    lines = content.split('\n')
    for line in lines:
        s_line = sanitize_text_for_pdf(line)
        if line.startswith('###') or line.startswith('**'):
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.multi_cell(0, 8, s_line.replace('#', '').replace('*', '').strip())
        elif line.startswith('##'):
            pdf.ln(8)
            pdf.set_font("Arial", 'B', 16)
            pdf.multi_cell(0, 10, s_line.replace('#', '').strip())
            pdf.ln(2)
        elif line.startswith('#'):
            pdf.set_font("Arial", 'B', 24)
            pdf.multi_cell(0, 15, s_line.replace('#', '').strip())
            pdf.ln(10)
        else:
            pdf.set_font("Arial", size=11)
            pdf.multi_cell(0, 6, s_line)
            
    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# SESSION STATE
# -----------------------------------------------------------------------------
if 'payment_status' not in st.session_state: st.session_state['payment_status'] = False
if 'generated_bible' not in st.session_state: st.session_state['generated_bible'] = None

# -----------------------------------------------------------------------------
# UI LAYOUT
# -----------------------------------------------------------------------------

# Top Header
st.markdown("""
<div class="main-header">
    <h1>Brand Bible Generator</h1>
    <div class="status-badge">v2.0 Stable</div>
</div>
""", unsafe_allow_html=True)

col_form, col_preview = st.columns([1.5, 1], gap="large")

with col_form:
    st.markdown('<div class="panel-container">', unsafe_allow_html=True)
    st.markdown('<div class="panel-header">1. Company Details</div>', unsafe_allow_html=True)
    
    api_key = st.text_input("Gemini API Key", type="password", help="Required for generation")
    
    c1, c2 = st.columns(2)
    with c1:
        company_name = st.text_input("Company Name", placeholder="e.g. Acme Inc")
    with c2:
        industry = st.text_input("Industry", placeholder="e.g. FinTech")
        
    url = st.text_input("Website URL", placeholder="https:// (Optional - we will read your site)")
    
    st.markdown('<div class="panel-header" style="margin-top: 2rem;">2. Strategy & Positioning</div>', unsafe_allow_html=True)
    
    enemy = st.text_input("The Enemy", placeholder="What are you fighting against? (e.g. 'Complexity')")
    origin_story = st.text_area("Origin Story", placeholder="How did this start?", height=100)
    one_thing = st.text_input("Value Proposition", placeholder="The one thing you do better than anyone else")
    
    st.markdown('<div class="panel-header" style="margin-top: 2rem;">3. Brand Voice & Style</div>', unsafe_allow_html=True)
    
    c3, c4 = st.columns(2)
    with c3:
        archetype = st.selectbox("Archetype", ["The Sage", "The Ruler", "The Creator", "The Outlaw", "The Magician", "The Hero", "The Lover", "The Jester"])
    with c4:
        aesthetic = st.selectbox("Visual Style", ["Minimalist", "Bold / Brutalist", "Luxury / Serif", "Playful / Pop", "Corporate / Trust"])
        
    voice_match = st.text_input("Celebrity Voice", placeholder="e.g. Ryan Reynolds meets Steve Jobs")
    
    st.markdown('</div>', unsafe_allow_html=True) # End Panel

with col_preview:
    st.markdown('<div class="panel-container">', unsafe_allow_html=True)
    st.markdown('<div class="panel-header">Output Preview</div>', unsafe_allow_html=True)

    if not st.session_state['payment_status']:
        st.markdown("""
        <div class="preview-placeholder">
            <div style="font-size: 2rem; margin-bottom: 1rem;">🔒</div>
            <div style="font-weight: 600; color: #374151;">Preview Locked</div>
            <div style="font-size: 0.9rem;">Complete payment to generate document</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("Includes: Manifesto, Voice Guidelines, Visual Brief, PDF Download.")
        
        if st.button("Unlock & Generate ($99)"):
            with st.spinner("Processing secure payment..."):
                time.sleep(1)
                st.session_state['payment_status'] = True
                st.rerun()
    
    else:
        # UNLOCKED STATE
        st.success("Access Granted")
        
        if st.button("Generate Brand Bible", type="primary"):
            if not api_key:
                st.error("Please enter your API Key in Section 1")
            else:
                genai.configure(api_key=api_key)
                
                with st.spinner("Analyzing strategy..."):
                    # Scrape
                    web_context = ""
                    if url:
                        with st.spinner("Reading website..."):
                            web_data = scrape_website_text(url)
                            if web_data: web_context = f"WEBSITE CONTENT: {web_data}"
                    
                    # Generate
                    prompt = f"""
                    Role: Senior Brand Strategist.
                    Task: Create a comprehensive Brand Bible.
                    
                    Client: {company_name} ({industry})
                    Context: {web_context}
                    
                    Strategy Inputs:
                    - Enemy: {enemy}
                    - Origin: {origin_story}
                    - One Thing: {one_thing}
                    - Archetype: {archetype}
                    - Style: {aesthetic}
                    - Voice: {voice_match}
                    
                    Output Requirements (Markdown):
                    1. THE NORTH STAR (Mission, Vision, Manifesto)
                    2. THE STRATEGY (Enemy, Insight, Position)
                    3. VERBAL IDENTITY (Voice, Tone, Taglines)
                    4. VISUAL DIRECTION (Color theory, Typography, Imagery)
                    """
                    
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        resp = model.generate_content(prompt)
                        st.session_state['generated_bible'] = resp.text
                    except Exception as e:
                        st.error(f"Error: {e}")

        if st.session_state['generated_bible']:
            st.markdown("---")
            st.markdown(st.session_state['generated_bible'])
            
            # PDF Button
            pdf_bytes = create_pdf(st.session_state['generated_bible'], company_name)
            st.download_button(
                label="Download PDF Report",
                data=pdf_bytes,
                file_name=f"{company_name}_Brand_Bible.pdf",
                mime="application/pdf"
            )

    st.markdown('</div>', unsafe_allow_html=True) # End Panel
