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
# APPLE-GRADE CSS SYSTEM
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* 1. RESET & FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
        color: #1d1d1f;
        background-color: #f5f5f7; /* Apple Light Gray Background */
    }

    /* 2. REMOVE STREAMLIT CHROME */
    section[data-testid="stSidebar"] { display: none !important; }
    header { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    .block-container { 
        padding-top: 0rem; 
        padding-bottom: 0rem; 
        padding-left: 0rem; 
        padding-right: 0rem;
        max-width: 100% !important;
    }

    /* 3. ANIMATIONS */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    .animate-enter {
        animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    .animate-fade {
        animation: fadeIn 1.2s ease-in-out forwards;
    }

    /* 4. LANDING PAGE HERO */
    .hero-section {
        height: 100vh;
        background: radial-gradient(circle at 50% 50%, #ffffff 0%, #f2f2f5 100%);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 40px;
    }
    .hero-eyebrow {
        font-size: 14px;
        font-weight: 600;
        color: #0071e3; /* Apple Blue */
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 16px;
    }
    .hero-title {
        font-size: 64px;
        font-weight: 600;
        letter-spacing: -2px;
        line-height: 1.05;
        background: -webkit-linear-gradient(#1d1d1f, #424245);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 24px;
        max-width: 800px;
    }
    .hero-subtitle {
        font-size: 24px;
        line-height: 1.4;
        font-weight: 400;
        color: #86868b;
        max-width: 600px;
        margin-bottom: 40px;
    }

    /* 5. APP CONTAINER (GLASS CARD) */
    .app-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        padding: 40px;
        background: #fbfbfd;
    }
    .glass-card {
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.4);
        border-radius: 24px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.04);
        width: 100%;
        max-width: 1100px;
        min-height: 600px;
        overflow: hidden;
        display: flex;
    }
    .card-left {
        flex: 1;
        padding: 60px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .card-right {
        flex: 1;
        background-color: #f0f0f2;
        position: relative;
        overflow: hidden;
    }
    .card-right img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 1.5s ease;
    }
    .card-right:hover img {
        transform: scale(1.05);
    }

    /* 6. FORM ELEMENTS (Clean, Floating) */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: rgba(255,255,255,0.8) !important;
        border: 1px solid #d2d2d7 !important;
        border-radius: 12px !important;
        padding: 16px !important;
        font-size: 17px !important;
        color: #1d1d1f !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02) !important;
        transition: all 0.2s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #0071e3 !important;
        box-shadow: 0 0 0 4px rgba(0,113,227,0.15) !important;
        background-color: #fff !important;
    }
    label {
        font-size: 12px !important;
        font-weight: 600 !important;
        color: #86868b !important;
        margin-bottom: 8px !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* 7. BUTTONS (The 'Buy' Button) */
    div.stButton > button {
        background-color: #0071e3; /* Apple Blue */
        color: white;
        font-size: 17px;
        font-weight: 500;
        padding: 14px 30px;
        border-radius: 980px; /* Pill shape */
        border: none;
        cursor: pointer;
        transition: all 0.2s ease;
        width: auto;
        min-width: 160px;
        box-shadow: 0 4px 6px rgba(0,113,227,0.2);
    }
    div.stButton > button:hover {
        background-color: #0077ED;
        transform: scale(1.02);
        box-shadow: 0 6px 12px rgba(0,113,227,0.3);
    }
    div.stButton > button:active {
        transform: scale(0.98);
    }
    
    /* Secondary Button Style */
    .secondary-btn button {
        background-color: #e8e8ed !important;
        color: #1d1d1f !important;
        box-shadow: none !important;
    }
    .secondary-btn button:hover {
        background-color: #d2d2d7 !important;
    }

    /* 8. TYPOGRAPHY IN APP */
    h2 {
        font-size: 40px;
        font-weight: 600;
        letter-spacing: -1px;
        margin-bottom: 10px;
        color: #1d1d1f;
    }
    .step-desc {
        font-size: 19px;
        line-height: 1.5;
        color: #86868b;
        margin-bottom: 40px;
        font-weight: 400;
    }
    .progress-dots {
        display: flex;
        gap: 8px;
        margin-bottom: 30px;
    }
    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #d2d2d7;
        transition: all 0.3s;
    }
    .dot.active {
        background-color: #1d1d1f;
        transform: scale(1.2);
    }

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
# NAVIGATION FUNCTIONS
# -----------------------------------------------------------------------------
def go_to_app(): st.session_state.page = 'app'; st.session_state.step = 1
def next_step(): st.session_state.step += 1
def prev_step(): st.session_state.step -= 1

