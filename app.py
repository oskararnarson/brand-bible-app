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
    page_title="The Brand Bible Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a "High-End SaaS" feel
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        font-weight: 600;
        transition: all 0.2s;
    }
    .pay-btn>button {
        background-color: #28a745;
        color: white;
        border: none;
    }
    .gen-btn>button {
        background-color: #000000;
        color: white;
        border: none;
    }
    h1 {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-weight: 800;
        letter-spacing: -1px;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def sanitize_text_for_pdf(text):
    """
    Cleans text to ensure FPDF compatibility (Standard FPDF fonts are Latin-1).
    Replaces common unicode characters with ASCII equivalents.
    """
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--', '\u2026': '...', '\u2022': '*',
        '—': '--', '’': "'", '“': '"', '”': '"'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    
    # Strip emojis or other non-latin-1 characters to prevent crashes
    return text.encode('latin-1', 'ignore').decode('latin-1')

def scrape_website_text(url):
    """
    Scrapes the text content from a given URL to inform the brand strategy.
    Includes headers to mimic a browser request.
    """
    if not url:
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
            
        text = soup.get_text(separator=' ')
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return clean_text[:4000] # Truncate to avoid token limits
        
    except Exception as e:
        st.warning(f"⚠️ Could not scrape website data: {str(e)}. Proceeding without URL context.")
        return None

def create_pdf(content, company_name):
    """
    Generates a professional PDF from the Markdown-like text content.
    """
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, f'Brand Bible: {company_name}', 0, 1, 'C')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    
    # Simple parsing: Treat lines starting with # or ## as headers
    lines = content.split('\n')
    for line in lines:
        sanitized_line = sanitize_text_for_pdf(line)
        
        if line.startswith('###') or line.startswith('**'):
            pdf.set_font("Arial", 'B', 12)
            pdf.multi_cell(0, 10, sanitized_line.replace('#', '').replace('*', '').strip())
            pdf.set_font("Arial", size=12)
        elif line.startswith('##'):
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 14)
            pdf.multi_cell(0, 10, sanitized_line.replace('#', '').strip())
            pdf.set_font("Arial", size=12)
        elif line.startswith('#'):
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 16)
            pdf.multi_cell(0, 10, sanitized_line.replace('#', '').strip())
            pdf.ln(2)
            pdf.set_font("Arial", size=12)
        else:
            pdf.multi_cell(0, 7, sanitized_line)
            
    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# SESSION STATE MANAGEMENT
# -----------------------------------------------------------------------------
if 'payment_status' not in st.session_state:
    st.session_state['payment_status'] = False

if 'generated_bible' not in st.session_state:
    st.session_state['generated_bible'] = None

# -----------------------------------------------------------------------------
# SIDEBAR: THE INTAKE
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚡ Brand Bible Gen.")
    st.caption("Strategic Intelligence Engine")
    
    # API Key Input (Critical for functionality)
    api_key = st.text_input("Google AI API Key", type="password", help="Required to activate the Brain (Gemini).")
    
    st.divider()
    
    st.subheader("1. The Basics")
    company_name = st.text_input("Company Name", "Acme Corp")
    industry = st.text_input("Industry", "SaaS / Tech")
    url = st.text_input("Current Website URL", placeholder="https://")
    
    st.subheader("2. Strategy Core")
    enemy = st.text_input("The Enemy", placeholder="E.g., Complexity, Boredom, Old Gatekeepers")
    origin_story = st.text_area("Origin Story (Brief)", placeholder="Started in a garage...")
    one_thing = st.text_input("The One Thing", placeholder="The single specific value you provide")
    
    st.subheader("3. Psychology")
    fears_desires = st.text_area("Audience Fears & Desires", placeholder="They fear obsolescence; they desire status.")
    archetype = st.selectbox("Brand Archetype", 
        ["The Rebel", "The Magician", "The Hero", "The Lover", "The Jester", 
         "The Sage", "The Explorer", "The Ruler", "The Caregiver", "The Creator", 
         "The Innocent", "The Everyman"])
    feeling = st.text_input("The Feeling", placeholder="E.g., Relieved, Empowered, Elite")
    
    st.subheader("4. Visuals")
    aesthetic = st.selectbox("Aesthetic Style", 
        ["Swiss Minimalist", "Brutalist", "Corporate Memphis", "Luxury Serif", "Tech Dark Mode", "Organic/Natural", "Industrial"])
    colors_avoid = st.text_input("Colors to Avoid", placeholder="E.g., No orange, no neon green")
    
    st.subheader("5. Voice")
    voice_match = st.text_input("Celebrity Voice Match", placeholder="E.g., Morgan Freeman meets Ryan Reynolds")
    taboo_words = st.text_input("Taboo Words", placeholder="E.g., 'Synergy', 'Disrupt', 'Cheap'")

# -----------------------------------------------------------------------------
# MAIN APPLICATION LOGIC
# -----------------------------------------------------------------------------

