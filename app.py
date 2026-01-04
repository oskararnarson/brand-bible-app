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
    page_title="BRAND BIBLE | ATELIER",
    page_icon="⚜️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# LUXURY MINIMALIST CSS
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* IMPORT LUXURY FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Lato:wght@300;400&display=swap');
    
    :root {
        --primary: #1A1A1A;
        --accent: #D4AF37; /* Gold */
        --bg: #FAFAFA;
        --text: #333333;
    }

    html, body, [class*="css"] {
        font-family: 'Lato', sans-serif;
        font-weight: 300;
        color: var(--text);
        background-color: var(--bg);
    }

    /* FORCE HIDE SIDEBAR & HEADER */
    section[data-testid="stSidebar"] { display: none !important; }
    header { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    
    /* MAIN CONTAINER */
    .stApp {
        background-color: var(--bg);
    }

    /* TYPOGRAPHY */
    h1, h2, h3 {
        font-family: 'Playfair Display', serif !important;
        color: var(--primary) !important;
        font-weight: 400 !important;
        letter-spacing: -0.5px;
    }
    
    .hero-title {
        font-family: 'Playfair Display', serif;
        font-size: 4rem;
        text-align: center;
        margin-top: 2rem;
        margin-bottom: 0.5rem;
        color: #000;
    }
    
    .hero-sub {
        text-align: center;
        font-family: 'Lato', sans-serif;
        font-size: 0.9rem;
        color: #666;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 4rem;
        border-bottom: 1px solid #ddd;
        padding-bottom: 2rem;
        width: 60%;
        margin-left: auto;
        margin-right: auto;
    }

    /* INPUTS - MINIMALIST 'GHOST' STYLE */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: transparent !important;
        border: none !important;
        border-bottom: 1px solid #ccc !important;
        border-radius: 0px !important;
        padding: 10px 0px !important;
        font-family: 'Lato', sans-serif;
        font-size: 15px;
        transition: border-color 0.3s;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-bottom: 1px solid var(--primary) !important;
        box-shadow: none !important;
    }
    /* Hide label usually, but for accessibility we keep it small */
    .stMarkdown label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #999;
    }

    /* BUTTONS - ELEGANT EDITORIAL */
    div.stButton > button {
        background-color: var(--primary);
        color: #fff;
        border: none;
        border-radius: 0px;
        padding: 1rem 2rem;
        font-family: 'Lato', sans-serif;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-size: 11px;
        font-weight: 400;
        transition: all 0.4s ease;
        margin-top: 20px;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #444;
        letter-spacing: 3px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }
    
    /* CARDS/PANELS */
    .glass-panel {
        background: #fff;
        padding: 40px;
        box-shadow: 0 20px 40px -10px rgba(0,0,0,0.03);
        border: 1px solid rgba(0,0,0,0.02);
        margin-bottom: 2rem;
    }
    
    /* EXPANDERS - CLEAN */
    .stExpander {
        border: none !important;
        box-shadow: none !important;
        background-color: transparent !important;
        border-bottom: 1px solid #eee !important;
    }
    .streamlit-expanderHeader {
        font-family: 'Playfair Display', serif;
        font-size: 1.1rem;
        color: #333;
        background-color: transparent !important;
        padding-left: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
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
            self.set_font('Times', '', 10)
            self.set_text_color(100, 100, 100)
            self.cell(0, 10, f'EST. 2024  |  {company_name.upper()}  |  STRATEGIC DOCUMENT', 0, 1, 'C')
            self.ln(10)
        def footer(self):
            self.set_y(-20)
            self.set_font('Times', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, 'CONFIDENTIAL', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    
    lines = content.split('\n')
    for line in lines:
        s_line = sanitize_text_for_pdf(line)
        if line.startswith('###') or line.startswith('**'):
            pdf.ln(8)
            pdf.set_font("Times", 'B', 11)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6, s_line.replace('#', '').replace('*', '').strip().upper())
        elif line.startswith('##'):
            pdf.add_page()
            pdf.set_font("Times", '', 24)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 15, s_line.replace('#', '').strip())
            pdf.ln(10)
        elif line.startswith('#'):
            pdf.set_font("Times", '', 40)
            pdf.multi_cell(0, 20, s_line.replace('#', '').strip(), align='C')
            pdf.ln(20)
        else:
            pdf.set_font("Times", '', 11)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 6, s_line)
            
    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# SESSION STATE
