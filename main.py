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
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure page for hologram display
st.set_page_config(
    page_title="AI Style Transfer Studio",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Enhanced CSS for Hologram Interface
st.markdown("""
<style>
    /* Hide default Streamlit UI elements */
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

    /* Style selection buttons */
    .stButton>button {
        background: linear-gradient(135deg, rgba(0, 255, 255, 0.2), rgba(255, 0, 255, 0.2)) !important;
        border: 3px solid #00FFFF !important;
        border-radius: 25px !important;
        padding: 2rem !important;
        text-align: center !important;
        transition: all 0.3s ease !important;
        backdrop-filter: blur(10px) !important;
        color: white !important;
        font-size: 1.2rem !important;
        font-weight: bold !important;
        height: 120px !important;
        width: 100% !important;
    }
    
    .stButton>button:hover {
        transform: scale(1.08) !important;
        border-color: #FF00FF !important;
        box-shadow: 0 0 40px rgba(255, 0, 255, 0.6) !important;
    }

    /* Full-screen image container */
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
        margin: 2rem 0;
    }

    /* Preview image container for captured photos */
    .preview-image {
        width: 100%;
        max-height: 50vh;
        border-radius: 20px;
        overflow: hidden;
        border: 3px solid #00FFFF;
        box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
        background: rgba(0, 0, 0, 0.2);
        margin: 1rem 0;
    }

    /* QR Code container */
    .qr-section {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(0, 255, 255, 0.1));
        border: 4px solid #00FFFF;
        border-radius: 25px;
        padding: 2rem;
        text-align: center;
        margin-top: 2rem;
        box-shadow: 0 0 50px rgba(0, 255, 255, 0.6);
    }

    .qr-section h3 {
        color: #000;
        margin-bottom: 1rem;
    }

    .qr-section p {
        color: #333;
        margin-top: 1rem;
    }
    
    /* Success message styling */
    .success-message {
        background: rgba(0, 255, 0, 0.2);
        border: 3px solid #00FF00;
        color: #00FF00;
        text-align: center;
        font-size: 1.2rem;
        padding: 1rem;
        border-radius: 15px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'style_selection'
if 'selected_style' not in st.session_state:
    st.session_state.selected_style = None
if 'captured_image_bytes' not in st.session_state:
    st.session_state.captured_image_bytes = None
if 'stylized_image_bytes' not in st.session_state:
    st.session_state.stylized_image_bytes = None

# AWS and OpenAI Client Initialization
@st.cache_resource
def init_aws_client():
    """Initialize AWS S3 client"""
    try:
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID') or st.secrets.get('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY') or st.secrets.get('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION') or st.secrets.get('AWS_REGION', 'us-east-1')
        
        if not aws_access_key or not aws_secret_key:
            st.error("🔑 **AWS credentials not found.** Please configure AWS keys in secrets.")
            st.stop()
            
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        return s3_client
    except Exception as e:
        st.error(f"❌ **AWS Client Error:** {e}")
        st.stop()

@st.cache_resource
def init_openai_client():
    """Initialize OpenAI client"""
    try:
        api_key = os.getenv('OPENAI_API_KEY') or st.secrets.get('OPENAI_API_KEY')
        if not api_key:
            st.error("🔑 **OpenAI API Key Not Found.** Please configure it in secrets.")
            st.stop()
        client = openai.OpenAI(api_key=api_key)
        client.models.list()
        return client
    except Exception as e:
        st.error(f"❌ **OpenAI Client Error:** {e}")
        st.stop()

s3_client = init_aws_client()
openai_client = init_openai_client()

# Configuration
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME') or st.secrets.get('AWS_BUCKET_NAME', 'ai-style-transfer-images')
AWS_REGION = os.getenv('AWS_REGION') or st.secrets.get('AWS_REGION', 'us-east-1')

# Style prompts
STYLE_PROMPTS = {
    "anime": {
        "name": "🎌 Anime",
        "prompt": "Create an image in anime/manga art style with the same composition, pose, and facial features as the reference image. Use cel-shaded coloring, bold black outlines, vibrant saturated colors, large expressive eyes typical of Japanese animation, and smooth gradients."
    },
    "ghibli": {
        "name": "🌿 Ghibli",
        "prompt": "Create a Studio Ghibli style image with soft watercolor-like textures, gentle pastel colors, whimsical and dreamy atmosphere, hand-drawn animation quality, natural organic shapes, and the characteristic Miyazaki aesthetic."
    },
    "fantasy": {
        "name": "🧙‍♂️ Fantasy",
        "prompt": "Create an image in fantasy art style with the same composition, pose, and facial features as the reference image. Add magical atmosphere with mystical lighting, rich colors with golden highlights, ornate fantasy details."
    },
    "cyberpunk": {
        "name": "🤖 Cyberpunk",
        "prompt": "Create a cyberpunk style image with neon colors, futuristic elements, high contrast lighting, and sci-fi aesthetic, while maintaining the original composition and pose."
    },
    "photorealistic": {
        "name": "📸 Realistic",
        "prompt": "Create a photorealistic version with professional lighting, sharp details, realistic textures, and cinematic quality. Maintain the exact same pose, facial features, and scene layout."
    }
}

def upload_image_to_s3(image_bytes, filename):
    """Upload image to AWS S3 and return public URL"""
    try:
        # Upload to S3
        s3_client.put_object(
            Bucket=AWS_BUCKET_NAME,
            Key=filename,
            Body=image_bytes,
            ContentType='image/png',
            ACL='public-read'  # Make the object publicly readable
        )
        
        # Generate public URL
        public_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
        logger.info(f"Image uploaded to S3: {public_url}")
        return public_url
        
    except ClientError as e:
        logger.error(f"AWS S3 upload failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        return None

def analyze_image_with_gpt4_vision(image_bytes):
    """Analyze image with GPT-4 Vision"""
    try:
        b64_image = base64.b64encode(image_bytes).decode()
        response = openai_client.chat.completions.create(
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
    """Generate styled image with DALL-E 3"""
    try:
        full_prompt = f"{style_prompt}\n\nScene: {description}"[:4000]
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024",
            quality="hd",
            n=1
        )
        image_url = response.data[0].url
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()
        return Image.open(io.BytesIO(img_response.content)), None
    except Exception as e:
        return None, f"Image generation failed: {e}"

def create_qr_code_for_s3_url(s3_url):
    """Create QR code that points directly to S3 image URL"""
    try:
        qr = segno.make(s3_url, error='M')
        qr_buffer = io.BytesIO()
        qr.save(qr_buffer, kind='png', scale=15, border=4, dark='#000000', light='white')
        qr_buffer.seek(0)
        return Image.open(qr_buffer)
    except Exception as e:
        logger.error(f"QR code generation failed: {e}")
        return None

# Page Rendering Functions
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
    
    # Show selected style
    if st.session_state.selected_style:
        style_info = STYLE_PROMPTS[st.session_state.selected_style]
        st.info(f"Selected Style: **{style_info['name']}**")

    # Check if image is already captured
    if st.session_state.captured_image_bytes:
        # Show captured image preview
        st.markdown("### 📷 Captured Photo")
        st.markdown('<div class="preview-image">', unsafe_allow_html=True)
        st.image(st.session_state.captured_image_bytes, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Success message
        st.markdown('<div class="success-message">✅ Photo captured successfully!</div>', unsafe_allow_html=True)
        
        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("← Back to Style Selection", use_container_width=True):
                st.session_state.current_page = 'style_selection'
                st.session_state.captured_image_bytes = None
                st.rerun()
        
        with col2:
            if st.button("📸 Retake Photo", use_container_width=True):
                st.session_state.captured_image_bytes = None
                st.rerun()
        
        with col3:
            if st.button("✨ Continue to AI Generation", use_container_width=True, type="primary"):
                st.session_state.current_page = 'result_display'
                st.rerun()
    
    else:
        # Show camera input when no image is captured
        camera_photo = st.camera_input(
            "📸 Position yourself in the frame and take a selfie",
            help="This will use your device's front-facing camera"
        )
        
        if camera_photo:
            st.session_state.captured_image_bytes = camera_photo.getvalue()
            st.rerun()

        # Back button
        if st.button("← Back to Style Selection"):
            st.session_state.current_page = 'style_selection'
            st.rerun()

def render_results_page():
    st.markdown('<h1 class="main-header">Your AI Masterpiece</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-indicator">Step 3 of 3: Download Your Creation</p>', unsafe_allow_html=True)

    if not st.session_state.stylized_image_bytes:
        with st.spinner("🤖 AI is analyzing and creating your masterpiece... Please wait."):
            image_bytes = st.session_state.captured_image_bytes
            selected_style_key = st.session_state.selected_style
            
            description, error = analyze_image_with_gpt4_vision(image_bytes)
            if error:
                st.error(f"❌ {error}")
                if st.button("🔄 Try Again"):
                    st.rerun()
                return

            style_prompt = STYLE_PROMPTS[selected_style_key]['prompt']
            stylized_image, error = style_transfer_with_dalle3(description, style_prompt)
            if error:
                st.error(f"❌ {error}")
                if st.button("🔄 Try Again"):
                    st.rerun()
                return
            
            buffer = io.BytesIO()
            stylized_image.save(buffer, format="PNG")
            st.session_state.stylized_image_bytes = buffer.getvalue()

    # Display the generated image only (no original image)
    st.markdown('<div class="fullscreen-image">', unsafe_allow_html=True)
    st.image(st.session_state.stylized_image_bytes, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Upload to AWS S3 and generate QR code
    with st.spinner("📤 Uploading to cloud and generating QR code..."):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"styled-images/{st.session_state.selected_style}/{timestamp}.png"
        
        # Upload to S3
        s3_url = upload_image_to_s3(st.session_state.stylized_image_bytes, filename)
        
        if s3_url:
            # Generate QR code
            qr_image = create_qr_code_for_s3_url(s3_url)
        else:
            qr_image = None

    # Create two columns: action buttons and QR code
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔄 Create Another", use_container_width=True):
            # Reset all session state
            st.session_state.selected_style = None
            st.session_state.captured_image_bytes = None
            st.session_state.stylized_image_bytes = None
            st.session_state.current_page = 'style_selection'
            st.rerun()
            
    with col2:
        if qr_image and s3_url:
            st.markdown('<div class="qr-section">', unsafe_allow_html=True)
            st.markdown("### 📱 Scan to Download")
            st.image(qr_image, width=200)
            st.markdown("**Scan with your phone to access your image**")
            st.caption(f"Hosted on AWS Cloud")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.error("❌ Failed to upload to cloud. Please try again.")
            st.download_button(
                label="💾 Download Locally",
                data=st.session_state.stylized_image_bytes,
                file_name=f"styled_{st.session_state.selected_style}_{timestamp}.png",
                mime="image/png",
                use_container_width=True
            )

# Main App Router
if st.session_state.current_page == 'style_selection':
    render_style_selection_page()
elif st.session_state.current_page == 'image_capture':
    render_image_capture_page()
elif st.session_state.current_page == 'result_display':
    render_results_page()
