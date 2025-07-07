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

    /* Custom download link styling */
    .download-link {
        text-decoration: none !important;
        background: linear-gradient(45deg, #00FFFF, #FF00FF) !important;
        color: white !important;
        padding: 15px 30px !important;
        border-radius: 25px !important;
        display: inline-block !important;
        font-weight: bold !important;
        font-size: 1.1rem !important;
        margin: 10px 0 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 5px 15px rgba(0, 255, 255, 0.3) !important;
    }

    .download-link:hover {
        transform: scale(1.05) !important;
        box-shadow: 0 8px 25px rgba(255, 0, 255, 0.4) !important;
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

# Streamlined style prompts
STYLE_PROMPTS = {
    "anime": {
        "name": "🎌 Anime",
        "prompt": "Create an image in anime/manga art style with the same composition, pose, and facial features as the reference image. Use cel-shaded coloring, bold black outlines, vibrant saturated colors, large expressive eyes typical of Japanese animation, and smooth gradients. Maintain the exact same pose, clothing, and scene layout.",
    },
    "ghibli": {
        "name": "🌿 Ghibli",
        "prompt": "Create a Studio Ghibli style image with soft watercolor-like textures, gentle pastel colors, whimsical and dreamy atmosphere, hand-drawn animation quality, natural organic shapes, and the characteristic Miyazaki aesthetic with attention to environmental details and magical realism.",
    },
    "fantasy": {
        "name": "🧙‍♂️ Fantasy",
        "prompt": "Create an image in fantasy art style with the same composition, pose, and facial features as the reference image. Add magical atmosphere with mystical lighting, rich deep colors with golden highlights, ornate fantasy details, and painterly quality like fantasy book illustrations. Keep the same pose, character features, and scene layout.",
    },
    "cyberpunk": {
        "name": "🤖 Cyberpunk",
        "prompt": "Create a cyberpunk style image with neon colors, futuristic elements, high contrast lighting, and sci-fi aesthetic, while maintaining the original composition and pose.",
    },
    "photorealistic": {
        "name": "📸 Realistic",
        "prompt": "Create a photorealistic version with professional lighting, sharp details, realistic textures, and cinematic quality. Maintain the exact same pose, facial features, and scene layout but with enhanced realism.",
    }
}

def validate_image(image_file):
    """Validate uploaded image for security"""
    try:
        # Check file size (max 10MB)
        if hasattr(image_file, 'size') and image_file.size > 10 * 1024 * 1024:
            return False, "Image too large (max 10MB)"
        
        # Verify it's actually an image
        img = Image.open(image_file)
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

def create_download_page(image_bytes, filename, style_name):
    """Create a beautiful HTML download page with image and download button"""
    try:
        # Encode image as base64
        b64_image = base64.b64encode(image_bytes).decode()
        
        # Create a beautiful HTML page optimized for mobile and desktop
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Your AI Styled Image - {filename}</title>
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
                
                .header {{
                    margin-bottom: 30px;
                }}
                
                .title {{
                    font-size: 2.5rem;
                    font-weight: bold;
                    background: linear-gradient(45deg, #00FFFF, #FF00FF, #FFFF00);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin-bottom: 10px;
                    text-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
                }}
                
                .subtitle {{
                    font-size: 1.2rem;
                    color: #00FFFF;
                    margin-bottom: 20px;
                }}
                
                .image-container {{
                    margin: 30px 0;
                    border-radius: 15px;
                    overflow: hidden;
                    border: 3px solid #00FFFF;
                    box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
                    background: rgba(0, 0, 0, 0.3);
                }}
                
                .styled-image {{
                    width: 100%;
                    height: auto;
                    display: block;
                }}
                
                .download-section {{
                    margin-top: 30px;
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
                    margin: 10px;
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
                
                .footer {{
                    margin-top: 30px;
                    font-size: 0.9rem;
                    color: #888;
                }}
                
                @media (max-width: 768px) {{
                    .title {{
                        font-size: 2rem;
                    }}
                    
                    .container {{
                        padding: 20px;
                        margin: 10px;
                    }}
                    
                    .download-btn {{
                        padding: 15px 30px;
                        font-size: 1.1rem;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 class="title">AI Style Transfer</h1>
                    <p class="subtitle">Your {style_name} styled image is ready!</p>
                </div>
                
                <div class="image-container">
                    <img src="data:image/png;base64,{b64_image}" alt="Styled Image" class="styled-image">
                </div>
                
                <div class="download-section">
                    <a href="data:image/png;base64,{b64_image}" download="{filename}" class="download-btn">
                        📥 Download High Quality PNG
                    </a>
                </div>
                
                <div class="info">
                    <p>🎨 <strong>Style:</strong> {style_name}</p>
                    <p>📱 <strong>Mobile Optimized:</strong> Works on all devices</p>
                    <p>🔒 <strong>Secure:</strong> Generated with AI Style Transfer Studio</p>
                    <div class="filename">{filename}</div>
                </div>
                
                <div class="footer">
                    <p>Powered by GPT-4 Vision + DALL-E 3 • Holomagic 3D Display Ready</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Upload HTML page to a hosting service
        try:
            # Using dpaste.com for HTML hosting
            response = requests.post('https://dpaste.com/api/v2/', 
                                   data={
                                       'content': html_content, 
                                       'syntax': 'html', 
                                       'expiry_days': 7  # 7 days expiration
                                   }, 
                                   timeout=30)
            
            if response.status_code == 201:
                page_url = response.text.strip()
                logger.info(f"Download page created: {page_url}")
                return page_url
                
        except Exception as e:
            logger.error(f"HTML page upload failed: {e}")
        
        # Fallback: Try alternative service
        try:
            # Using hastebin as fallback
            response = requests.post('https://hastebin.com/documents', 
                                   data=html_content, 
                                   timeout=30)
            
            if response.status_code == 200:
                key = response.json()['key']
                page_url = f"https://hastebin.com/raw/{key}"
                logger.info(f"Fallback download page created: {page_url}")
                return page_url
                
        except Exception as e:
            logger.error(f"Fallback HTML upload failed: {e}")
            
    except Exception as e:
        logger.error(f"Download page creation failed: {e}")
    
    return None

def create_qr_with_download_page(image_bytes, filename, style_name):
    """Create QR code that links to a download page with image and button"""
    try:
        # Create the download page
        page_url = create_download_page(image_bytes, filename, style_name)
        
        if page_url:
            # Create QR code with the page URL
            qr = segno.make(page_url, error='M')
            buffer = io.BytesIO()
            qr.save(buffer, kind='png', scale=12, border=4, dark='#000000', light='white')
            buffer.seek(0)
            return Image.open(buffer), page_url
        else:
            # Fallback QR with app info
            fallback_text = f"AI Style Transfer - {filename} - {style_name} Style"
            qr = segno.make(fallback_text, error='M')
            buffer = io.BytesIO()
            qr.save(buffer, kind='png', scale=10, border=4)
            buffer.seek(0)
            return Image.open(buffer), None
        
    except Exception as e:
        logger.error(f"QR creation with download page failed: {e}")
        return None, None

def create_download_options(image_bytes, style_name):
    """Create download options with QR code linking to download page"""
    try:
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_style_name = "".join(c for c in style_name if c.isalnum() or c in ('-', '_'))
        filename = f"styled_{safe_style_name}_{timestamp}.png"
        
        # Create base64 data URL for HTML download
        b64 = base64.b64encode(image_bytes).decode()
        download_link = f'<a href="data:image/png;base64,{b64}" download="{filename}" class="download-link">📥 Download {filename}</a>'
        
        # Create QR code with download page
        qr_image, page_url = create_qr_with_download_page(image_bytes, filename, style_name)
        
        return download_link, qr_image, filename, page_url
            
    except Exception as e:
        logger.error(f"Download options creation failed: {e}")
        return None, None, None, None

# Main Interface
st.markdown('<h1 class="main-header">AI Selfie Style Transfer</h1>', unsafe_allow_html=True)

# Style Selection
st.markdown("## 1. Select Your Style")
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

# Image Upload with Camera Priority
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

# Main Processing Logic
if image_source is not None:
    # Validate uploaded image
    is_valid, validation_message = validate_image(image_source)
    
    if not is_valid:
        st.error(f"❌ {validation_message}")
    else:
        try:
            # Reset file pointer after validation
            image_source.seek(0)
            original_image = Image.open(image_source).convert('RGB')
            
            # Display layout
            col1, col2 = st.columns(2, gap="large")
            
            with col1:
                st.markdown("### Original Photo")
                st.markdown('<div class="image-container">', unsafe_allow_html=True)
                st.image(original_image, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.caption(f"Size: {original_image.size[0]}x{original_image.size[1]} pixels")
            
            with col2:
                current_style = STYLE_PROMPTS[st.session_state.selected_style]
                st.markdown(f"### ✨ {current_style['name']} Style")
                
                # Transform button
                if st.button("🎨 Transform My Photo!", type="primary", use_container_width=True):
                    # Clear previous results
                    st.session_state.styled_image_bytes = None
                    
                    with st.spinner("🔍 Analyzing your photo..."):
                        image_description, error = analyze_image_with_gpt4_vision(original_image)
                        
                        if error:
                            st.error(f"❌ {error}")
                        else:
                            with st.spinner(f"🎨 Generating {current_style['name']} version..."):
                                stylized_image, error = style_transfer_with_dalle3(
                                    image_description,
                                    current_style['prompt']
                                )
                                
                                if stylized_image and not error:
                                    # Store image as bytes in session state
                                    buffer = io.BytesIO()
                                    stylized_image.save(buffer, format="PNG")
                                    st.session_state.styled_image_bytes = buffer.getvalue()
                                    st.success("✅ Transformation complete!")
                                else:
                                    st.error(f"❌ {error}")
                
                # Display result and download options
                if st.session_state.get('styled_image_bytes'):
                    st.markdown('<div class="image-container">', unsafe_allow_html=True)
                    st.image(st.session_state.styled_image_bytes, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Create download options with QR code linking to download page
                    with st.spinner("🔗 Creating download page..."):
                        download_link, qr_image, filename, page_url = create_download_options(
                            st.session_state.styled_image_bytes, 
                            st.session_state.selected_style
                        )
                    
                    st.markdown("### 📥 Download Options")
                    
                    # Method 1: Streamlit's built-in download button (always works)
                    st.download_button(
                        label="💾 Download PNG",
                        data=st.session_state.styled_image_bytes,
                        file_name=filename,
                        mime="image/png",
                        use_container_width=True
                    )
                    
                    # Method 2: HTML download link (works in most browsers)
                    if download_link:
                        st.markdown(download_link, unsafe_allow_html=True)
                    
                    # Method 3: QR code linking to download page (MAIN FEATURE)
                    if qr_image:
                        st.markdown("### 📱 Scan QR Code for Download Page")
                        st.markdown('<div class="qr-container">', unsafe_allow_html=True)
                        st.image(qr_image, width=250)
                        if page_url:
                            st.markdown("**Scan to open download page with image and button**")
                            st.code(page_url, language=None)
                            st.caption("✨ Page includes: Image display + Download button + Mobile optimized")
                        else:
                            st.markdown("**QR contains image information**")
                        st.markdown('</div>', unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"❌ Error processing image: {str(e)}")
            logger.error(f"Image processing error: {e}")

else:
    st.info("👆 Take a photo or upload an image to begin transformation")

# Footer with security info
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #7F8C8D; font-size: 1rem; margin-top: 2rem;'>
        🔒 Secure AI Style Transfer • 🤖 GPT-4 Vision + DALL-E 3<br>
        🛡️ API Keys Protected • 📱 QR Download Pages Available
    </div>
    """,
    unsafe_allow_html=True
)