def generate_dots(current_step, total_steps=5):
    html = '<div class="progress-dots">'
    for i in range(1, total_steps + 1):
        active = 'active' if i == current_step else ''
        html += f'<div class="dot {active}"></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# LANDING PAGE
# -----------------------------------------------------------------------------
if st.session_state.page == 'landing':
    st.markdown("""
    <div class="hero-section animate-fade">
        <div class="hero-eyebrow">Strategic Intelligence</div>
        <div class="hero-title">The Operating System<br>for your Brand.</div>
        <div class="hero-subtitle">Turn a few simple inputs into a comprehensive identity system. Strategy, Voice, and Visuals. Instantaneously.</div>
    </div>
    """, unsafe_allow_html=True)
    
    # We use columns to center the button perfectly in Streamlit
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        if st.button("Begin Journey"):
            go_to_app()
            st.rerun()

# -----------------------------------------------------------------------------
# WIZARD APPLICATION
# -----------------------------------------------------------------------------
else:
    # IMAGES FOR EACH STEP (High Quality Abstract/Tech)
    step_images = {
        1: "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=1000", # Office/Structure
        2: "https://images.unsplash.com/photo-1505506874110-6a7a69069a08?auto=format&fit=crop&q=80&w=1000", # Storm/Conflict
        3: "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&q=80&w=1000", # Abstract/Identity
        4: "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&q=80&w=1000", # Lock/Secure
        5: "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&q=80&w=1000"  # Book/Output
    }
    
    current_image = step_images.get(st.session_state.step, step_images[1])

    # MAIN LAYOUT: Split Screen Glass Card
    col_ui, col_visual = st.columns([1, 1], gap="small")

    # LEFT COLUMN: THE UI
    with col_ui:
        st.markdown('<div style="padding: 40px 20px 0px 40px;" class="animate-enter">', unsafe_allow_html=True)
        generate_dots(st.session_state.step)
        
        # STEP 1: ENTITY
        if st.session_state.step == 1:
            st.markdown("<h2>The Foundation.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">Let’s establish the core parameters of the entity.</div>', unsafe_allow_html=True)
            
            st.text_input("API Access Key", key="api_key", type="password")
            st.text_input("Company Name", key="company_name", placeholder="e.g. Acme Inc")
            st.text_input("Industry", key="industry", placeholder="e.g. Aerospace")
            
            st.write("")
            if st.button("Continue"):
                if st.session_state.api_key: next_step(); st.rerun()
                else: st.error("API Key is required to initialize the engine.")

        # STEP 2: STRATEGY
        elif st.session_state.step == 2:
            st.markdown("<h2>The Conflict.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">Great brands solve a problem. Who is the villain?</div>', unsafe_allow_html=True)
            
            st.text_input("The Enemy", key="enemy", placeholder="What are you fighting? (e.g. Complexity)")
            st.text_input("Origin Story", key="origin", placeholder="How did it start?")
            st.text_input("Value Proposition", key="one_thing", placeholder="The one thing you do best")
            
            st.write("")
            c1, c2 = st.columns([1, 3])
            with c1: 
                st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
                if st.button("Back"): prev_step(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with c2: 
                if st.button("Continue"): next_step(); st.rerun()

        # STEP 3: IDENTITY
        elif st.session_state.step == 3:
            st.markdown("<h2>The Persona.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">Defining the human characteristics of the brand.</div>', unsafe_allow_html=True)
            
            st.selectbox("Archetype", ["The Creator", "The Sage", "The Ruler", "The Outlaw", "The Hero", "The Magician"], key="archetype")
            st.selectbox("Aesthetic Style", ["Swiss Minimalist", "Neo-Brutalist", "Luxury Serif", "Tech Modern", "Warm & Organic"], key="style")
            st.text_input("Voice Reference", key="voice", placeholder="e.g. Steve Jobs meets Tony Stark")
            
            st.write("")
            c1, c2 = st.columns([1, 3])
            with c1: 
                st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
                if st.button("Back"): prev_step(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with c2: 
                if st.button("Finalize"): next_step(); st.rerun()

        # STEP 4: PURCHASE
        elif st.session_state.step == 4:
            st.markdown("<h2>Acquisition.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">Unlock the intelligence engine to generate your strategy.</div>', unsafe_allow_html=True)
            
            st.markdown("""
            <div style="background: #f5f5f7; padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                <div style="font-size: 12px; font-weight: 600; color: #86868b; text-transform: uppercase;">Total</div>
                <div style="font-size: 32px; font-weight: 600; color: #1d1d1f;">$99.00</div>
                <div style="font-size: 14px; color: #86868b; margin-top: 5px;">One-time payment. Lifetime access.</div>
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
                st.success("Transaction verified.")
                if st.button("Generate Bible"): next_step(); st.rerun()

        # STEP 5: OUTPUT
        elif st.session_state.step == 5:
            st.markdown("<h2>The Bible.</h2>", unsafe_allow_html=True)
            st.markdown('<div class="step-desc">Your strategic asset is ready for deployment.</div>', unsafe_allow_html=True)

            if not st.session_state.generated_bible:
                genai.configure(api_key=st.session_state.api_key)
                with st.spinner("Synthesizing Strategy..."):
                    prompt = f"""
                    Role: Expert Brand Strategist.
                    Client: {st.session_state.company_name} ({st.session_state.industry}).
                    Inputs: Enemy={st.session_state.enemy}, Origin={st.session_state.origin}, Value={st.session_state.one_thing},
                    Archetype={st.session_state.archetype}, Style={st.session_state.style}, Voice={st.session_state.voice}.
                    
                    Generate Brand Bible (Markdown):
                    # {st.session_state.company_name.upper()}
                    ## 1. MANIFESTO
                    ## 2. STRATEGY (Enemy, Insight, Position)
                    ## 3. VERBAL IDENTITY (Voice, Tone, Taglines)
                    ## 4. VISUAL DIRECTION (Color, Type, Imagery)
                    """
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content(prompt)
                        st.session_state.generated_bible = response.text
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            if st.session_state.generated_bible:
                # PDF Generation Logic
                def create_pdf(text):
                    class PDF(FPDF):
                        def header(self):
                            self.set_font('Arial', 'B', 10)
                            self.cell(0, 10, 'STRATEGIC DOCUMENT', 0, 1, 'C')
                    pdf = PDF(); pdf.add_page(); pdf.set_font("Arial", size=11)
                    # Simple text dump for stability
                    pdf.multi_cell(0, 5, text.encode('latin-1', 'ignore').decode('latin-1')) 
                    return pdf.output(dest='S').encode('latin-1')

                pdf_data = create_pdf(st.session_state.generated_bible)
                
                st.markdown("""
                <div style="background: #e8f3ff; border: 1px solid #0071e3; padding: 20px; border-radius: 12px; color: #0071e3; font-weight: 500; margin-bottom: 20px;">
                    ✓ Document Generated Successfully
                </div>
                """, unsafe_allow_html=True)
                
                st.download_button("Download PDF", pdf_data, "Brand_Bible.pdf", "application/pdf")
                
                st.write("")
                if st.button("Start New Project"):
                    st.session_state.step = 1; st.session_state.generated_bible = None; st.rerun()

        st.markdown('</div>', unsafe_allow_html=True) # Close padding container

    # RIGHT COLUMN: THE VISUAL
    with col_visual:
        # We render the image in a container that fills the height
        st.markdown(f"""
        <style>
            .visual-container {{
                height: 600px;
                width: 100%;
                background-image: url('{current_image}');
                background-size: cover;
                background-position: center;
                border-radius: 0px 24px 24px 0px;
                position: relative;
            }}
            /* Overlay gradient */
            .visual-overlay {{
                position: absolute;
                bottom: 0;
                left: 0;
                width: 100%;
                height: 50%;
                background: linear-gradient(to top, rgba(0,0,0,0.5), transparent);
                border-radius: 0px 0px 24px 0px;
            }}
        </style>
        <div class="visual-container animate-fade">
            <div class="visual-overlay"></div>
        </div>
        """, unsafe_allow_html=True)
