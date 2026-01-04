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
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# PREMIUM WIZARD CSS
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* IMPORT ELEGANT FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=Inter:wght@300;400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #000000;
        background-color: #FFFFFF;
    }

    /* HIDE STREAMLIT CHROME */
    section[data-testid="stSidebar"] { display: none !important; }
    header { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    .block-container { padding-top: 3rem; padding-bottom: 5rem; }

    /* TYPOGRAPHY */
    h1 {
        font-family: 'Playfair Display', serif;
        font-size: 3rem !important;
        font-weight: 400 !important;
        margin-bottom: 1rem !important;
        color: #111 !important;
        letter-spacing: -0.5px;
    }
    h2 {
        font-family: 'Playfair Display', serif;
        font-size: 2rem !important;
        margin-bottom: 2rem !important;
        color: #111 !important;
    }
    p {
        font-size: 1.1rem;
        color: #666;
        line-height: 1.6;
    }

    /* INPUTS - ELEGANT UNDERLINE STYLE */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: transparent !important;
        border: none !important;
        border-bottom: 2px solid #E5E7EB !important;
        border-radius: 0px !important;
        padding: 1rem 0rem !important;
        font-size: 1.2rem !important;
        color: #111 !important;
        font-family: 'Inter', sans-serif;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-bottom: 2px solid #000 !important;
        box-shadow: none !important;
    }
    label {
        font-size: 0.85rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #999 !important;
    }

    /* BUTTONS - MINIMALIST */
    div.stButton > button {
        background-color: #000;
        color: #fff;
        border-radius: 50px;
        padding: 0.75rem 2.5rem;
        font-weight: 500;
        font-size: 1rem;
        border: none;
        transition: transform 0.2s;
        margin-top: 2rem;
    }
    div.stButton > button:hover {
        background-color: #333;
        transform: translateY(-2px);
    }
    div.stButton > button:active {
        transform: translateY(0);
    }

    /* PROGRESS BAR */
    .step-indicator {
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 2rem;
    }

    /* PAYMENT BOX */
    .payment-box {
        border: 1px solid #eee;
        padding: 3rem;
        border-radius: 12px;
        text-align: center;
        background: #FAFAFA;
        margin-top: 2rem;
    }
    
    /* SUCCESS ANIMATION */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-in {
        animation: fadeIn 0.8s ease-out forwards;
    }

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -----------------------------------------------------------------------------
if 'step' not in st.session_state: st.session_state.step = 1
if 'payment_status' not in st.session_state: st.session_state.payment_status = False
if 'generated_bible' not in st.session_state: st.session_state.generated_bible = None

# Input Storage Initialization (to prevent key errors)
keys = [
    'api_key', 'company_name', 'industry', 'url', 
    'enemy', 'origin_story', 'one_thing',
    'archetype', 'aesthetic', 'voice_match', 'generated_bible'
]
for key in keys:
    if key not in st.session_state:
        st.session_state[key] = ""

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
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
            self.set_font('Arial', 'B', 10); self.cell(0, 10, f'{company_name} // STRATEGY', 0, 1, 'C'); self.ln(10)
    pdf = PDF(); pdf.add_page(); pdf.set_auto_page_break(True, 20); pdf.set_font("Arial", size=11)
    for line in content.split('\n'):
        s = sanitize_text_for_pdf(line)
        if s.startswith('#'): pdf.set_font("Arial", 'B', 14); pdf.ln(5)
        else: pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 6, s.replace('#','').strip())
    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# MAIN LAYOUT CONTAINER
# -----------------------------------------------------------------------------
# Use a centered column for focus
col_left, col_center, col_right = st.columns([1, 2, 1])

