import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import requests
from bs4 import BeautifulSoup
import io
import time

# -----------------------------------------------------------------------------
# CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Brand Bible | Strategic Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# "SWISS STUDIO" BRIGHT THEME
st.markdown("""
<style>
    /* IMPORT FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    /* GLOBAL STYLES */
    .stApp {
        background-color: #ffffff;
        color: #000000;
    }
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* TEXT OVERRIDES */
    h1, h2, h3, h4, h5, h6, .stMarkdown {
        color: #111111 !important;
    }
    p, li {
        color: #333333 !important;
    }
    
    /* HIDE STREAMLIT ELEMENTS */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* CUSTOM HERO SECTION */
    .hero-container {
        padding: 4rem 0 3rem 0;
        border-bottom: 2px solid #000;
        margin-bottom: 3rem;
        background-color: #fff;
    }
    .hero-title {
        font-size: 4.5rem;
        font-weight: 800;
        letter-spacing: -3px;
        line-height: 1;
        color: #000;
        margin-bottom: 1rem;
    }
    .hero-subtitle {
        font-size: 1.4rem;
        font-weight: 400;
        color: #555;
        max-width: 700px;
        line-height: 1.4;
    }
    
    /* SIDEBAR REFINEMENT */
    section[data-testid="stSidebar"] {
        background-color: #F7F9FC; /* Very subtle cool gray */
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 3rem;
    }
    
    /* FORM ELEMENTS - CLEAN & BRIGHT */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        border-radius: 6px;
        border: 1px solid #E2E8F0;
        background-color: #ffffff;
        color: #000;
        padding: 0.5rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #2563EB; /* Bright Blue Focus */
        box-shadow: 0 0 0 2px rgba(37,99,235,0.1);
    }
    
    /* ACCORDIONS */
    .stExpander {
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        background-color: #ffffff;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    
    /* BUTTONS */
    div.stButton > button {
        background-color: #000000;
        color: #ffffff;
        border-radius: 6px;
        border: none;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.2s ease;
        width: 100%;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    div.stButton > button:hover {
        background-color: #2563EB; /* Bright Blue Hover */
        color: #fff;
        transform: translateY(-1px);
    }
    div.stButton > button:active {
        transform: translateY(0px);
    }
    
    /* PAYMENT BUTTON STYLE override */
    div[data-testid="stVerticalBlock"] > div > div[data-testid="stButton"] > button {
        background-color: #2563EB; /* Primary Action Blue */
    }
    
    /* CARDS/CONTAINERS */
    .feature-card {
        background: #ffffff;
        padding: 2rem;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
    }
    .feature-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .feature-number {
        font-weight: 800;
        font-size: 1.2rem;
        color: #2563EB;
        margin-bottom: 0.5rem;
    }
    
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def sanitize_text_for_pdf(text):
    """
    Cleans text to ensure FPDF compatibility (Standard FPDF fonts are Latin-1).
    """
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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for script in soup(["script", "style", "nav", "footer"]): script.extract()
        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        return clean_text[:4000]
    except Exception: return None

def create_pdf(content, company_name):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.set_text_color(0, 0, 0)
            self.cell(0, 10, f'STRATEGIC DOCUMENT: {company_name.upper()}', 0, 1, 'R')
            self.ln(5)
            self.line(10, 25, 200, 25) # Top line
            self.ln(10)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, 'CONFIDENTIAL // BRAND BIBLE GENERATOR', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_text_color(0, 0, 0)
    
    lines = content.split('\n')
    for line in lines:
        s_line = sanitize_text_for_pdf(line)
        if line.startswith('###') or line.startswith('**'):
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.multi_cell(0, 8, s_line.replace('#', '').replace('*', '').strip())
        elif line.startswith('##'):
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 24)
            pdf.multi_cell(0, 12, s_line.replace('#', '').strip().upper())
            pdf.ln(2)
        elif line.startswith('#'):
            pdf.add_page()
            pdf.set_font("Arial", 'B', 36)
            pdf.multi_cell(0, 20, s_line.replace('#', '').strip().upper(), align='L')
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
# SIDEBAR: THE CONFIGURATOR
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<h3 style='margin-bottom:0px; letter-spacing: -1px; color: #000;'>⚙️ CONFIGURATION</h3>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 13px; color: #666; margin-bottom: 2rem;'>Input your parameters below.</p>", unsafe_allow_html=True)
    
    api_key = st.text_input("Google AI Key", type="password", help="Enter your Gemini API Key")
    
    # ORGANIZED ACCORDIONS
    with st.expander("1. IDENTITY CORE", expanded=True):
        company_name = st.text_input("Company Name", "Acme Corp")
        industry = st.text_input("Industry", "SaaS")
        url = st.text_input("Website (for context)", placeholder="https://")

    with st.expander("2. STRATEGIC POSITION"):
        enemy = st.text_input("The Enemy", placeholder="E.g. Boredom")
        origin_story = st.text_area("Origin Story", height=100)
        one_thing = st.text_input("The Single Value Prop")

    with st.expander("3. PSYCHOGRAPHICS"):
        fears_desires = st.text_area("Fears & Desires")
        archetype = st.selectbox("Archetype", ["The Rebel", "The Magician", "The Hero", "The Lover", "The Sage", "The Creator", "The Ruler"])
        feeling = st.text_input("Desired Feeling")

    with st.expander("4. AESTHETICS & VOICE"):
        aesthetic = st.selectbox("Style", ["Swiss Minimalist", "Brutalist", "Luxury Serif", "Tech Dark Mode"])
        colors_avoid = st.text_input("Colors to Avoid")
        voice_match = st.text_input("Celebrity Voice")
        taboo_words = st.text_input("Taboo Words")

# -----------------------------------------------------------------------------
# MAIN APP
# -----------------------------------------------------------------------------

# HERO SECTION
st.markdown("""
<div class="hero-container">
    <div class="hero-title">The Brand Bible.</div>
    <div class="hero-subtitle">Generative Strategic Intelligence. 
    Turn simple inputs into a complete verbal and visual identity system.</div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1], gap="large")

