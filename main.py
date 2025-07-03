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
    
    /* File uploader */
    .stFileUploader {
        border: 2px dashed #00FFFF;
        border-radius: 20px;
        padding: 2rem;
        background: rgba(0, 255, 255, 0.05);
    }
    
    /* Download link styling */
    .download-info {
        background: rgba(0, 255, 255, 0.1);
        border: 2px solid #00FFFF;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        text-align: center;
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
        # Try multiple sources for API key
        api_key = None
        
        # 1. Try Streamlit secrets (production)
        if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
            api_key = st.secrets['OPENAI_API_KEY']
            logger.info("API key loaded from Streamlit secrets")
        
        # 2. Try environment variable (local development)
        elif 'OPENAI_API_KEY' in os.environ:
            api_key = os.environ['OPENAI_API_KEY']
            logger.info("API key loaded from environment variable")
        
        # 3. No API key found
        if not api_key:
            st.error("🔑 **OpenAI API Key Not Found**")
            st.info("**For Streamlit Cloud deployment:**")
            st.code("""
Go to your app dashboard → Settings → Secrets
Add: OPENAI_API_KEY = "your-api-key-here"
            """)
            st.info("**For local development:**")
            st.code("""
Create .streamlit/secrets.toml:
OPENAI_API_KEY = "your-api-key-here"
            """)
            st.stop()
        
        # Validate API key format
        if not api_key.startswith('sk-'):
            st.error("❌ Invalid OpenAI API key format")
            st.stop()
        
        # Initialize client with error handling
        client = openai.OpenAI(api_key=api_key)
        
        # Test API key validity with a minimal request
        try:
            client.models.list()
            logger.info("OpenAI client initialized successfully")
            return client
        except openai.AuthenticationError:
            st.error("❌ Invalid OpenAI API key. Please check your key and try again.")
            st.info("Get a new API key at: https://platform.openai.com/api-keys")
            st.stop()
        except Exception as e:
            st.error(f"❌ OpenAI API connection failed: {str(e)}")
            st.stop()
            
    except Exception as e:
        st.error(f"❌ Failed to initialize OpenAI client: {str(e)}")
        st.stop()

client = init_openai_client()

# Create secure directories
def create_secure_directories():
    """Create directories with proper permissions"""
    directories = ["static", "uploaded_images"]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, mode=0o755)
            logger.info(f"Created directory: {directory}")

create_secure_directories()

def get_base_url():
    """Get the base URL for static file serving with error handling"""
    try:
        # Get current session info
        session_info = st.runtime.get_instance()
        if hasattr(session_info, '_session_mgr'):
            sessions = session_info._session_mgr.list_active_sessions()
            if sessions:
                session = sessions[0]
                if hasattr(session, 'client') and hasattr(session.client, 'request'):
                    protocol = getattr(session.client.request, 'protocol', 'http')
                    host = getattr(session.client.request, 'host', 'localhost:8501')
                    return f"{protocol}://{host}"
    except Exception as e:
        logger.warning(f"Could not determine base URL: {e}")
    
    # Fallback URLs
    if 'streamlit.app' in os.environ.get('STREAMLIT_SERVER_HEADLESS', ''):
        return "https://your-app-name.streamlit.app"
    return "http://localhost:8501"

# Streamlined style prompts
STYLE_PROMPTS = {
    "anime": {
        "name": "🎌 Anime",
        "prompt": "Create an anime/manga style image with cel-shaded coloring, bold outlines, vibrant colors, and large expressive eyes. Maintain the same composition and pose.",
    },
    "ghibli": {
        "name": "🌿 Ghibli",
        "prompt": "Create a Studio Ghibli style image with soft watercolor-like textures, gentle pastel colors, whimsical and dreamy atmosphere, hand-drawn animation quality, natural organic shapes, and the characteristic Miyazaki aesthetic with attention to environmental details and magical realism.",
    },
    "fantasy": {
        "name": "🧙‍♂️ Fantasy",
        "prompt": "Create a fantasy art style image with magical atmosphere, mystical lighting, rich colors with golden highlights, and painterly quality.",
    },
    "cyberpunk": {
        "name": "🤖 Cyberpunk",
        "prompt": "Create a cyberpunk style image with neon colors, futuristic elements, high contrast lighting, and sci-fi aesthetic.",
    },
    "photorealistic": {
        "name": "📸 Realistic",
        "prompt": "Create a photorealistic version with professional lighting, sharp details, realistic textures, and cinematic quality.",
    }
}


