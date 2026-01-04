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
    page_title="Brand Bible",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# CSS SYSTEM
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1d1d1f;
        background-color: #f5f5f7;
    }

    section[data-testid="stSidebar"] { display: none !important; }
    header, footer { visibility: hidden !important; }
    
    .block-container { 
        padding-top: 2rem; 
        padding-bottom: 2rem; 
        max-width: 1200px !important;
        margin: 0 auto;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-enter {
        animation: fadeInUp 0.6s ease-out forwards;
    }

    /* LANDING HERO */
    .hero-container {
        text-align: center;
        padding: 80px 20px;
        background: white;
        border-radius: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 40px;
    }
    .hero-title {
        font-size: 56px;
        font-weight: 700;
        letter-spacing: -1.5px;
        color: #1d1d1f;
        margin-bottom: 20px;
        line-height: 1.1;
    }
    .hero-subtitle {
        font-size: 21px;
        line-height: 1.5;
        font-weight: 400;
        color: #86868b;
        max-width: 600px;
        margin: 0 auto 40px auto;
    }
    
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        margin-top: 40px;
        text-align: left;
    }
    .feature-item h3 { font-size: 18px; font-weight: 600; margin-bottom: 8px; }
    .feature-item p { font-size: 15px; color: #6e6e73; line-height: 1.4; }

    /* APP CARD */
    .app-card {
        background: #ffffff;
        border-radius: 24px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.08);
        overflow: hidden;
        border: 1px solid rgba(0,0,0,0.05);
        display: flex;
        min-height: 600px;
    }
    
    /* INPUTS */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important;
        border: 1px solid #d2d2d7 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        font-size: 16px !important;
        color: #1d1d1f !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        transition: all 0.2s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #0071e3 !important;
        box-shadow: 0 0 0 4px rgba(0,113,227,0.15) !important;
    }
    
    /* BUTTONS */
    div.stButton > button {
        background-color: #0071e3;
        color: white;
        font-size: 16px;
        font-weight: 500;
        padding: 12px 30px;
        border-radius: 999px;
        border: none;
        box-shadow: 0 2px 4px rgba(0,113,227,0.3);
        transition: transform 0.1s ease;
    }
    div.stButton > button:hover {
        background-color: #0077ED;
        transform: scale(1.02);
    }
    
    .secondary-btn button {
        background-color: #f5f5f7 !important;
        color: #1d1d1f !important;
        box-shadow: none !important;
    }
    
    .demo-btn button {
        background-color: #e8f3ff !important;
        color: #0071e3 !important;
        border: 1px solid rgba(0,113,227,0.2) !important;
        box-shadow: none !important;
    }

    h2 { font-size: 32px; font-weight: 600; margin-bottom: 8px; color: #1d1d1f; letter-spacing: -0.5px; }
    .step-desc { font-size: 17px; color: #6e6e73; margin-bottom: 32px; max-width: 90%; }
    .api-helper { font-size: 12px; color: #0071e3; margin-top: -10px; margin-bottom: 20px; text-decoration: none; display: inline-block; }
    
    /* PROGRESS */
    .progress-bar { display: flex; gap: 6px; margin-bottom: 30px; }
    .p-dot { width: 8px; height: 8px; border-radius: 50%; background: #e5e5e5; transition: 0.3s; }
    .p-dot.active { background: #1d1d1f; transform: scale(1.2); }

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE
# -----------------------------------------------------------------------------
if 'page' not in st.session_state: st.session_state.page = 'landing'
if 'step' not in st.session_state: st.session_state.step = 1
if 'payment_status' not in st.session_state: st.session_state.payment_status = False
if 'generated_bible' not in st.session_state: st.session_state.generated_bible = None

# Init Inputs
keys = ['api_key', 'company_name', 'industry', 'url', 'enemy', 'origin', 'one_thing', 'archetype', 'style', 'voice']
for k in keys: 
    if k not in st.session_state: st.session_state[k] = ""

# -----------------------------------------------------------------------------
# NAVIGATION & UTILS
# -----------------------------------------------------------------------------
def go_to_app(): st.session_state.page = 'app'; st.session_state.step = 1
def next_step(): st.session_state.step += 1
def prev_step(): st.session_state.step -= 1

def fill_demo_data():
    st.session_state.company_name = "Oura Ring"
    st.session_state.industry = "Wearable Health Tech"
    st.session_state.enemy = "Passive Tracking & Health Anxiety"
    st.session_state.origin = "Started in Finland to help people sleep better, not just count steps."
    st.session_state.one_thing = "Data that feels like a hug, not a spreadsheet."
    st.session_state.archetype = "The Caregiver"
    st.session_state.style = "Swiss Minimalist"
    st.session_state.voice = "Jony Ive meets Brené Brown"
    
def render_progress(current):
    html = '<div class="progress-bar">'
    for i in range(1, 6):
        active = 'active' if i == current else ''
        html += f'<div class="p-dot {active}"></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PDF ENGINE (ROBUST)
# -----------------------------------------------------------------------------
def sanitize_text_for_pdf(text):
    # Robust replacement map for common encoding issues
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--', '\u2026': '...', '\u2022': '*',
        '—': '--', '’': "'", '“': '"', '”': '"', '–': '-'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    
    # Force encode to Latin-1, replacing errors with ? instead of crashing
    return text.encode('latin-1', 'replace').decode('latin-1')

def create_pdf(text, company_name):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.cell(0, 10, f'{sanitize_text_for_pdf(company_name).upper()} | STRATEGIC BIBLE', 0, 1, 'C')
            self.ln(10)
    
    try:
        pdf = PDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=11)
        
        lines = text.split('\n')
        for line in lines:
            safe_line = sanitize_text_for_pdf(line)
            if line.startswith('# '):
                pdf.set_font("Arial", 'B', 16)
                pdf.ln(5)
                pdf.multi_cell(0, 8, safe_line.replace('#', '').strip())
                pdf.ln(5)
                pdf.set_font("Arial", size=11)
            elif line.startswith('## '):
                pdf.set_font("Arial", 'B', 14)
                pdf.ln(4)
                pdf.multi_cell(0, 7, safe_line.replace('#', '').strip())
                pdf.ln(2)
                pdf.set_font("Arial", size=11)
            elif line.startswith('### '):
                pdf.set_font("Arial", 'B', 12)
                pdf.multi_cell(0, 6, safe_line.replace('#', '').strip())
                pdf.set_font("Arial", size=11)
            else:
                pdf.multi_cell(0, 5, safe_line)
                pdf.ln(1)
                
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        return f"PDF Error: {str(e)}".encode('utf-8')

# -----------------------------------------------------------------------------
# PAGE 1: LANDING PAGE
# -----------------------------------------------------------------------------
if st.session_state.page == 'landing':
    st.markdown("""
    <div class="hero-container animate-enter">
        <div class="hero-eyebrow">Strategic Intelligence</div>
        <div class="hero-title">The Operating System<br>for your Brand.</div>
        <div class="hero-subtitle">
            Most brands are messy. We fix that.
            Turn a few simple inputs into a comprehensive identity system.<br>
            Strategy, Voice, and Visuals. Instantaneously.
        </div>
        
        <div class="feature-grid">
            <div class="feature-item">
                <h3>The North Star</h3>
                <p>Define your Mission, Vision, and a rallying Manifesto that aligns your team.</p>
            </div>
            <div class="feature-item">
                <h3>Verbal Identity</h3>
                <p>Lock in your voice. Get specific "We Say / We Don't Say" guidelines and taglines.</p>
            </div>
            <div class="feature-item">
                <h3>Visual Direction</h3>
                <p>Art direction briefs for designers. Colors, typography, and imagery defined.</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        if st.button("Begin Journey"):
            go_to_app()
            st.rerun()

# -----------------------------------------------------------------------------
# PAGE 2: WIZARD APP
# -----------------------------------------------------------------------------
else:
    # High-quality images for the right column
    step_images = {
        1: "https://images.unsplash.com/photo-1497215728101-856f4ea42174?q=80&w=1000&auto=format&fit=crop", # Office
        2: "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1000&auto=format&fit=crop", # Technology
        3: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1000&auto=format&fit=crop", # Abstract
        4: "https://images.unsplash.com/photo-1563013544-824ae1b704d3?q=80&w=1000&auto=format&fit=crop", # Money/Value
        5: "https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?q=80&w=1000&auto=format&fit=crop"  # Creative
    }
    current_img = step_images.get(st.session_state.step, step_images[1])

    # The Card Layout
    st.markdown('<div class="app-card animate-enter">', unsafe_allow_html=True)
    c_left, c_right = st.columns([1, 1], gap="large")
    
    with c_left:
        st.markdown('<div style="padding: 40px;">', unsafe_allow_html=True)
        render_progress(st.session_state.step)
        
        # --- STEP 1: ENTITY ---
        if st.session_state.step == 1:
            st.markdown("<h2>The Foundation.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">This is the bedrock. Who are we building this for?</div>', unsafe_allow_html=True)
            
            # DEMO BUTTON
            c_input, c_demo = st.columns([3, 1])
            with c_input:
                st.text_input("Company Name", key="company_name", placeholder="e.g. Acme Inc")
            with c_demo:
                st.markdown('<div class="demo-btn">', unsafe_allow_html=True)
                if st.button("⚡ Quick Fill"):
                    fill_demo_data()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            st.text_input("Industry", key="industry", placeholder="e.g. Aerospace")
            st.text_input("Gemini API Key", key="api_key", type="password", help="Required for AI generation")
            st.markdown('<a href="https://aistudio.google.com/app/apikey" target="_blank" class="api-helper">Get your free API Key here →</a>', unsafe_allow_html=True)

            st.write("")
            if st.button("Continue"):
                if st.session_state.api_key and st.session_state.company_name:
                    next_step()
                    st.rerun()
                else:
                    st.warning("Please enter your Company Name and API Key.")
        
        # --- STEP 2: STRATEGY ---
        elif st.session_state.step == 2:
            st.markdown("<h2>The Conflict.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">To be different, you must stand against something.</div>', unsafe_allow_html=True)
            
            st.text_input("The Enemy", key="enemy", placeholder="e.g. Complexity", help="What frustrates your customers?")
            st.text_input("Origin Story", key="origin", placeholder="How did it start?")
            st.text_input("Value Proposition", key="one_thing", placeholder="The one thing you do best")
            
            st.write("")
            col_a, col_b = st.columns([1,3])
            with col_a:
                st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
                if st.button("Back"): prev_step(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with col_b:
                if st.button("Continue"): next_step(); st.rerun()

        # --- STEP 3: IDENTITY ---
        elif st.session_state.step == 3:
            st.markdown("<h2>The Persona.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">People buy from people. Let\'s define the character.</div>', unsafe_allow_html=True)
            
            st.selectbox("Archetype", ["The Creator", "The Sage", "The Ruler", "The Outlaw", "The Hero", "The Magician", "The Caregiver"], key="archetype")
            st.selectbox("Aesthetic Style", ["Swiss Minimalist", "Neo-Brutalist", "Luxury Serif", "Tech Modern", "Warm & Organic"], key="style")
            st.text_input("Voice Reference", key="voice", placeholder="e.g. Steve Jobs meets Tony Stark")
            
            st.write("")
            col_a, col_b = st.columns([1,3])
            with col_a:
                st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
                if st.button("Back"): prev_step(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with col_b:
                if st.button("Continue"): next_step(); st.rerun()

        # --- STEP 4: CHECKOUT ---
        elif st.session_state.step == 4:
            st.markdown("<h2>Acquisition.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">Unlock the intelligence engine.</div>', unsafe_allow_html=True)
            
            st.markdown("""
            <div style="background: #f5f5f7; padding: 24px; border-radius: 16px; margin-bottom: 24px;">
                <div style="font-size: 13px; font-weight: 600; color: #86868b; text-transform: uppercase; margin-bottom: 4px;">Total Amount</div>
                <div style="font-size: 36px; font-weight: 600; color: #1d1d1f; letter-spacing: -1px;">$99.00</div>
                <div style="font-size: 14px; color: #86868b; margin-top: 8px;">Lifetime access to strategy generation.</div>
            </div>
            """, unsafe_allow_html=True)
            
            if not st.session_state.payment_status:
                if st.button("Purchase Access"):
                    with st.spinner("Processing transaction..."):
                        time.sleep(1.5)
                        st.session_state.payment_status = True
                        st.rerun()
                st.write("")
                st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
                if st.button("Back"): prev_step(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.success("Access Granted.")
                if st.button("Generate Strategy"): next_step(); st.rerun()

        # --- STEP 5: OUTPUT ---
        elif st.session_state.step == 5:
            st.markdown("<h2>The Bible.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">Your strategic asset is being synthesized.</div>', unsafe_allow_html=True)
            
            if not st.session_state.generated_bible:
                genai.configure(api_key=st.session_state.api_key)
                
                # Dynamic Status
                status = st.empty()
                status.info("Initializing Neural Engine...")
                
                try:
                    # PROMPT CONSTRUCTION
                    prompt = f"""
                    Role: Expert Brand Strategist.
                    Client: {st.session_state.company_name} ({st.session_state.industry}).
                    Inputs: Enemy={st.session_state.enemy}, Origin={st.session_state.origin}, Value={st.session_state.one_thing},
                    Archetype={st.session_state.archetype}, Style={st.session_state.style}, Voice={st.session_state.voice}.
                    
                    Generate Brand Bible (Markdown). Do NOT use complex Unicode characters.
                    Structure:
                    # {st.session_state.company_name.upper()}
                    ## 1. MANIFESTO
                    ## 2. STRATEGY (Enemy, Insight, Position)
                    ## 3. VERBAL IDENTITY (Voice, Tone, Taglines)
                    ## 4. VISUAL DIRECTION (Color, Type, Imagery)
                    """
                    
                    status.info("Generating Strategy...")
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(prompt)
                    
                    if response.text:
                        st.session_state.generated_bible = response.text
                        status.empty()
                        st.rerun()
                    else:
                        st.error("The AI returned an empty response. Please try again.")

                except Exception as e:
                    st.error(f"Generation Error: {str(e)}")
                    st.warning("Ensure your API Key is correct and has access to Gemini.")
            
            if st.session_state.generated_bible:
                st.success("Strategy Generated Successfully.")
                
                # Safe PDF Generation
                pdf_bytes = create_pdf(st.session_state.generated_bible, st.session_state.company_name)
                
                st.download_button(
                    label="Download PDF Report",
                    data=pdf_bytes,
                    file_name="Brand_Bible.pdf",
                    mime="application/pdf"
                )
                
                st.write("")
                st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
                if st.button("Start New Project"):
                    st.session_state.step = 1; st.session_state.generated_bible = None; st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True) # End padding div
        
    with c_right:
        st.markdown(f"""
        <div style="
            height: 100%; 
            min-height: 600px;
            background-image: url('{current_img}');
            background-size: cover;
            background-position: center;
            border-left: 1px solid rgba(0,0,0,0.1);
        "></div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True) # End App Card
