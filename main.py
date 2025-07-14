import streamlit as st
import openai
from PIL import Image
import io
import base64
import segno
import os
from datetime import datetime
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure page for a wide layout suitable for hologram displays
st.set_page_config(
    page_title="AI Style Transfer Studio",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Enhanced CSS for the Hologram Multi-Page Interface
st.markdown("""
<style>
    /* Hide default Streamlit UI elements for a cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Main container settings */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
        height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    /* Header with futuristic gradient effect */
    .main-header {
        text-align: center;
        font-size: 3.5rem;
        font-weight: bold;
        background: linear-gradient(45deg, #00FFFF, #FF00FF, #FFFF00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
        text-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
    }

    /* Page progress indicator */
    .page-indicator {
        text-align: center;
        margin-bottom: 2rem;
        font-size: 1.2rem;
        color: #00FFFF;
    }

    /* Large, interactive style selection cards for hologram displays */
    .stButton>button {
        background: linear-gradient(135deg, rgba(0, 255, 255, 0.2), rgba(255, 0, 255, 0.2)) !important;
        border: 3px solid #00FFFF !important;
        border-radius: 25px !important;
        padding: 1.5rem !important;
        text-align: center !important;
        transition: all 0.3s ease !important;
        backdrop-filter: blur(10px) !important;
        cursor: pointer !important;
        height: 120px !important;
        width: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        color: white !important;
        font-size: 1.2rem !important;
        font-weight: bold !important;
    }
    
    .stButton>button:hover {
        transform: scale(1.05) !important;
        border-color: #FF00FF !important;
        box-shadow: 0 0 40px rgba(255, 0, 255, 0.6) !important;
    }

    /* Full-screen container for image previews */
    .fullscreen-image {
        width: 100%;
        max-height: 70vh;
        border-radius: 25px;
        overflow: hidden;
        border: 4px solid #00FFFF;
        box-shadow: 0 0 40px rgba(0, 255, 255, 0.4);
        background: rgba(0, 0, 0, 0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 2rem;
    }

    /* QR Code container styling */
    .qr-section {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(0, 255, 255, 0.1));
        border: 4px solid #00FFFF;
        border-radius: 25px;
        padding: 2rem;
        text-align: center;
        box-shadow: 0 0 50px rgba(0, 255, 255, 0.6);
        margin: 2rem auto;
        max-width: 400px;
    }

    .qr-section h3 {
        color: #000;
        margin-bottom: 1rem;
    }

    .qr-section p {
        color: #333;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for page navigation and data
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'style_selection'
if 'selected_style' not in st.session_state:
    st.session_state.selected_style = None
if 'captured_image_bytes' not in st.session_state:
    st.session_state.captured_image_bytes = None
if 'stylized_image_bytes' not in st.session_state:
    st.session_state.stylized_image_bytes = None

# --- Backend Functions ---

@st.cache_resource
def init_openai_client():
    """Securely initializes the OpenAI client."""
    try:
        api_key = os.getenv('OPENAI_API_KEY') or st.secrets.get('OPENAI_API_KEY')
        if not api_key:
            st.error("🔑 **OpenAI API Key Not Found.** Please configure it in secrets.")
            st.stop()
        client = openai.OpenAI(api_key=api_key)
        client.models.list()
        return client
    except Exception as e:
        st.error(f"❌ **API Client Error:** {e}")
        st.stop()

client = init_openai_client()

STYLE_PROMPTS = {
    "anime": {
        "name": "🎌 Anime", 
        "prompt": "Create an image in anime/manga art style with the same composition, pose, and facial features as the reference image. Use cel-shaded coloring, bold black outlines, vibrant saturated colors, large expressive eyes typical of Japanese animation, and smooth gradients. Maintain the exact same pose, clothing, and scene layout."
    },
    "ghibli": {
        "name": "🌿 Ghibli", 
        "prompt": "Create a Studio Ghibli style image with soft watercolor-like textures, gentle pastel colors, whimsical and dreamy atmosphere, hand-drawn animation quality, natural organic shapes, and the characteristic Miyazaki aesthetic with attention to environmental details and magical realism."
    },
    "fantasy": {
        "name": "🧙‍♂️ Fantasy", 
        "prompt": "Create an image in fantasy art style with the same composition, pose, and facial features as the reference image. Add magical atmosphere with mystical lighting, rich deep colors with golden highlights, ornate fantasy details, and painterly quality like fantasy book illustrations."
    },
    "cyberpunk": {
        "name": "🤖 Cyberpunk", 
        "prompt": "Create a cyberpunk style image with neon colors, futuristic elements, high contrast lighting, and sci-fi aesthetic, while maintaining the original composition and pose."
    },
    "photorealistic": {
        "name": "📸 Realistic", 
        "prompt": "Create a photorealistic version with professional lighting, sharp details, realistic textures, and cinematic quality. Maintain the exact same pose, facial features, and scene layout but with enhanced realism."
    }
}

def analyze_image_with_gpt4_vision(image_bytes):
    """Uses GPT-4 Vision to create a text description of an image."""
    try:
        b64_image = base64.b64encode(image_bytes).decode()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user", 
                "content": [
                    {"type": "text", "text": "Describe this image focusing on pose, facial features, clothing, background, and composition. Be specific about positioning for accurate recreation."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}", "detail": "high"}}
                ]
            }],
            max_tokens=400
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return None, f"Image analysis failed: {e}"

def style_transfer_with_dalle3(description, style_prompt):
    """Uses DALL-E 3 to generate a new image."""
    try:
        full_prompt = f"{style_prompt}\n\nScene: {description}"[:4000]
        response = client.images.generate(
            model="dall-e-3", 
            prompt=full_prompt, 
            size="1024x1024", 
            quality="hd", 
            n=1
        )
        img_response = requests.get(response.data[0].url)
        img_response.raise_for_status()
        return Image.open(io.BytesIO(img_response.content)), None
    except Exception as e:
        return None, f"Image generation failed: {e}"

def create_download_page_and_qr(image_bytes, filename, style_name):
    """Creates a beautiful HTML download page and generates a QR code for it."""
    try:
        # Encode image as base64
        b64_image = base64.b64encode(image_bytes).decode()
        
        # Create a beautiful HTML download page
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Download Your AI Styled Image</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Arial', sans-serif;
                    background: linear-gradient(135deg, #000011, #001122, #002233);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }}
                
                .container {{
                    max-width: 600px;
                    width: 100%;
                    text-align: center;
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 30px;
                    border: 2px solid rgba(0, 255, 255, 0.3);
                    box-shadow: 0 0 40px rgba(0, 255, 255, 0.2);
                }}
                
                .title {{
                    font-size: 2.5rem;
                    font-weight: bold;
                    background: linear-gradient(45deg, #00FFFF, #FF00FF, #FFFF00);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin-bottom: 20px;
                }}
                
                .subtitle {{
                    font-size: 1.2rem;
                    color: #00FFFF;
                    margin-bottom: 30px;
                }}
                
                .image-container {{
                    margin: 30px 0;
                    border-radius: 15px;
                    overflow: hidden;
                    border: 3px solid #00FFFF;
                    box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
                }}
                
                .styled-image {{
                    width: 100%;
                    height: auto;
                    display: block;
                }}
                
                .download-btn {{
                    background: linear-gradient(45deg, #00FFFF, #FF00FF);
                    color: white;
                    border: none;
                    padding: 20px 40px;
                    font-size: 1.3rem;
                    font-weight: bold;
                    border-radius: 30px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    transition: all 0.3s ease;
                    box-shadow: 0 5px 20px rgba(0, 255, 255, 0.3);
                    margin: 20px 0;
                }}
                
                .download-btn:hover {{
                    transform: scale(1.05);
                    box-shadow: 0 8px 30px rgba(255, 0, 255, 0.4);
                }}
                
                .info {{
                    margin-top: 20px;
                    padding: 15px;
                    background: rgba(0, 255, 255, 0.1);
                    border-radius: 10px;
                    border: 1px solid rgba(0, 255, 255, 0.3);
                }}
                
                .filename {{
                    font-family: monospace;
                    color: #00FFFF;
                    font-size: 0.9rem;
                    margin-top: 10px;
                }}
                
                @media (max-width: 768px) {{
                    .title {{ font-size: 2rem; }}
                    .container {{ padding: 20px; margin: 10px; }}
                    .download-btn {{ padding: 15px 30px; font-size: 1.1rem; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="title">AI Style Transfer</h1>
                <p class="subtitle">Your {style_name} styled image is ready!</p>
                
                <div class="image-container">
                    <img src="data:image/png;base64,{b64_image}" alt="Styled Image" class="styled-image">
                </div>
                
                <a href="data:image/png;base64,{b64_image}" download="{filename}" class="download-btn">
                    📥 Download High Quality PNG
                </a>
                
                <div class="info">
                    <p>🎨 <strong>Style:</strong> {style_name}</p>
                    <p>📱 <strong>Mobile Optimized:</strong> Works on all devices</p>
                    <p>🔒 <strong>Secure:</strong> Generated with AI Style Transfer Studio</p>
                    <div class="filename">{filename}</div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Upload HTML page to hosting service
        try:
            # Using dpaste.com for reliable HTML hosting
            response = requests.post('https://dpaste.com/api/v2/', 
                                   data={
                                       'content': html_content, 
                                       'syntax': 'html', 
                                       'expiry_days': 7
                                   }, 
                                   timeout=30)
            
            if response.status_code == 201:
                page_url = response.text.strip()
                logger.info(f"Download page created: {page_url}")
                
                # Generate QR code
                qr = segno.make(page_url, error='M')
                qr_buffer = io.BytesIO()
                qr.save(qr_buffer, kind='png', scale=12, border=4, dark='#000000', light='white')
                qr_buffer.seek(0)
                
                return Image.open(qr_buffer), page_url
                
        except Exception as e:
            logger.error(f"Primary upload failed: {e}")
        
        # Fallback: Try alternative hosting
        try:
            # Using 0x0.st as fallback
            files = {'file': (f'{filename}.html', html_content.encode(), 'text/html')}
            response = requests.post('https://0x0.st', files=files, timeout=30)
            
            if response.status_code == 200:
                page_url = response.text.strip()
                logger.info(f"Fallback download page created: {page_url}")
                
                # Generate QR code
                qr = segno.make(page_url, error='M')
                qr_buffer = io.BytesIO()
                qr.save(qr_buffer, kind='png', scale=12, border=4, dark='#000000', light='white')
                qr_buffer.seek(0)
                
                return Image.open(qr_buffer), page_url
                
        except Exception as e:
            logger.error(f"Fallback upload failed: {e}")
            
    except Exception as e:
        logger.error(f"Download page creation failed: {e}")
    
    return None, None

# --- Page Rendering Functions ---

def render_style_selection_page():
    st.markdown('<h1 class="main-header">Choose Your AI Style</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-indicator">Step 1 of 3: Select a Style</p>', unsafe_allow_html=True)
    
    cols = st.columns(len(STYLE_PROMPTS))
    for i, (style_key, style_info) in enumerate(STYLE_PROMPTS.items()):
        with cols[i]:
            if st.button(style_info['name'], key=style_key, use_container_width=True):
                st.session_state.selected_style = style_key
                st.session_state.current_page = 'image_capture'
                st.rerun()

def render_image_capture_page():
    st.markdown('<h1 class="main-header">Take Your Photo</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-indicator">Step 2 of 3: Capture Your Image</p>', unsafe_allow_html=True)

    camera_photo = st.camera_input("Center yourself in the frame and take a photo")
    
    if camera_photo:
        st.session_state.captured_image_bytes = camera_photo.getvalue()
        st.session_state.current_page = 'result_display'
        st.rerun()

    if st.button("← Back to Style Selection"):
        st.session_state.current_page = 'style_selection'
        st.rerun()

def render_results_page():
    st.markdown('<h1 class="main-header">Your AI Masterpiece</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-indicator">Step 3 of 3: View and Download</p>', unsafe_allow_html=True)

    if not st.session_state.stylized_image_bytes:
        with st.spinner("AI is analyzing and stylizing your photo... This may take a moment."):
            image_bytes = st.session_state.captured_image_bytes
            selected_style_key = st.session_state.selected_style
            
            description, error = analyze_image_with_gpt4_vision(image_bytes)
            if error:
                st.error(error)
                return

            style_prompt = STYLE_PROMPTS[selected_style_key]['prompt']
            stylized_image, error = style_transfer_with_dalle3(description, style_prompt)
            if error:
                st.error(error)
                return
            
            buffer = io.BytesIO()
            stylized_image.save(buffer, format="PNG")
            st.session_state.stylized_image_bytes = buffer.getvalue()

    # Display the generated image only
    st.markdown('<div class="fullscreen-image">', unsafe_allow_html=True)
    st.image(st.session_state.stylized_image_bytes, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Generate QR code for download page
    with st.spinner("Creating download page and QR code..."):
        filename = f"styled_{st.session_state.selected_style}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        style_name = STYLE_PROMPTS[st.session_state.selected_style]['name']
        
        qr_image, page_url = create_download_page_and_qr(
            st.session_state.stylized_image_bytes, 
            filename,
            style_name
        )

    # Display QR code and start over button
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🔄 Start Over", use_container_width=True):
            # Reset session state for a new run
            for key in list(st.session_state.keys()):
                if key != 'current_page':
                    del st.session_state[key]
            st.session_state.current_page = 'style_selection'
            st.rerun()
    
    with col2:
        if qr_image and page_url:
            st.markdown('<div class="qr-section">', unsafe_allow_html=True)
            st.markdown("### 📱 Scan to Download")
            st.image(qr_image, width=200)
            st.markdown("**Scan with your phone to open download page**")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.error("Could not generate QR code. Please try again.")

# --- Main App Router ---
page_map = {
    'style_selection': render_style_selection_page,
    'image_capture': render_image_capture_page,
    'result_display': render_results_page
}

page_function = page_map.get(st.session_state.current_page, render_style_selection_page)
page_function()
# --- End of main.py ---