# -----------------------------------------------------------------------------
if 'payment_status' not in st.session_state: st.session_state['payment_status'] = False
if 'generated_bible' not in st.session_state: st.session_state['generated_bible'] = None

# -----------------------------------------------------------------------------
# MAIN LAYOUT
# -----------------------------------------------------------------------------

# HERO
st.markdown("""
<div class="hero-title">The Brand Bible.</div>
<div class="hero-sub">The Strategic Atelier for Modern Business</div>
""", unsafe_allow_html=True)

# LAYOUT: LEFT (INPUTS) | RIGHT (OUTPUT/ACTION)
col_inputs, col_action = st.columns([1.2, 1], gap="large")

with col_inputs:
    st.markdown("### I. Configuration")
    
    with st.expander("The Entity", expanded=True):
        api_key = st.text_input("Gemini API Key", type="password")
        company_name = st.text_input("Company Name")
        industry = st.text_input("Industry")
        url = st.text_input("Digital Presence (URL)")

    with st.expander("The Strategy"):
        enemy = st.text_input("The Adversary (Enemy)")
        origin_story = st.text_area("Origin Story")
        one_thing = st.text_input("Singular Value Proposition")

    with st.expander("The Psychology"):
        fears_desires = st.text_area("Client Fears & Desires")
        archetype = st.selectbox("Archetype", ["The Sage", "The Ruler", "The Creator", "The Outlaw", "The Magician", "The Hero", "The Lover"])
        feeling = st.text_input("Emotive Response")

    with st.expander("The Aesthetic"):
        aesthetic = st.selectbox("Visual Direction", ["Minimalist / Swiss", "Editorial / Serif", "Industrial / Brutalist", "Warm / Organic"])
        voice_match = st.text_input("Voice Persona")
        taboo_words = st.text_input("Restricted Vocabulary")

with col_action:
    st.markdown("### II. Acquisition")
    
    st.markdown("""
    <div class="glass-panel">
        <h3 style="margin-top:0;">The Deliverable</h3>
        <p style="font-size: 14px; line-height: 1.6; color: #666;">
            A comprehensive strategic document defining the North Star, 
            verbal identity, and visual direction of the entity. 
            Delivered in professional PDF format.
        </p>
        <br>
    """, unsafe_allow_html=True)

    if not st.session_state['payment_status']:
        st.markdown("""
            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #eee; padding-top: 20px;">
                <span style="font-family: 'Playfair Display'; font-size: 1.5rem;">$99.00</span>
                <span style="font-size: 10px; color: #999; letter-spacing: 1px;">SECURE CHECKOUT</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Purchase Access"):
            with st.spinner("Processing..."):
                time.sleep(1.5)
                st.session_state['payment_status'] = True
                st.rerun()
    else:
        st.markdown("""
            <div style="border-top: 1px solid #eee; padding-top: 20px;">
                <span style="font-size: 12px; color: #D4AF37; letter-spacing: 1px;">● ACCESS GRANTED</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Generate Strategy"):
            if not api_key:
                st.error("Authentication Required: Please provide API Key in Configuration.")
            else:
                genai.configure(api_key=api_key)
                with st.spinner("Synthesizing..."):
                    web_context = ""
                    if url:
                        web_data = scrape_website_text(url)
                        if web_data: web_context = f"DIGITAL CONTEXT: {web_data}"

                    prompt = f"""
                    Act as a high-end Brand Strategist.
                    Client: {company_name}. Industry: {industry}.
                    Context: {web_context}
                    Strategy: Enemy={enemy}, Origin={origin_story}, Value={one_thing}.
                    Psych: Fears/Desires={fears_desires}, Archetype={archetype}, Feeling={feeling}.
                    Style: {aesthetic}, Voice={voice_match}, Avoid={taboo_words}.
                    
                    Create a Brand Bible (Markdown).
                    # {company_name.upper()}
                    ## MANIFESTO
                    ## VERBAL IDENTITY
                    ## VISUAL DIRECTION
                    """
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        resp = model.generate_content(prompt)
                        st.session_state['generated_bible'] = resp.text
                    except Exception as e:
                        st.error(f"Error: {e}")

        if st.session_state['generated_bible']:
            st.divider()
            st.markdown(st.session_state['generated_bible'])
            pdf = create_pdf(st.session_state['generated_bible'], company_name)
            st.download_button("Download PDF Document", pdf, "brand_bible.pdf", "application/pdf")
