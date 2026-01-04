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
    page_title="Brand Bible | Atelier",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# DEFINITIVE DESIGN SYSTEM (CLEAN, STABLE, LUXURY)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:ital,wght@0,600;1,600&display=swap');
    
    /* GLOBAL STYLES */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Inter", sans-serif;
        color: #1d1d1f;
        background-color: #ffffff;
    }

    /* HIDE STREAMLIT CHROME */
    section[data-testid="stSidebar"] { display: none !important; }
    header, footer { visibility: hidden !important; }
    
    /* STABLE APP CONTAINER */
    .block-container { 
        padding-top: 2rem; 
        padding-bottom: 2rem; 
        max-width: 1000px !important;
        margin: 0 auto;
    }

    /* ANIMATIONS */
    @keyframes slideUpFade {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-step {
        animation: slideUpFade 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    /* LANDING PAGE - THE PITCH */
    .landing-card {
        padding: 60px 40px;
        background: #fbfbfd;
        border-radius: 32px;
        text-align: center;
        border: 1px solid #f2f2f5;
    }
    .eyebrow {
        font-size: 13px;
        font-weight: 600;
        color: #0071e3;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 20px;
    }
    .hero-text {
        font-family: 'Playfair Display', serif;
        font-size: 52px;
        font-weight: 600;
        letter-spacing: -1.5px;
        line-height: 1.1;
        margin-bottom: 30px;
    }
    .sub-hero {
        font-size: 20px;
        color: #6e6e73;
        max-width: 600px;
        margin: 0 auto 50px auto;
        line-height: 1.5;
    }

    /* WIZARD INTERFACE */
    .atelier-card {
        background: #ffffff;
        border: 1px solid #e5e5e7;
        border-radius: 24px;
        display: flex;
        overflow: hidden;
        min-height: 600px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.04);
    }
    .atelier-left {
        flex: 1.2;
        padding: 50px;
        display: flex;
        flex-direction: column;
    }
    .atelier-right {
        flex: 1;
        background-color: #f5f5f7;
        background-size: cover;
        background-position: center;
        border-left: 1px solid #e5e5e7;
    }

    /* FORM STYLING */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important;
        border: 1px solid #d2d2d7 !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        font-size: 16px !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #0071e3 !important;
        box-shadow: 0 0 0 4px rgba(0,113,227,0.1) !important;
    }
    label {
        font-size: 11px !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #86868b !important;
        margin-bottom: 6px !important;
    }

    /* PREMIUM BUTTONS */
    div.stButton > button {
        background-color: #000000;
        color: white;
        font-size: 16px;
        font-weight: 500;
        padding: 12px 36px;
        border-radius: 980px;
        border: none;
        transition: all 0.2s;
        width: auto;
    }
    div.stButton > button:hover {
        background-color: #333333;
        transform: scale(1.02);
    }
    
    .secondary-btn button {
        background-color: #f5f5f7 !important;
        color: #1d1d1f !important;
    }

    /* NAVIGATION */
    .progress-bar { display: flex; gap: 8px; margin-bottom: 40px; }
    .step-dot { width: 8px; height: 8px; border-radius: 50%; background: #e5e5e7; }
    .step-dot.active { background: #000000; transform: scale(1.2); }

    h2 { font-family: 'Playfair Display', serif; font-size: 32px; font-weight: 600; margin-bottom: 12px; }
    .step-hint { font-size: 17px; color: #6e6e73; margin-bottom: 30px; line-height: 1.5; }
    .api-link { font-size: 12px; color: #0071e3; text-decoration: none; margin-top: -10px; display: block; margin-bottom: 20px; }

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CORE ENGINE
# -----------------------------------------------------------------------------
if 'page' not in st.session_state: st.session_state.page = 'landing'
if 'step' not in st.session_state: st.session_state.step = 1
if 'payment_verified' not in st.session_state: st.session_state.payment_verified = False
if 'final_asset' not in st.session_state: st.session_state.final_asset = None

# Input Store
for k in ['api_key', 'co_name', 'ind', 'url', 'foe', 'origin', 'edge', 'arch', 'style', 'voice']:
    if k not in st.session_state: st.session_state[k] = ""

def next_step(): st.session_state.step += 1
def prev_step(): st.session_state.step -= 1

def run_demo():
    st.session_state.co_name = "Oura"
    st.session_state.ind = "Health Technology"
    st.session_state.foe = "Passive data tracking"
    st.session_state.origin = "Founded in Finland to bring sleep health into the light."
    st.session_state.edge = "Bio-rhythmic empathy."
    st.session_state.arch = "The Caregiver"
    st.session_state.style = "Swiss Minimalist"
    st.session_state.voice = "Calm, Clinical, yet Human."

def sanitize_pdf(text):
    chars = {'\u2018':"'", '\u2019':"'", '\u201c':'"', '\u201d':'"', '\u2013':'-', '\u2014':'--', '\u2026':'...', '—':'--', '’':"'", '“':'"', '”':'"'}
    for k, v in chars.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

def export_to_pdf(text, name):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 9)
            self.set_text_color(180)
            self.cell(0, 10, f'{name.upper()} // BRAND STRATEGY DOCUMENT', 0, 1, 'R')
    pdf = PDF(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20); pdf.set_font("Arial", size=11)
    for line in text.split('\n'):
        s = sanitize_pdf(line)
        if line.startswith('# '): pdf.set_font("Arial", 'B', 18); pdf.ln(6); pdf.multi_cell(0, 10, s[2:]); pdf.ln(4); pdf.set_font("Arial", size=11)
        elif line.startswith('## '): pdf.set_font("Arial", 'B', 14); pdf.ln(4); pdf.multi_cell(0, 8, s[3:]); pdf.ln(2); pdf.set_font("Arial", size=11)
        else: pdf.multi_cell(0, 5, s); pdf.ln(1)
    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# LANDING PAGE
# -----------------------------------------------------------------------------
if st.session_state.page == 'landing':
    st.markdown("""
    <div class="landing-card animate-step">
        <div class="eyebrow">The Strategic Atelier</div>
        <div class="hero-text">Strategy is the difference<br>between a company and a brand.</div>
        <div class="sub-hero">
            Generic brands are forgettable. We help you define your North Star, your Verbal Identity, and your Visual Direction in a single sitting.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    _, c_btn, _ = st.columns([1,1,1])
    with c_btn:
        if st.button("Enter the Atelier"):
            st.session_state.page = 'app'
            st.rerun()

# -----------------------------------------------------------------------------
# ATELIER WIZARD
# -----------------------------------------------------------------------------
else:
    visuals = {
        1: "https://images.unsplash.com/photo-1497215728101-856f4ea42174?q=80&w=1000",
        2: "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1000",
        3: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1000",
        4: "https://images.unsplash.com/photo-1563013544-824ae1b704d3?q=80&w=1000",
        5: "https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?q=80&w=1000"
    }
    
    st.markdown('<div class="atelier-card animate-step">', unsafe_allow_html=True)
    l, r = st.columns([1.3, 1], gap="large")
    
    with l:
        st.markdown('<div style="padding: 10px 0px;">', unsafe_allow_html=True)
        # Progress
        dots = "".join([f'<div class="step-dot {"active" if i == st.session_state.step else ""} "></div>' for i in range(1, 6)])
        st.markdown(f'<div class="progress-bar">{dots}</div>', unsafe_allow_html=True)
        
        if st.session_state.step == 1:
            st.markdown("<h2>Identification.</h2>", unsafe_allow_html=True)
            st.markdown('<p class="step-hint">Great strategy starts with clear definitions. Who are we building for?</p>', unsafe_allow_html=True)
            
            c_n, c_d = st.columns([3, 1])
            with c_n: st.text_input("Entity Name", key="co_name", placeholder="ACME")
            with c_d: 
                st.markdown('<div style="padding-top:28px;">', unsafe_allow_html=True)
                if st.button("⚡ Quick Fill"): run_demo(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.text_input("Industry Segment", key="ind", placeholder="TECH / RETAIL")
            st.text_input("Gemini API Access Key", key="api_key", type="password")
            st.markdown('<a href="https://aistudio.google.com/app/apikey" target="_blank" class="api-link">Secure your Key from Google →</a>', unsafe_allow_html=True)
            
            if st.button("Advance"):
                if st.session_state.api_key and st.session_state.co_name: next_step(); st.rerun()
                else: st.warning("Identification and API Access required.")

        elif st.session_state.step == 2:
            st.markdown("<h2>The Conflict.</h2>", unsafe_allow_html=True)
            st.markdown('<p class="step-hint">Strong brands stand against the status quo. What is your adversary?</p>', unsafe_allow_html=True)
            
            st.text_input("The Adversary (Enemy)", key="foe", placeholder="e.g. COMPROMISE")
            st.text_input("Historical Context (Origin)", key="origin", placeholder="HOW DID THIS START?")
            st.text_input("The Singular Advantage", key="edge", placeholder="YOUR UNFAIR TRUTH")
            
            c1, c2 = st.columns([1,3])
            with c1: st.markdown('<div class="secondary-btn">', unsafe_allow_html=True); st.button("Back", on_click=prev_step); st.markdown('</div>', unsafe_allow_html=True)
            with c2: st.button("Advance", on_click=next_step)

        elif st.session_state.step == 3:
            st.markdown("<h2>The Persona.</h2>", unsafe_allow_html=True)
            st.markdown('<p class="step-hint">If your brand was a person, what soul would inhabit it?</p>', unsafe_allow_html=True)
            
            st.selectbox("Archetype", ["The Sage", "The Creator", "The Ruler", "The Outlaw", "The Hero", "The Magician"], key="arch")
            st.selectbox("Visual Ethos", ["Swiss Minimalist", "Luxury Serif", "Tech Modern", "Organic Warmth"], key="style")
            st.text_input("Vocal Reference", key="voice", placeholder="e.g. STEVE JOBS")
            
            c1, c2 = st.columns([1,3])
            with c1: st.markdown('<div class="secondary-btn">', unsafe_allow_html=True); st.button("Back", on_click=prev_step); st.markdown('</div>', unsafe_allow_html=True)
            with c2: st.button("Finalize Parameters", on_click=next_step)

        elif st.session_state.step == 4:
            st.markdown("<h2>Authorization.</h2>", unsafe_allow_html=True)
            st.markdown('<p class="step-hint">Authorize the strategic engine to synthesize your asset.</p>', unsafe_allow_html=True)
            
            st.markdown(f"""
            <div style="background: #fbfbfd; padding: 24px; border-radius: 20px; border: 1px solid #e5e5e7; margin-bottom: 30px;">
                <div style="font-size: 11px; font-weight: 700; color: #86868b; text-transform: uppercase;">Strategic Value</div>
                <div style="font-size: 40px; font-weight: 700; color: #1d1d1f; letter-spacing: -1.5px;">$99.00</div>
                <div style="font-size: 14px; color: #86868b; margin-top: 6px;">One-time authorization.</div>
            </div>
            """, unsafe_allow_html=True)
            
            if not st.session_state.payment_verified:
                if st.button("Authorize Purchase"):
                    with st.spinner("Processing..."):
                        time.sleep(1.2)
                        st.session_state.payment_verified = True
                        st.rerun()
                st.markdown('<div class="secondary-btn" style="margin-top:10px;">', unsafe_allow_html=True); st.button("Back", on_click=prev_step); st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.success("Authorized.")
                if st.button("Initialize Synthesis"): next_step(); st.rerun()

        elif st.session_state.step == 5:
            st.markdown("<h2>The Bible.</h2>", unsafe_allow_html=True)
            
            if not st.session_state.final_asset:
                genai.configure(api_key=st.session_state.api_key)
                status = st.empty()
                
                try:
                    prompt = f"""
                    Role: Senior Brand Strategist (Pentagram).
                    Client: {st.session_state.co_name} ({st.session_state.ind}).
                    Strategy: Enemy={st.session_state.foe}, Origin={st.session_state.origin}, Advantage={st.session_state.edge}.
                    Persona: Archetype={st.session_state.arch}, Style={st.session_state.style}, Voice={st.session_state.voice}.
                    
                    Output Markdown:
                    # {st.session_state.co_name.upper()}
                    ## MANIFESTO
                    ## THE STRATEGY
                    ## VERBAL IDENTITY
                    ## VISUAL DIRECTION
                    """
                    status.info("Drafting Manifesto...")
                    time.sleep(1)
                    status.info("Defining Verbal Identity...")
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(prompt)
                    st.session_state.final_asset = response.text
                    status.empty()
                    st.rerun()
                except Exception as e:
                    st.error(f"Synthesis Error: {e}")
                    if st.button("Reset Engine"): st.session_state.step = 1; st.rerun()
            
            if st.session_state.final_asset:
                st.success("Asset Synthesized.")
                pdf = export_to_pdf(st.session_state.final_asset, st.session_state.co_name)
                st.download_button("Download Official Strategy (PDF)", pdf, "Brand_Bible.pdf", "application/pdf")
                st.markdown('<div class="secondary-btn" style="margin-top:20px;">', unsafe_allow_html=True); st.button("New Project", on_click=lambda: st.session_state.update({'step': 1, 'final_asset': None})); st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
            
    with r:
        st.markdown(f"""
        <div style="
            height: 100%; min-height: 600px;
            background-image: url('{visuals[st.session_state.step]}');
            background-size: cover;
            background-position: center;
        "></div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
