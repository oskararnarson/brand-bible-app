import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import requests
from bs4 import BeautifulSoup
import time

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Brand Bible Generator",
    page_icon="⚫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# AGENCY-GRADE CSS (SWISS STYLE / BRUTALIST MINIMALISM)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* IMPORT FONTS: Inter (Modern Swiss) & Playfair (Editorial) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;900&family=Playfair+Display:ital,wght@1,400&display=swap');
    
    /* GLOBAL RESET */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #000000;
        background-color: #ffffff;
    }

    /* HIDE CHROME */
    section[data-testid="stSidebar"] { display: none !important; }
    header { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    #MainMenu { visibility: hidden !important; }
    .block-container { padding-top: 5rem; padding-bottom: 5rem; max-width: 800px !important; }

    /* TYPOGRAPHY - MASSIVE & STARK */
    h1 {
        font-family: 'Inter', sans-serif;
        font-weight: 900 !important;
        font-size: 4.5rem !important;
        letter-spacing: -3px !important;
        line-height: 0.9 !important;
        text-transform: uppercase;
        margin-bottom: 0.5rem !important;
        color: #000 !important;
    }
    h2 {
        font-family: 'Playfair Display', serif;
        font-style: italic;
        font-weight: 400 !important;
        font-size: 2rem !important;
        margin-bottom: 3rem !important;
        color: #444 !important;
        border-left: 2px solid #000;
        padding-left: 20px;
    }
    p {
        font-size: 1.1rem;
        line-height: 1.6;
        color: #111;
        font-weight: 300;
    }

    /* INPUTS - EDITORIAL STYLE (No Boxes, Just Lines) */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: transparent !important;
        border: none !important;
        border-bottom: 3px solid #000 !important;
        border-radius: 0px !important;
        padding: 1rem 0rem !important;
        font-size: 1.5rem !important;
        font-weight: 600 !important;
        color: #000 !important;
        font-family: 'Inter', sans-serif;
        caret-color: #000;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-bottom: 3px solid #000 !important;
        box-shadow: none !important;
        background-color: #FAFAFA !important;
    }
    /* Hide Labels visually but keep for accessibility - moving them above like kicker text */
    label {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.75rem !important;
        font-weight: 900 !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        color: #999 !important;
        margin-bottom: 0px !important;
    }

    /* BUTTONS - HIGH CONTRAST AGENCY STYLE */
    div.stButton > button {
        background-color: #000000;
        color: #ffffff;
        border: 1px solid #000;
        border-radius: 0px; /* Sharp edges */
        padding: 1rem 3rem;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        transition: all 0.3s ease;
        margin-top: 3rem;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #fff;
        color: #000;
        border: 1px solid #000;
        transform: none;
    }

    /* PROGRESS - MINIMAL */
    .step-indicator {
        position: fixed;
        top: 2rem;
        left: 2rem;
        font-size: 0.7rem;
        font-weight: 900;
        letter-spacing: 1px;
        color: #ccc;
        transform: rotate(0deg);
    }
    
    /* ANIMATIONS */
    @keyframes slideUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-in {
        animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    
    /* PAYMENT CARD MOCKUP */
    .black-card {
        background: #000;
        color: #fff;
        padding: 2rem;
        border-radius: 10px; /* Slight radius for card feel */
        margin-top: 2rem;
        box-shadow: 0 20px 40px -10px rgba(0,0,0,0.5);
    }

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# STATE MANAGEMENT
# -----------------------------------------------------------------------------
if 'step' not in st.session_state: st.session_state.step = 1
if 'payment_status' not in st.session_state: st.session_state.payment_status = False
if 'generated_bible' not in st.session_state: st.session_state.generated_bible = None

# Init keys
for key in ['api_key', 'company_name', 'industry', 'url', 'enemy', 'origin_story', 'one_thing', 'archetype', 'aesthetic', 'voice_match', 'generated_bible']:
    if key not in st.session_state: st.session_state[key] = ""

# -----------------------------------------------------------------------------
# UTILITIES
# -----------------------------------------------------------------------------
def next_step(): st.session_state.step += 1
def prev_step(): st.session_state.step -= 1

def sanitize_text_for_pdf(text):
    replacements = {'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2013': '-', '—': '--'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def scrape_website_text(url):
    if not url: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(["script", "style"]): s.extract()
        return soup.get_text(separator=' ')[:4000]
    except: return None

def create_pdf(content, company_name):
    class PDF(FPDF):
        def header(self):
            # Minimalist Header
            self.set_font('Arial', 'B', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'{company_name.upper()}  |  STRATEGIC BIBLE', 0, 1, 'R')
            self.ln(10)
    
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(True, 25)
    pdf.set_margins(20, 20, 20)
    
    lines = content.split('\n')
    for line in lines:
        s = sanitize_text_for_pdf(line)
        if line.startswith('###') or line.startswith('**'):
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6, s.replace('#','').replace('*','').strip().upper())
        elif line.startswith('##'):
            pdf.add_page() # New page for major sections
            pdf.set_font("Arial", 'B', 24)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 15, s.replace('#','').strip().upper())
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(10)
        elif line.startswith('#'):
            pdf.set_font("Arial", 'B', 40)
            pdf.multi_cell(0, 20, s.replace('#','').strip().upper())
            pdf.ln(20)
        else:
            pdf.set_font("Arial", '', 11)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 7, s)
            
    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# APP FLOW (SINGLE COLUMN FOCUS)