with col_center:
    
    # -------------------------------------------------------------------------
    # STEP 1: WELCOME & BASICS
    # -------------------------------------------------------------------------
    if st.session_state.step == 1:
        st.markdown('<div class="step-indicator">STEP 01 / 05</div>', unsafe_allow_html=True)
        st.markdown('<div class="animate-in">', unsafe_allow_html=True)
        st.markdown("# Let's define the entity.")
        st.write("To begin, we need the fundamental identifiers of the brand.")
        st.write("")
        
        st.text_input("Gemini API Key", key="api_key", type="password", help="Required to proceed")
        st.text_input("Company Name", key="company_name", placeholder="e.g. Acme Inc.")
        st.text_input("Industry", key="industry", placeholder="e.g. FinTech")
        st.text_input("Website URL (Optional)", key="url", placeholder="We will read this for context")
        
        if st.button("Continue →"):
            if st.session_state.api_key and st.session_state.company_name:
                next_step()
                st.rerun()
            else:
                st.error("Please provide API Key and Company Name.")
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # STEP 2: STRATEGY
    # -------------------------------------------------------------------------
    elif st.session_state.step == 2:
        st.markdown('<div class="step-indicator">STEP 02 / 05</div>', unsafe_allow_html=True)
        st.markdown('<div class="animate-in">', unsafe_allow_html=True)
        st.markdown("# The Strategic Core.")
        st.write("Great brands are built on conflict and truth.")
        st.write("")
        
        st.text_input("The Enemy", key="enemy", placeholder="What are you fighting against? (e.g. Complexity, Boredom)")
        st.text_area("Origin Story", key="origin_story", placeholder="Briefly, how did this start?", height=100)
        st.text_input("The One Thing", key="one_thing", placeholder="Your singular value proposition")
        
        c1, c2 = st.columns([1,1])
        with c1: 
            if st.button("← Back"): prev_step(); st.rerun()
        with c2: 
            if st.button("Continue →"): next_step(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # STEP 3: IDENTITY
    # -------------------------------------------------------------------------
    elif st.session_state.step == 3:
        st.markdown('<div class="step-indicator">STEP 03 / 05</div>', unsafe_allow_html=True)
        st.markdown('<div class="animate-in">', unsafe_allow_html=True)
        st.markdown("# The Persona.")
        st.write("If the brand were a person, who would they be?")
        st.write("")
        
        st.selectbox("Brand Archetype", 
            ["The Sage", "The Ruler", "The Creator", "The Outlaw", "The Magician", "The Hero", "The Lover", "The Jester", "The Caregiver"],
            key="archetype")
        
        st.selectbox("Visual Aesthetic", 
            ["Minimalist / Swiss", "Bold / Brutalist", "Luxury / Serif", "Playful / Pop", "Corporate / Trust", "Organic / Warm"],
            key="aesthetic")
            
        st.text_input("Celebrity Voice Match", key="voice_match", placeholder="e.g. 'Ryan Reynolds meets Steve Jobs'")
        
        c1, c2 = st.columns([1,1])
        with c1: 
            if st.button("← Back"): prev_step(); st.rerun()
        with c2: 
            if st.button("Review & Unlock →"): next_step(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # STEP 4: PAYMENT GATE
    # -------------------------------------------------------------------------
    elif st.session_state.step == 4:
        st.markdown('<div class="step-indicator">STEP 04 / 05</div>', unsafe_allow_html=True)
        st.markdown('<div class="animate-in">', unsafe_allow_html=True)
        st.markdown("# Access Strategy Engine.")
        st.write("Your inputs are ready for processing. Unlock the full Brand Bible generation.")
        
        st.markdown(f"""
        <div class="payment-box">
            <h3>Total: $99.00</h3>
            <p>Includes: Manifesto, Voice Guidelines, Visual Brief, PDF.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if not st.session_state.payment_status:
            if st.button("Secure Checkout ($99)"):
                with st.spinner("Processing payment..."):
                    time.sleep(1.5)
                    st.session_state.payment_status = True
                    st.rerun()
            if st.button("← Back"): prev_step(); st.rerun()
        else:
            st.success("Payment Verified. Access Granted.")
            if st.button("Generate Brand Bible →"):
                next_step()
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # STEP 5: GENERATION & OUTPUT
    # -------------------------------------------------------------------------
    elif st.session_state.step == 5:
        st.markdown('<div class="step-indicator">STEP 05 / 05</div>', unsafe_allow_html=True)
        st.markdown("# The Brand Bible.")
        
        if not st.session_state.generated_bible:
            genai.configure(api_key=st.session_state.api_key)
            
            with st.spinner("Analyzing market context... synthesizing strategy..."):
                web_c = ""
                if st.session_state.url:
                    web_c = scrape_website_text(st.session_state.url)
                
                prompt = f"""
                Act as a world-class Brand Strategist.
                Client: {st.session_state.company_name} ({st.session_state.industry})
                Context: {web_c}
                Inputs: Enemy={st.session_state.enemy}, Origin={st.session_state.origin_story}, Value={st.session_state.one_thing},
                Archetype={st.session_state.archetype}, Style={st.session_state.aesthetic}, Voice={st.session_state.voice_match}.
                
                Generate a Brand Bible in Markdown. Sections:
                1. THE NORTH STAR (Mission, Vision, Manifesto)
                2. THE STRATEGY (Enemy, Insight, Position)
                3. VERBAL IDENTITY (Voice, Tone, Taglines)
                4. VISUAL DIRECTION (Color, Type, Imagery)
                """
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(prompt)
                    st.session_state.generated_bible = response.text
                except Exception as e:
                    st.error(f"Error: {e}")
                    if st.button("Retry"): st.rerun()

        if st.session_state.generated_bible:
            st.markdown(st.session_state.generated_bible)
            st.divider()
            
            pdf_data = create_pdf(st.session_state.generated_bible, st.session_state.company_name)
            st.download_button(
                label="Download Official PDF",
                data=pdf_data,
                file_name=f"{st.session_state.company_name}_Bible.pdf",
                mime="application/pdf"
            )
            
            if st.button("Start New Project"):
                st.session_state.step = 1
                st.session_state.generated_bible = None
                st.rerun()