# Header
st.title("The Brand Bible Generator")
st.markdown("### Generate a comprehensive Brand Strategy, Voice, and Visual Identity System in seconds.")
st.markdown("---")

# Logic Container
col1, col2 = st.columns([2, 1])

with col1:
    if not st.session_state['payment_status']:
        st.info("👋 Welcome. Please complete the intake form on the left.")
        st.markdown("""
        **What you get for $99:**
        * **The North Star:** Mission, Vision, Manifesto.
        * **The Persona:** Deep psychographic profiling.
        * **Verbal Identity:** Taglines, hooks, and voice rules.
        * **Visual Direction:** Briefs for logo, type, and art direction.
        * **PDF Download:** Ready to send to your team or investors.
        """)
        
        # Simulated Payment Gate
        st.write("")
        st.markdown("#### Unlock Strategic Access")
        
        # Using a container for the pay button to style it
        pay_col, _ = st.columns([1,2])
        with pay_col:
            pay_btn = st.button("Process Payment ($99)", key="pay_btn", type="primary")
        
        if pay_btn:
            with st.spinner("Processing secure transaction..."):
                time.sleep(2) # Simulate network delay
                st.session_state['payment_status'] = True
                st.balloons()
                st.rerun()
                
    else:
        # ---------------------------------------------------------------------
        # POST-PAYMENT VIEW
        # ---------------------------------------------------------------------
        st.success("✅ Payment Verified. Access Granted.")
        
        # Generation Trigger
        if st.button("Generate Brand Bible", type="primary"):
            if not api_key:
                st.error("Please enter your Google AI API Key in the sidebar to proceed.")
            else:
                # Configure Google AI
                genai.configure(api_key=api_key)
                
                with st.spinner("Analyzing market data... scraping URL... synthesizing strategy..."):
                    
                    # 1. Scrape Context (if URL provided)
                    web_context = ""
                    if url:
                        web_data = scrape_website_text(url)
                        if web_data:
                            web_context = f"\n\nCONTEXT FROM CURRENT WEBSITE:\n{web_data}"
                    
                    # 2. Construct Prompt
                    system_prompt = (
                        "You are a world-renowned Brand Strategist, combining the wit of Ogilvy, "
                        "the distinctiveness of Wolff Olins, and the aesthetic rigor of Pentagram. "
                        "Your job is not to chat, but to generate a comprehensive Brand Bible. "
                        "Tone: Authoritative, Sophisticated, and Deeply Strategic. Do not be generic. Be bold."
                    )
                    
                    user_prompt = f"""
                    Create a Brand Bible for: {company_name}
                    
                    DATA INPUTS:
                    Industry: {industry}
                    The Enemy: {enemy}
                    Origin Story: {origin_story}
                    The One Thing: {one_thing}
                    Audience Fears/Desires: {fears_desires}
                    Archetype: {archetype}
                    Desired Feeling: {feeling}
                    Aesthetic Preference: {aesthetic}
                    Colors to Avoid: {colors_avoid}
                    Voice Match: {voice_match}
                    Taboo Words: {taboo_words}
                    {web_context}
                    
                    REQUIRED OUTPUT SECTIONS (Use Markdown Headers ##):
                    1. THE NORTH STAR (Mission, Vision, and a rousing Brand Manifesto)
                    2. THE PERSONA (Psychographic profile of the believer)
                    3. VERBAL IDENTITY (Voice guidelines, "We say / We never say", 5 Taglines)
                    4. VISUAL DIRECTION (Art Direction briefs for Logo, Typography, Photography)
                    """
                    
                    try:
                        # Initialize Model (Gemini 1.5 Flash is great for speed/cost)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        # Combine system instruction with user prompt
                        full_prompt = f"{system_prompt}\n\n{user_prompt}"
                        
                        response = model.generate_content(full_prompt)
                        
                        st.session_state['generated_bible'] = response.text
                        
                    except Exception as e:
                        st.error(f"Generation Error: {e}")

        # Display Result
        if st.session_state['generated_bible']:
            st.divider()
            st.subheader(f"📂 Brand Bible: {company_name}")
            
            # Show content in an expander or main area
            st.markdown(st.session_state['generated_bible'])
            
            # PDF Generation
            pdf_bytes = create_pdf(st.session_state['generated_bible'], company_name)
            
            st.divider()
            st.download_button(
                label="Download Brand Bible (PDF)",
                data=pdf_bytes,
                file_name=f"{company_name.replace(' ', '_')}_Brand_Bible.pdf",
                mime="application/pdf"
            )

# Right Column - Visual Filler or Status
with col2:
    if st.session_state['payment_status']:
        st.markdown("### Status")
        st.write("🟢 **Account:** Premium")
        st.write("🟢 **Credits:** Unlimited")
        st.write(f"🏢 **Active Project:** {company_name}")
    else:
        st.markdown("### Examples")
        st.info('"The Nike of Gardening Tools"')
        st.info('"The Apple of Dog Food"')
        st.info('"The Tesla of Toasters"')
