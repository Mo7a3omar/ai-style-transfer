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
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Full screen layout */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }
    
    /* Holomagic optimized header */
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
    
    /* Style selection cards */
    .style-button {
        background: linear-gradient(135deg, rgba(0, 255, 255, 0.2), rgba(255, 0, 255, 0.2));
        border: 2px solid #00FFFF;
        border-radius: 20px;
        padding: 1.5rem;
        margin: 0.5rem;
        text-align: center;
        transition: all 0.3s ease;
        backdrop-filter: blur(10px);
    }
    
    .style-button:hover {
        transform: scale(1.05);
        border-color: #FF00FF;
        box-shadow: 0 0 30px rgba(255, 0, 255, 0.5);
    }
    
    /* Image containers */
    .image-container {
        border-radius: 20px;
        overflow: hidden;
        border: 3px solid #00FFFF;
        box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
        margin: 1rem 0;
        background: rgba(0, 0, 0, 0.3);
    }
    
    /* QR Code container for 3D display */
    .qr-container {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(0, 255, 255, 0.1));
        border: 3px solid #00FFFF;
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        margin: 2rem auto;
        max-width: 350px;
        box-shadow: 0 0 40px rgba(0, 255, 255, 0.4);
    }
    
    /* Transform button */
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
    
    /* Status messages */
    .stSuccess {
        background: rgba(0, 255, 0, 0.1);
        border: 2px solid #00FF00;
        border-radius: 15px;
    }
    
    .stError {
        background: rgba(255, 0, 0, 0.1);
        border: 2px solid #FF0000;
        border-radius: 15px;
    }
    
    /* File uploader and camera input */
    .stFileUploader, .stCameraInput {
        border: 2px dashed #00FFFF;
        border-radius: 20px;
        padding: 2rem;
        background: rgba(0, 255, 255, 0.05);
    }
    
    /* Security indicator */
    .security-badge {
        position: fixed;
        top: 10px;
        right: 10px;
        background: rgba(0, 255, 0, 0.8);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.8rem;
        z-index: 1000;
    }
