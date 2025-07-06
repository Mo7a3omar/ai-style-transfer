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

# Configure page for holomagic display proportions
st.set_page_config(
    page_title="AI Style Transfer Studio",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Optimized CSS for Holomagic 3D Display
st.markdown("""
<style>
    /* Hide default Streamlit UI elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Style for the main header */
    .main-header {
        text-align: center;
        font-size: 4rem;
        font-weight: bold;
        background: linear-gradient(45deg, #00FFFF, #FF00FF, #FFFF00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
        text-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
    }

    /* Style for the main action button */
    .stButton > button {
        background: linear-gradient(45deg, #00FFFF, #FF00FF);
        color: white;
        border: none;
        border-radius: 30px;
        padding: 1.5rem 3rem;
        font-size: 1.5rem;
        font-weight: bold;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
    }

    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 40px rgba(255, 0, 255, 0.5);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_openai_client():
    """Securely initializes the OpenAI client."""
    try:
        api_key = os.getenv('OPENAI_API_KEY') or st.secrets.get('OPENAI_API_KEY')
        if not api_key:
            st.error("🔑 **OpenAI API Key Not Found**")
            st.info("Please configure your OPENAI_API_KEY in Streamlit secrets.")
            st.stop()
        
        client = openai.OpenAI(api_key=api_key)
        client.models.list()
        return client
            
    except Exception as e:
        st.error(f"❌ Failed to initialize OpenAI client: {str(e)}")
        st.stop()

client = init_openai_client()

def create_secure_directories():
    """Creates necessary directories for storing images."""
    # ✅ FIXED: Create 'static' directory to match configuration
    os.makedirs("static", mode=0o755, exist_ok=True)
    logger.info("Created static directory for image storage")

create_secure_directories()

def get_base_url():
    """Determines the base URL of the running Streamlit app."""
    try:
        session_info = st.runtime.get_instance()._session_mgr.list_active_sessions()[0]
        return f"{session_info.client.request.protocol}://{session_info.client.request.host}"
    except Exception:
        return "http://localhost:8501"

# Artistic styles available to the user
STYLE_PROMPTS = {
    "anime": {"name": "🎌 Anime", "prompt": "Create an image in a vibrant anime/manga art style, maintaining the original pose and composition. Use cel-shading, bold outlines, and large expressive eyes."},
    "ghibli": {"name": "🌿 Ghibli", "prompt": "Create an image in the style of Studio Ghibli, with soft watercolor textures, gentle pastel colors, and a whimsical, dreamy atmosphere. Keep the original pose."},
    "fantasy": {"name": "🧙‍♂️ Fantasy", "prompt": "Create an image in a high-fantasy art style, with magical lighting, rich colors, and ornate details, while preserving the original character's pose and features."},
    "cyberpunk": {"name": "🤖 Cyberpunk", "prompt": "Create a cyberpunk style image featuring neon colors, futuristic elements, and high-contrast lighting. The original composition and pose should be maintained."},
    "photorealistic": {"name": "📸 Realistic", "prompt": "Create a photorealistic version of the image with professional lighting, sharp details, and cinematic quality, matching the original pose exactly."}
}

def validate_image(image_file):
    """Validates the user-provided image."""
    try:
        if image_file.size > 10 * 1024 * 1024:
            return False, "Image is too large (max 10MB)."
        img = Image.open(image_file)
        img.verify()
        if img.size[0] > 4096 or img.size[1] > 4096:
            return False, "Image dimensions are too large (max 4096x4096)."
        return True, "Valid image."
    except Exception as e:
        return False, f"Invalid image file: {e}"

def encode_image_to_base64(image):
    """Encodes a PIL image to a base64 string."""
    buffered = io.BytesIO()
    image.convert('RGB').save(buffered, format="JPEG", quality=95)
    return base64.b64encode(buffered.getvalue()).decode()

def analyze_image_with_gpt4_vision(image):
    """Uses GPT-4 Vision to create a text description of an image."""
    try:
        base64_image = encode_image_to_base64(image)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [{"type": "text", "text": "Describe this image in detail, focusing on the subject's pose, expression, clothing, and the background setting."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}}]}],
            max_tokens=400
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return None, f"Image analysis failed: {e}"

def style_transfer_with_dalle3(description, style_prompt):
    """Uses DALL-E 3 to generate a new image."""
    try:
        full_prompt = f"{style_prompt}\n\nScene details: {description}"[:4000]
        response = client.images.generate(model="dall-e-3", prompt=full_prompt, size="1024x1024", quality="hd", n=1)
        image_url = response.data[0].url
        img_response = requests.get(image_url)
        img_response.raise_for_status()
        return Image.open(io.BytesIO(img_response.content)), None
    except Exception as e:
        return None, f"Image generation failed: {e}"

def save_image_to_static(image, style_name):
    """Saves the generated image to the 'static' directory."""
    try:
        safe_name = "".join(c for c in style_name if c.isalnum())
        filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        # ✅ FIXED: Save to 'static' directory
        filepath = os.path.join("static", filename)
        image.save(filepath, 'PNG', optimize=True)
        # ✅ FIXED: Use '/static/' in URL path
        public_url = f"{get_base_url()}/static/{filename}"
        logger.info(f"Image saved to: {filepath}")
        logger.info(f"Public URL: {public_url}")
        return filepath, filename, public_url
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        return None, None, None

def create_download_qr(public_url):
    """Generates a QR code for the public URL."""
    try:
        qr = segno.make(public_url, error='M')
        buffer = io.BytesIO()
        qr.save(buffer, kind='png', scale=12, border=4)
        buffer.seek(0)
        return Image.open(buffer)
    except Exception as e:
        logger.error(f"Failed to create QR code: {e}")
        return None

# --- Main Application UI ---
st.markdown('<h1 class="main-header">AI Selfie Style Transfer</h1>', unsafe_allow_html=True)

st.markdown("## 1. Select Your Style")
style_cols = st.columns(len(STYLE_PROMPTS))
selected_key = st.session_state.get('selected_style', 'anime')

for i, (key, info) in enumerate(STYLE_PROMPTS.items()):
    if style_cols[i].button(info["name"], key=f"style_{key}", use_container_width=True):
        selected_key = key
        st.session_state.selected_style = key

st.markdown("## 2. Provide an Image")
tab1, tab2 = st.tabs(["📸 Take Photo", "⬆️ Upload Image"])
image_source = tab1.camera_input("Take a selfie!", help="Uses your device's camera.") or \
               tab2.file_uploader("Upload an image file", type=["png", "jpg", "jpeg"])

if image_source:
    is_valid, message = validate_image(image_source)
    if not is_valid:
        st.error(f"❌ {message}")
    else:
        try:
            image_source.seek(0)
            original_image = Image.open(image_source).convert('RGB')
            
            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.markdown("### Original Photo")
                st.image(original_image, use_container_width=True)
            
            with col2:
                style = STYLE_PROMPTS[selected_key]
                st.markdown(f"### ✨ AI Result ({style['name']})")
                
                if st.button("🎨 Transform My Photo!", type="primary", use_container_width=True):
                    st.session_state.styled_image_bytes = None
                    with st.spinner("Analyzing your photo..."):
                        description, error = analyze_image_with_gpt4_vision(original_image)
                    
                    if error:
                        st.error(f"❌ {error}")
                    else:
                        with st.spinner(f"Generating {style['name']} version..."):
                            styled_image, error = style_transfer_with_dalle3(description, style['prompt'])
                        
                        if error:
                            st.error(f"❌ {error}")
                        else:
                            buffer = io.BytesIO()
                            styled_image.save(buffer, format="PNG")
                            st.session_state.styled_image_bytes = buffer.getvalue()
                            st.success("✅ Transformation complete!")
                
                if st.session_state.get('styled_image_bytes'):
                    st.image(st.session_state.styled_image_bytes, use_container_width=True)
                    
                    image_to_save = Image.open(io.BytesIO(st.session_state.styled_image_bytes))
                    # ✅ FIXED: Updated function name to match
                    _, filename, public_url = save_image_to_static(image_to_save, selected_key)
                    
                    if public_url:
                        st.markdown("### 📱 Scan to Download")
                        qr_image = create_download_qr(public_url)
                        if qr_image:
                            st.image(qr_image, width=250)
                            st.markdown(f"**{filename}**")
                            st.code(public_url, language=None)
                            
        except Exception as e:
            st.error(f"❌ An unexpected error occurred: {e}")
else:
    st.info("👆 Take a photo or upload an image to begin.")