with col1:
    if not st.session_state['payment_status']:
        st.markdown("### The Deliverable")
        st.markdown("""
        <div class="feature-card">
            <div class="feature-number">01.</div>
            <strong>The North Star</strong><br>
            <span style="color:#555; font-size: 14px;">Mission, Vision, and a rallying Manifesto.</span>
        </div>
        <div class="feature-card">
            <div class="feature-number">02.</div>
            <strong>The Verbal Identity</strong><br>
            <span style="color:#555; font-size: 14px;">Voice guidelines, Taglines, and Hook points.</span>
        </div>
        <div class="feature-card">
            <div class="feature-number">03.</div>
            <strong>The Visual Direction</strong><br>
            <span style="color:#555; font-size: 14px;">Art Direction briefs for Designers (Logo, Type, Photo).</span>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        st.markdown("#### Ready to Start?")
        
        # Payment Flow
        pay_col, lock_col = st.columns([1,1])
        with pay_col:
            pay_btn = st.button("UNLOCK ACCESS - $99", type="primary")
        with lock_col:
            st.markdown("<div style='padding-top: 15px; color: #888; font-size: 13px;'>🔒 Secure SSL Connection</div>", unsafe_allow_html=True)

        if pay_btn:
            with st.spinner("Authenticating..."):
                time.sleep(1.5)
                st.session_state['payment_status'] = True
                st.rerun()

    else:
        # LOGIC FOR GENERATION
        st.success("✅ ACCESS GRANTED")
        st.markdown("---")
        
        if st.button("INITIALIZE GENERATION SEQUENCE"):
            if not api_key:
                st.error("⚠️ SYSTEM ERROR: API Key missing in Configurator.")
            else:
                genai.configure(api_key=api_key)
                
                with st.spinner("Connecting to Neural Engine..."):
                    # Scrape
                    web_context = ""
                    if url:
                        web_data = scrape_website_text(url)
                        if web_data: web_context = f"WEBSITE CONTEXT: {web_data}"

                    # Prompts
                    sys_prompt = "You are a Chief Brand Officer. Tone: Elite, Strategic, Brief. No fluff."
                    user_prompt = f"""
                    Generate Brand Bible for: {company_name} ({industry}).
                    Strategy: Fighting '{enemy}'. Origin: {origin_story}. Value: {one_thing}.
                    Psychology: Audience fears/desires: {fears_desires}. Archetype: {archetype}.
                    Style: {aesthetic}. Voice: {voice_match}. Avoid: {colors_avoid}, {taboo_words}.
                    {web_context}
                    
                    OUTPUT FORMAT (Markdown):
                    # BRAND BIBLE: {company_name.upper()}
                    ## 1. THE NORTH STAR
                    (Mission, Vision, Manifesto)
                    ## 2. THE PERSONA
                    (Psychographics)
                    ## 3. VERBAL IDENTITY
                    (Voice Rules, Taglines)
                    ## 4. VISUAL DIRECTION
                    (Art Direction Brief)
                    """
                    
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content(f"{sys_prompt}\n{user_prompt}")
                        st.session_state['generated_bible'] = response.text
                    except Exception as e:
                        st.error(f"Generation Failed: {e}")

        if st.session_state['generated_bible']:
            st.markdown(st.session_state['generated_bible'])
            pdf_bytes = create_pdf(st.session_state['generated_bible'], company_name)
            st.download_button("DOWNLOAD OFFICIAL PDF", pdf_bytes, f"{company_name}_Bible.pdf", "application/pdf")

with col2:
    if not st.session_state['payment_status']:
        st.markdown("""
        <div style="background: #F8F9FA; padding: 1.5rem; border: 1px solid #E2E8F0; border-radius: 8px;">
            <div style="font-size: 12px; font-weight: 700; margin-bottom: 15px; color: #999; letter-spacing: 1px;">RECENT GENERATIONS</div>
            <div style="margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #eee;">
                <strong>Oura Ring</strong><br>
                <span style="color: #666; font-size: 13px;">Tech / Wellness</span>
            </div>
            <div style="margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #eee;">
                <strong>Liquid Death</strong><br>
                <span style="color: #666; font-size: 13px;">Beverage / FMCG</span>
            </div>
            <div>
                <strong>MSCHF</strong><br>
                <span style="color: #666; font-size: 13px;">Art / eCommerce</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