</style>
""", unsafe_allow_html=True)

# Security indicator
st.markdown('<div class="security-badge">🔒 Secure API</div>', unsafe_allow_html=True)

# Secure OpenAI client initialization
@st.cache_resource
def init_openai_client():
    """Initialize OpenAI client with comprehensive security checks"""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key and hasattr(st, 'secrets'):
            api_key = st.secrets.get('OPENAI_API_KEY')

        if not api_key:
            st.error("🔑 **OpenAI API Key Not Found**")
            st.info("Please configure your OPENAI_API_KEY in Streamlit secrets.")
            st.code('OPENAI_API_KEY = "your-api-key-here"')
            st.stop()
        
        if not api_key.startswith('sk-'):
            st.error("❌ Invalid OpenAI API key format.")
            st.stop()
        
        client = openai.OpenAI(api_key=api_key)
        client.models.list()
        logger.info("OpenAI client initialized successfully")
        return client
            
    except openai.AuthenticationError:
        st.error("❌ Invalid OpenAI API key. Please check your key and try again.")
        st.info("Get a new API key at: https://platform.openai.com/api-keys")
        st.stop()
    except Exception as e:
        st.error(f"❌ Failed to initialize OpenAI client: {str(e)}")
        st.stop()

client = init_openai_client()

# Create secure directories
def create_secure_directories():
    """Create directories with proper permissions, ignoring if they already exist"""
    directories = ["static", "uploaded_images"]
    for directory in directories:
        os.makedirs(directory, mode=0o755, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")

create_secure_directories()

def get_base_url():
    """Get the base URL for static file serving."""
    try:
        session_info = st.runtime.get_instance()._session_mgr.list_active_sessions()[0]
        return f"{session_info.client.request.protocol}://{session_info.client.request.host}"
    except Exception:
        # Fallback for local development or other environments
        return "http://localhost:8501"

# Streamlined style prompts
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
        "prompt": "Create an image in fantasy art style with the same composition, pose, and facial features as the reference image. Add magical atmosphere with mystical lighting, rich deep colors with golden highlights, ornate fantasy details, and painterly quality like fantasy book illustrations. Keep the same pose, character features, and scene layout."
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

def validate_image(image_file):
    """Validate uploaded image for security"""
    try:
        # Check file size (max 10MB)
        if image_file.size > 10 * 1024 * 1024:
            return False, "Image too large (max 10MB)"
        
        # Verify it's actually an image
        img = Image.open(image_file)
        img.verify()
        
        # Check dimensions (reasonable limits)
        if img.size[0] > 4096 or img.size[1] > 4096:
            return False, "Image dimensions too large (max 4096x4096)"
        
        return True, "Valid image"
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"

def encode_image_to_base64(image):
    """Convert PIL Image to base64 string"""
    buffered = io.BytesIO()
    if image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')
    image.save(buffered, format="JPEG", quality=95)
    return base64.b64encode(buffered.getvalue()).decode()

def analyze_image_with_gpt4_vision(image):
    """Analyze image with GPT-4 Vision"""
    try:
        base64_image = encode_image_to_base64(image)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image focusing on pose, facial features, clothing, background, and composition. Be specific about positioning for accurate recreation."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}}
                ]
            }],
            max_tokens=400,
            timeout=30
        )
        return response.choices[0].message.content, None
    except openai.RateLimitError:
        return None, "Rate limit exceeded. Please try again in a moment."
    except Exception as e:
        return None, f"Analysis error: {str(e)}"

def style_transfer_with_dalle3(image_description, style_prompt):
    """Generate styled image with DALL-E 3"""
    try:
        full_prompt = f"{style_prompt}\n\nScene: {image_description}"[:4000]
        response = client.images.generate(
            model="dall-e-3", 
            prompt=full_prompt, 
            size="1024x1024", 
            quality="hd", 
            n=1, 
            timeout=60
        )
        image_url = response.data[0].url
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()
        return Image.open(io.BytesIO(img_response.content)), None
    except openai.RateLimitError:
        return None, "Rate limit exceeded. Please try again in a moment."
    except Exception as e:
        return None, f"Generation error: {str(e)}"

def save_image_to_static(image, style_name):
    """Save image to static directory with the corrected public URL"""
    try:
        safe_style_name = "".join(c for c in style_name if c.isalnum() or c in ('-', '_'))
        filename = f"{safe_style_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join("static", filename)
        image.save(filepath, 'PNG', optimize=True)
        
        # ✅ FIXED: Removed the incorrect '/app' from the URL path
        public_url = f"{get_base_url()}/static/{filename}"
        
        logger.info(f"Image saved to: {filepath}")
        logger.info(f"Public URL created: {public_url}")
        return filepath, filename, public_url
    except Exception as e:
        logger.error(f"Image save error: {e}")
        return None, None, None


def create_download_qr(public_url):
    """Create QR code for download"""
    try:
        qr = segno.make(public_url, error='M')
        buffer = io.BytesIO()
        qr.save(buffer, kind='png', scale=12, border=4, dark='#000000', light='white')
        buffer.seek(0)
        return Image.open(buffer)
    except Exception as e:
        logger.error(f"QR code generation error: {e}")
        return None

# --- Main UI ---
st.markdown('<h1 class="main-header">AI Selfie Style Transfer</h1>', unsafe_allow_html=True)

# Style Selection
st.markdown("## 1. Select Your Style")
style_cols = st.columns(len(STYLE_PROMPTS))
selected_style_key = st.session_state.get('selected_style', 'anime')

for idx, (style_key, style_info) in enumerate(STYLE_PROMPTS.items()):
    with style_cols[idx]:
        if st.button(style_info["name"], key=f"style_{style_key}", use_container_width=True):
            selected_style_key = style_key
            st.session_state.selected_style = style_key

# --- New Camera-First Input ---
st.markdown("## 2. Provide an Image")

# Use tabs for Camera and Upload options
tab1, tab2 = st.tabs(["📸 Take Photo", "⬆️ Upload Image"])
image_source = None

with tab1:
    # Selfie camera is the default on mobile devices
    camera_photo = st.camera_input(
        "Take a selfie to transform!", 
        help="This will use your device's front-facing camera."
    )
    if camera_photo:
        image_source = camera_photo

with tab2:
    uploaded_file = st.file_uploader(
        "Or upload an image file",
        type=["png", "jpg", "jpeg"],
        help="Select an image to transform (max 10MB, 4096x4096px)"
    )
    if uploaded_file:
        image_source = uploaded_file

# --- Main Processing Logic ---
if image_source is not None:
    is_valid, validation_message = validate_image(image_source)
    
    if not is_valid:
        st.error(f"❌ {validation_message}")
    else:
        try:
            image_source.seek(0)
            original_image = Image.open(image_source).convert('RGB')
            
            col1, col2 = st.columns(2, gap="large")
            
            with col1:
                st.markdown("### Original Photo")
                st.markdown('<div class="image-container">', unsafe_allow_html=True)
                st.image(original_image, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                current_style = STYLE_PROMPTS[selected_style_key]
                st.markdown(f"### ✨ AI Result ({current_style['name']})")

                # The "Transform" button now acts as the trigger for the AI process
                if st.button("🎨 Transform My Photo!", type="primary", use_container_width=True):
                    st.session_state.stylized_image = None # Clear previous result
                    with st.spinner("🔍 Analyzing your photo..."):
                        desc, err = analyze_image_with_gpt4_vision(original_image)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        with st.spinner(f"🎨 Generating {current_style['name']} version..."):
                            styled_img, err = style_transfer_with_dalle3(desc, current_style['prompt'])
                        if err:
                            st.error(f"❌ {err}")
                        else:
                            st.session_state.stylized_image = styled_img
                            st.success("✅ Transformation complete!")
                
                if 'stylized_image' in st.session_state and st.session_state.stylized_image is not None:
                    st.markdown('<div class="image-container">', unsafe_allow_html=True)
                    st.image(st.session_state.stylized_image, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    filepath, filename, public_url = save_image_to_static(st.session_state.stylized_image, selected_style_key)
                    
                    if public_url:
                        st.markdown("### 📱 Scan to Download")
                        qr_image = create_download_qr(public_url)
                        if qr_image:
                            st.markdown('<div class="qr-container">', unsafe_allow_html=True)
                            st.image(qr_image, width=250)
                            st.markdown(f"**{filename}**")
                            st.markdown(f"[Direct Link]({public_url})")
                            st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"❌ An unexpected error occurred: {str(e)}")
            logger.error(f"Image processing error: {e}")
else:
    st.info("👆 Take a photo or upload an image to begin the transformation.")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #7F8C8D; font-size: 1rem; margin-top: 2rem;'>
        🔒 Secure AI Style Transfer • 🤖 GPT-4 Vision + DALL-E 3<br>
        🛡️ API Keys Protected • 📱 QR Downloads Available
    </div>
    """,
    unsafe_allow_html=True
)