def validate_image(image):
    """Validate uploaded image for security"""
    try:
        # Check file size (max 10MB)
        if hasattr(image, 'size') and image.size > 10 * 1024 * 1024:
            return False, "Image too large (max 10MB)"
        
        # Verify it's actually an image
        img = Image.open(image)
        img.verify()
        
        # Check dimensions (reasonable limits)
        if img.size[0] > 4096 or img.size[1] > 4096:
            return False, "Image dimensions too large (max 4096x4096)"
        
        return True, "Valid image"
    except Exception as e:
        return False, f"Invalid image: {str(e)}"

def encode_image_to_base64(image):
    """Convert PIL Image to base64 string with error handling"""
    try:
        buffered = io.BytesIO()
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        image.save(buffered, format="JPEG", quality=95)
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        logger.error(f"Image encoding error: {e}")
        raise

def analyze_image_with_gpt4_vision(image):
    """Analyze image with GPT-4 Vision with comprehensive error handling"""
    try:
        base64_image = encode_image_to_base64(image)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe this image focusing on pose, facial features, clothing, background, and composition. Be specific about positioning for accurate recreation."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=400,
            timeout=30
        )
        
        return response.choices[0].message.content, None
        
    except openai.RateLimitError:
        return None, "Rate limit exceeded. Please try again in a moment."
    except openai.APIError as e:
        return None, f"OpenAI API error: {str(e)}"
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return None, f"Analysis error: {str(e)}"

def style_transfer_with_dalle3(image_description, style_prompt):
    """Generate styled image with DALL-E 3 with comprehensive error handling"""
    try:
        full_prompt = f"{style_prompt}\n\nScene: {image_description}"
        
        if len(full_prompt) > 4000:
            full_prompt = full_prompt[:4000]
        
        response = client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024",
            quality="hd",
            n=1,
            timeout=60
        )
        
        if response.data and len(response.data) > 0:
            image_url = response.data[0].url
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()
            generated_image = Image.open(io.BytesIO(img_response.content))
            return generated_image, None
        else:
            return None, "No image generated"
            
    except openai.RateLimitError:
        return None, "Rate limit exceeded. Please try again in a moment."
    except openai.APIError as e:
        return None, f"DALL-E API error: {str(e)}"
    except requests.RequestException as e:
        return None, f"Image download error: {str(e)}"
    except Exception as e:
        logger.error(f"Style transfer error: {e}")
        return None, f"Generation error: {str(e)}"

def save_image_to_static(image, style_name):
    """Save image to static directory with security measures"""
    try:
        # Generate secure filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize style name
        safe_style_name = "".join(c for c in style_name if c.isalnum() or c in ('-', '_'))
        filename = f"{safe_style_name}_{timestamp}.png"
        filepath = os.path.join("static", filename)
        
        # Save with error handling
        image.save(filepath, 'PNG', optimize=True)
        
        base_url = get_base_url()
        public_url = f"{base_url}/app/static/{filename}"
        
        logger.info(f"Image saved: {filename}")
        return filepath, filename, public_url
    except Exception as e:
        logger.error(f"Image save error: {e}")
        return None, None, None

def create_download_qr(public_url):
    """Create QR code for download with error handling"""
    try:
        qr = segno.make(public_url, error='M')
        
        buffer = io.BytesIO()
        qr.save(buffer, kind='png', scale=12, border=4, dark='#000000', light='white')
        buffer.seek(0)
        
        qr_image = Image.open(buffer)
        return qr_image
    except Exception as e:
        logger.error(f"QR code generation error: {e}")
        return None

