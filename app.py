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
    page_title="Brand Bible | Strategic Atelier",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# REFINED LUXURY CSS (STABLE & RESPONSIVE)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
    
    /* GLOBAL RESET */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1d1d1f;
        background-color: #f5f5f7;
    }

    section[data-testid="stSidebar"] { display: none !important; }
    header, footer { visibility: hidden !important; }
    
    /* FIXING THE GIGANTIC WHITE SPACE */
    .block-container { 
        padding-top: 3rem; 
        padding-bottom: 5rem; 
        max-width: 1100px !important;
        margin: 0 auto;
    }

    /* ANIMATIONS */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(15px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-enter {
        animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    /* LANDING PAGE - LUXURY EDITORIAL STYLE */
    .landing-hero {
        text-align: center;
        padding: 100px 40px;
        background: #ffffff;
        border-radius: 32px;
        margin-bottom: 40px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.04);
    }
    .hero-eyebrow {
        font-size: 14px;
        font-weight: 600;
        color: #0071e3;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 16px;
    }
    .hero-title {
        font-size: 64px;
        font-weight: 700;
        letter-spacing: -2.5px;
        color: #1d1d1f;
        margin-bottom: 24px;
        line-height: 1.05;
    }
    .hero-subtitle {
        font-size: 22px;
        line-height: 1.5;
        font-weight: 400;
        color: #86868b;
        max-width: 700px;
        margin: 0 auto 48px auto;
    }
    
    .feature-row {
        display: flex;
        gap: 32px;
        margin-top: 60px;
        text-align: left;
        border-top: 1px solid #f2f2f5;
        padding-top: 40px;
    }
    .feature-col {
        flex: 1;
    }
    .feature-col h3 { font-size: 19px; font-weight: 600; margin-bottom: 12px; }
    .feature-col p { font-size: 15px; color: #6e6e73; line-height: 1.5; }

    /* THE WIZARD CARD */
    .wizard-card {
        background: #ffffff;
        border-radius: 32px;
        box-shadow: 0 24px 60px rgba(0,0,0,0.1);
        display: flex;
        overflow: hidden;
        min-height: 650px;
        border: 1px solid rgba(0,0,0,0.03);
    }
    
    .wizard-left {
        flex: 1.2;
        padding: 60px;
    }
    .wizard-right {
        flex: 1;
        background-color: #f0f0f2;
        background-size: cover;
        background-position: center;
    }

    /* FORM STYLING */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #fbfbfd !important;
        border: 1px solid #d2d2d7 !important;
        border-radius: 14px !important;
        padding: 14px 18px !important;
        font-size: 17px !important;
        color: #1d1d1f !important;
        transition: all 0.2s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #0071e3 !important;
        box-shadow: 0 0 0 4px rgba(0,113,227,0.12) !important;
        background-color: #ffffff !important;
    }
    label {
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #86868b !important;
        margin-bottom: 8px !important;
        letter-spacing: 0.2px;
    }

    /* BUTTONS */
    div.stButton > button {
        background-color: #0071e3;
        color: white;
        font-size: 17px;
        font-weight: 500;
        padding: 14px 32px;
        border-radius: 980px;
        border: none;
        box-shadow: 0 4px 12px rgba(0,113,227,0.25);
        transition: all 0.2s ease;
    }
    div.stButton > button:hover {
        background-color: #0077ED;
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(0,113,227,0.35);
    }
    
    .back-btn button {
        background-color: #f5f5f7 !important;
        color: #1d1d1f !important;
        box-shadow: none !important;
    }
    .demo-btn button {
        background-color: #e8f3ff !important;
        color: #0071e3 !important;
        border: 1px solid rgba(0,113,227,0.1) !important;
        box-shadow: none !important;
        font-size: 14px !important;
    }

    /* PROGRESS */
    .progress-dots { display: flex; gap: 10px; margin-bottom: 40px; }
    .dot { width: 10px; height: 10px; border-radius: 50%; background: #e5e5e5; }
    .dot.active { background: #0071e3; transform: scale(1.2); }

    /* TYPOGRAPHY */
    h2 { font-size: 38px; font-weight: 700; color: #1d1d1f; letter-spacing: -1px; margin-bottom: 12px; }
    .desc { font-size: 19px; color: #6e6e73; margin-bottom: 40px; line-height: 1.4; }
    .helper-link { font-size: 13px; color: #0071e3; text-decoration: none; margin-top: -10px; display: block; margin-bottom: 20px; }

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE & UTILS
# -----------------------------------------------------------------------------
if 'page' not in st.session_state: st.session_state.page = 'landing'
if 'step' not in st.session_state: st.session_state.step = 1
if 'payment_status' not in st.session_state: st.session_state.payment_status = False
if 'generated_bible' not in st.session_state: st.session_state.generated_bible = None

# Init data keys
keys = ['api_key', 'company_name', 'industry', 'url', 'enemy', 'origin', 'one_thing', 'archetype', 'style', 'voice']
for k in keys: 
    if k not in st.session_state: st.session_state[k] = ""

def next_step(): st.session_state.step += 1
def prev_step(): st.session_state.step -= 1

def fill_demo():
    st.session_state.company_name = "Oura Ring"
    st.session_state.industry = "Health Tech"
    st.session_state.enemy = "Passive Health Tracking"
    st.session_state.origin = "Founded in Finland to transform how we sleep and recover."
    st.session_state.one_thing = "Data that feels human, not clinical."
    st.session_state.archetype = "The Sage"
    st.session_state.style = "Swiss Minimalist"
    st.session_state.voice = "Jony Ive meets Brené Brown"

def sanitize_pdf_text(text):
    m = {'\u2018':"'", '\u2019':"'", '\u201c':'"', '\u201d':'"', '\u2013':'-', '\u2014':'--', '\u2026':'...', '—':'--', '’':"'"}
    for k, v in m.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

def create_pdf_report(text, company):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.cell(0, 10, f'{company.upper()} | BRAND STRATEGY', 0, 1, 'C')
    pdf = PDF(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=15); pdf.set_font("Arial", size=11)
    for line in text.split('\n'):
        s = sanitize_pdf_text(line)
        if line.startswith('# '): pdf.set_font("Arial", 'B', 16); pdf.ln(5); pdf.multi_cell(0, 10, s[2:]); pdf.ln(5); pdf.set_font("Arial", size=11)
        elif line.startswith('## '): pdf.set_font("Arial", 'B', 14); pdf.ln(3); pdf.multi_cell(0, 8, s[3:]); pdf.ln(3); pdf.set_font("Arial", size=11)
        else: pdf.multi_cell(0, 5, s)
    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# LANDING PAGE
# -----------------------------------------------------------------------------
if st.session_state.page == 'landing':
    st.markdown(f"""
    <div class="landing-hero animate-enter">
        <div class="hero-eyebrow">Strategic Intelligence</div>
        <div class="hero-title">The Operating System<br>for your Brand.</div>
        <div class="hero-subtitle">
            Most brands are messy and unaligned. We solve that. 
            Turn a few inputs into a comprehensive identity system. Strategy, Voice, and Visuals. Delivered.
        </div>
        <div class="feature-row">
            <div class="feature-col">
                <h3>The North Star</h3>
                <p>Define your Mission, Vision, and a rallying Manifesto that aligns your culture.</p>
            </div>
            <div class="feature-col">
                <h3>Verbal Identity</h3>
                <p>Lock in your voice. Specific tone guidelines and actionable taglines.</p>
            </div>
            <div class="feature-col">
                <h3>Visual Direction</h3>
                <p>Art direction briefs for designers. Colors, typography, and imagery defined.</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    _, btn_col, _ = st.columns([1,1,1])
    with btn_col:
        if st.button("Begin the Journey"):
            st.session_state.page = 'app'
            st.rerun()

# -----------------------------------------------------------------------------
# WIZARD APPLICATION
# -----------------------------------------------------------------------------
else:
    step_images = {
        1: "https://images.unsplash.com/photo-1497215728101-856f4ea42174?q=80&w=1000&auto=format&fit=crop",
        2: "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1000&auto=format&fit=crop",
        3: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1000&auto=format&fit=crop",
        4: "https://images.unsplash.com/photo-1563013544-824ae1b704d3?q=80&w=1000&auto=format&fit=crop",
        5: "https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?q=80&w=1000&auto=format&fit=crop"
    }
    
    st.markdown('<div class="wizard-card animate-enter">', unsafe_allow_html=True)
    
    # Left Panel: Logic & Forms
    with st.container():
        left, right = st.columns([1.2, 1], gap="large")
        
        with left:
            st.markdown('<div style="padding: 60px;">', unsafe_allow_html=True)
            
            # Progress Dots
            dots = "".join([f'<div class="dot {"active" if i == st.session_state.step else ""} "></div>' for i in range(1, 6)])
            st.markdown(f'<div class="progress-dots">{dots}</div>', unsafe_allow_html=True)
            
            if st.session_state.step == 1:
                st.markdown("<h2>The Foundation.</h2>", unsafe_allow_html=True)
                st.markdown('<p class="desc">Who is the entity we are building for? Let\'s start with the basics.</p>', unsafe_allow_html=True)
                
                c_name, c_demo = st.columns([3, 1])
                with c_name: st.text_input("Company Name", key="company_name", placeholder="e.g. Acme Corp")
                with c_demo: 
                    st.markdown('<div class="demo-btn" style="padding-top:28px;">', unsafe_allow_html=True)
                    if st.button("⚡ Demo"): fill_demo(); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                st.text_input("Industry", key="industry", placeholder="e.g. Health Tech")
                st.text_input("Gemini API Key", key="api_key", type="password")
                st.markdown('<a href="https://aistudio.google.com/app/apikey" target="_blank" class="helper-link">Get your free key here →</a>', unsafe_allow_html=True)
                
                if st.button("Continue"):
                    if st.session_state.api_key and st.session_state.company_name: next_step(); st.rerun()
                    else: st.warning("Company Name and API Key are mandatory.")

            elif st.session_state.step == 2:
                st.markdown("<h2>The Conflict.</h2>", unsafe_allow_html=True)
                st.markdown('<p class="desc">Every great brand stands against something. What is the villain in your story?</p>', unsafe_allow_html=True)
                
                st.text_input("The Enemy", key="enemy", placeholder="e.g. Complexity, Boredom")
                st.text_input("Origin Story", key="origin", placeholder="Briefly, how did this start?")
                st.text_input("Singular Value", key="one_thing", placeholder="The one thing you do better than anyone.")
                
                c1, c2 = st.columns([1,3])
                with c1: st.markdown('<div class="back-btn">', unsafe_allow_html=True); st.button("Back", on_click=prev_step); st.markdown('</div>', unsafe_allow_html=True)
                with c2: st.button("Continue", on_click=next_step)

            elif st.session_state.step == 3:
                st.markdown("<h2>The Persona.</h2>", unsafe_allow_html=True)
                st.markdown('<p class="desc">If your brand was a person, who would it be? Define the soul.</p>', unsafe_allow_html=True)
                
                st.selectbox("Archetype", ["The Sage", "The Creator", "The Ruler", "The Outlaw", "The Hero", "The Magician", "The Lover"], key="archetype")
                st.selectbox("Visual Style", ["Swiss Minimalist", "Luxury Serif", "Tech Modern", "Organic Warmth"], key="style")
                st.text_input("Voice Reference", key="voice", placeholder="e.g. Steve Jobs meets Tony Stark")
                
                c1, c2 = st.columns([1,3])
                with c1: st.markdown('<div class="back-btn">', unsafe_allow_html=True); st.button("Back", on_click=prev_step); st.markdown('</div>', unsafe_allow_html=True)
                with c2: st.button("Finalize Inputs", on_click=next_step)

            elif st.session_state.step == 4:
                st.markdown("<h2>Unlock Access.</h2>", unsafe_allow_html=True)
                st.markdown('<p class="desc">Your strategic blueprint is ready to be synthesized by the engine.</p>', unsafe_allow_html=True)
                
                st.markdown("""
                <div style="background: #f5f5f7; padding: 24px; border-radius: 20px; margin-bottom: 30px;">
                    <div style="font-size: 13px; font-weight: 600; color: #86868b; text-transform: uppercase;">Total</div>
                    <div style="font-size: 40px; font-weight: 700; color: #1d1d1f; letter-spacing: -1px;">$99.00</div>
                    <div style="font-size: 14px; color: #86868b; margin-top: 6px;">One-time strategic investment.</div>
                </div>
                """, unsafe_allow_html=True)
                
                if not st.session_state.payment_status:
                    if st.button("Secure Purchase"):
                        with st.spinner("Authorizing..."):
                            time.sleep(1.5)
                            st.session_state.payment_status = True
                            st.rerun()
                    st.markdown('<div class="back-btn" style="margin-top:10px;">', unsafe_allow_html=True); st.button("Back", on_click=prev_step); st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.success("Transaction Verified.")
                    st.button("Synthesize Brand Bible", on_click=next_step)

            elif st.session_state.step == 5:
                st.markdown("<h2>Synthesis.</h2>", unsafe_allow_html=True)
                st.markdown('<p class="desc">The engine is currently generating your asset.</p>', unsafe_allow_html=True)
                
                if not st.session_state.generated_bible:
                    genai.configure(api_key=st.session_state.api_key)
                    status = st.empty()
                    status.info("Processing neural nodes...")
                    
                    try:
                        prompt = f"""
                        Role: World-class Brand Strategist (Pentagram/Wolff Olins level).
                        Task: Create a Brand Bible for {st.session_state.company_name} ({st.session_state.industry}).
                        
                        Inputs: Enemy={st.session_state.enemy}, Origin={st.session_state.origin}, Value={st.session_state.one_thing},
                        Archetype={st.session_state.archetype}, Style={st.session_state.style}, Voice={st.session_state.voice}.
                        
                        Structure (Markdown):
                        # {st.session_state.company_name.upper()}
                        ## THE MANIFESTO
                        ## THE STRATEGY (Enemy, Insight, Position)
                        ## THE VERBAL IDENTITY (Voice, Tone, Taglines)
                        ## THE VISUAL DIRECTION (Color, Typography, Imagery)
                        """
                        status.info("Drafting Manifesto...")
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content(prompt)
                        st.session_state.generated_bible = response.text
                        status.empty()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                        if st.button("Retry"): st.rerun()
                
                if st.session_state.generated_bible:
                    st.success("Bible Generated Successfully.")
                    pdf = create_pdf_report(st.session_state.generated_bible, st.session_state.company_name)
                    st.download_button("Download Official PDF", pdf, f"{st.session_state.company_name}_Bible.pdf", "application/pdf")
                    st.markdown('<div class="back-btn" style="margin-top:20px;">', unsafe_allow_html=True); st.button("Start New Project", on_click=lambda: st.session_state.update({'step': 1, 'generated_bible': None})); st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)
            
        with right:
            # The Visual Background for the Card
            st.markdown(f"""
            <div style="
                height: 100%; min-height: 650px;
                background-image: url('{step_images[st.session_state.step]}');
                background-size: cover;
                background-position: center;
                border-left: 1px solid rgba(0,0,0,0.05);
            "></div>
            """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