# -----------------------------------------------------------------------------

# Fixed Step Indicator
st.markdown(f'<div class="step-indicator">PHASE 0{st.session_state.step} / 05</div>', unsafe_allow_html=True)

# 1. THE FOUNDATION
if st.session_state.step == 1:
    st.markdown('<div class="animate-in">', unsafe_allow_html=True)
    st.markdown("<h1>The Entity</h1>")
    st.markdown("<h2>Establish the subject.</h2>")
    
    st.text_input("API Key", key="api_key", type="password", help="Gemini Key")
    st.text_input("Name", key="company_name", placeholder="ACME")
    st.text_input("Industry", key="industry", placeholder="AEROSPACE")
    st.text_input("Digital Context (URL)", key="url", placeholder="HTTPS://")
    
    if st.button("INITIATE STRATEGY"):
        if st.session_state.api_key and st.session_state.company_name:
            next_step()
            st.rerun()
        else:
            st.error("IDENTIFICATION REQUIRED")
    st.markdown('</div>', unsafe_allow_html=True)

# 2. THE CONFLICT
elif st.session_state.step == 2:
    st.markdown('<div class="animate-in">', unsafe_allow_html=True)
    st.markdown("<h1>The Conflict</h1>")
    st.markdown("<h2>Great brands fight for something.</h2>")
    
    st.text_input("The Enemy", key="enemy", placeholder="STAGNATION")
    st.text_area("The Origin", key="origin_story", placeholder="STARTED IN A BASEMENT...", height=100)
    st.text_input("The Singular Value", key="one_thing", placeholder="SPEED")
    
    col1, col2 = st.columns(2)
    with col1: 
        if st.button("BACK"): prev_step(); st.rerun()
    with col2: 
        if st.button("NEXT"): next_step(); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 3. THE IDENTITY
elif st.session_state.step == 3:
    st.markdown('<div class="animate-in">', unsafe_allow_html=True)
    st.markdown("<h1>The Persona</h1>")
    st.markdown("<h2>If the brand spoke, how would it sound?</h2>")
    
    st.selectbox("Archetype", 
        ["The Sage", "The Ruler", "The Creator", "The Outlaw", "The Magician", "The Hero", "The Lover", "The Jester", "The Caregiver"],
        key="archetype")
    
    st.selectbox("Aesthetic", 
        ["Swiss International", "Neo-Brutalist", "Luxury Serif", "Tech Minimalist", "Corporate Trust", "Organic Warmth"],
        key="aesthetic")
        
    st.text_input("Voice Reference", key="voice_match", placeholder="HEMINGWAY MEETS ELON")
    
    col1, col2 = st.columns(2)
    with col1: 
        if st.button("BACK"): prev_step(); st.rerun()
    with col2: 
        if st.button("FINALIZE"): next_step(); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 4. THE GATE