# Main Interface
st.markdown('<h1 class="main-header">AI Style Transfer</h1>', unsafe_allow_html=True)

# Style Selection
st.markdown("## Select Style")
style_cols = st.columns(5)

selected_style = None
for idx, (style_key, style_info) in enumerate(STYLE_PROMPTS.items()):
    with style_cols[idx]:
        if st.button(style_info["name"], key=f"style_{style_key}", use_container_width=True):
            selected_style = style_key

if selected_style:
    st.session_state.selected_style = selected_style

if 'selected_style' not in st.session_state:
    st.session_state.selected_style = 'anime'

# Image Upload with validation
uploaded_file = st.file_uploader(
    "Upload Image",
    type=["png", "jpg", "jpeg"],
    help="Select an image to transform (max 10MB, 4096x4096px)"
)

if uploaded_file is not None:
    # Validate uploaded image
    is_valid, validation_message = validate_image(uploaded_file)
    
    if not is_valid:
        st.error(f"❌ {validation_message}")
        st.stop()
    
    try:
        # Reset file pointer after validation
        uploaded_file.seek(0)
        original_image = Image.open(uploaded_file).convert('RGB')
        
        # Display layout
        col1, col2 = st.columns(2, gap="large")
        
        with col1:
            st.markdown("### Original")
            st.markdown('<div class="image-container">', unsafe_allow_html=True)
            st.image(original_image, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            st.caption(f"Size: {original_image.size[0]}x{original_image.size[1]} pixels")
        
        with col2:
            current_style = STYLE_PROMPTS[st.session_state.selected_style]
            st.markdown(f"### {current_style['name']} Style")
            
            # Transform button
            if st.button("🎨 Transform", type="primary", use_container_width=True):
                with st.spinner("🔍 Analyzing image..."):
                    image_description, error = analyze_image_with_gpt4_vision(original_image)
                    
                    if error:
                        st.error(f"❌ {error}")
                    else:
                        with st.spinner("🎨 Generating styled image..."):
                            stylized_image, error = style_transfer_with_dalle3(
                                image_description,
                                current_style['prompt']
                            )
                            
                            if stylized_image and not error:
                                st.session_state.stylized_image = stylized_image
                                st.success("✅ Transformation complete!")
                            else:
                                st.error(f"❌ {error}")
            
            # Display result
            if 'stylized_image' in st.session_state:
                st.markdown('<div class="image-container">', unsafe_allow_html=True)
                st.image(st.session_state.stylized_image, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Save and create QR
                filepath, filename, public_url = save_image_to_static(
                    st.session_state.stylized_image, 
                    st.session_state.selected_style
                )
                
                if public_url:
                    # QR Code for download
                    st.markdown("### 📱 Scan to Download")
                    qr_image = create_download_qr(public_url)
                    
                    if qr_image:
                        st.markdown('<div class="qr-container">', unsafe_allow_html=True)
                        st.image(qr_image, width=250)
                        st.markdown(f"**{filename}**")
                        st.markdown(f"[Direct Link]({public_url})")
                        st.markdown('</div>', unsafe_allow_html=True)
                
                # Direct download
                img_buffer = io.BytesIO()
                st.session_state.stylized_image.save(img_buffer, format='PNG')
                st.download_button(
                    label="💾 Download",
                    data=img_buffer.getvalue(),
                    file_name=f"styled_{st.session_state.selected_style}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                    mime="image/png",
                    use_container_width=True
                )
    
    except Exception as e:
        st.error(f"❌ Error processing image: {str(e)}")
        logger.error(f"Image processing error: {e}")

else:
    st.info("👆 Upload an image to begin transformation")

# Usage statistics (optional)
if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0

if uploaded_file is not None:
    st.session_state.usage_count += 1

# Footer with security info
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