elif st.session_state.step == 4:
    st.markdown('<div class="animate-in">', unsafe_allow_html=True)
    st.markdown("<h1>Acquisition</h1>")
    st.markdown("<h2>Unlock the strategic intelligence engine.</h2>")
    
    st.markdown(f"""
    <div class="black-card">
        <div style="font-size: 0.8rem; opacity: 0.7; margin-bottom: 2rem;">TOTAL AMOUNT</div>
        <div style="font-size: 3rem; font-weight: 700; margin-bottom: 2rem;">$99.00</div>
        <div style="border-top: 1px solid #333; padding-top: 1rem; font-size: 0.8rem; letter-spacing: 1px;">
            INCLUDES MANIFESTO, VOICE, VISUAL DIRECTION
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.payment_status:
        if st.button("AUTHORIZE PAYMENT"):
            with st.spinner("AUTHENTICATING..."):
                time.sleep(1.5)
                st.session_state.payment_status = True
                st.rerun()
        if st.button("BACK"): prev_step(); st.rerun()
    else:
        st.success("ACCESS GRANTED")
        if st.button("GENERATE BIBLE"):
            next_step()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 5. THE OUTPUT
elif st.session_state.step == 5:
    st.markdown('<div class="animate-in">', unsafe_allow_html=True)
    st.markdown("<h1>The Bible</h1>")
    
    if not st.session_state.generated_bible:
        genai.configure(api_key=st.session_state.api_key)
        
        with st.spinner("SYNTHESIZING STRATEGY..."):
            web_c = ""
            if st.session_state.url:
                web_c = scrape_website_text(st.session_state.url)
            
            prompt = f"""
            You are a Legendary Brand Strategist (Pentagram/Wolff Olins level).
            Client: {st.session_state.company_name} ({st.session_state.industry})
            Context: {web_c}
            
            Inputs:
            - Enemy: {st.session_state.enemy}
            - Origin: {st.session_state.origin_story}
            - One Thing: {st.session_state.one_thing}
            - Archetype: {st.session_state.archetype}
            - Aesthetic: {st.session_state.aesthetic}
            - Voice: {st.session_state.voice_match}
            
            OUTPUT: A Brand Bible in Markdown. Tone: Authoritative, Minimalist, Profound.
            Structure:
            # {st.session_state.company_name.upper()}
            ## 1. THE NORTH STAR (Manifesto, Mission, Vision)
            ## 2. THE STRATEGIC WEDGE (The Enemy, The Insight, The Edge)
            ## 3. VERBAL IDENTITY (Voice Guidelines, 3 Taglines, Vocabulary)
            ## 4. VISUAL DIRECTION (Art Direction, Typography Brief, Imagery)
            """
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                st.session_state.generated_bible = response.text
                st.rerun()
            except Exception as e:
                st.error(f"ERROR: {e}")
                if st.button("RETRY"): st.rerun()

    if st.session_state.generated_bible:
        st.markdown(st.session_state.generated_bible)
        st.markdown("---")
        
        pdf_data = create_pdf(st.session_state.generated_bible, st.session_state.company_name)
        st.download_button(
            label="DOWNLOAD PDF ASSET",
            data=pdf_data,
            file_name=f"{st.session_state.company_name}_STRATEGY.pdf",
            mime="application/pdf"
        )
        
        if st.button("RESET SYSTEM"):
            st.session_state.step = 1
            st.session_state.generated_bible = None
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
