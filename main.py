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
import ssl
import urllib3


# Disable SSL warnings for development (remove in production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure page for hologram display
st.set_page_config(
    page_title="AI Style Transfer Studio",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# [Keep your existing CSS styling here]
# Comprehensive footer removal for mobile devices
# Mobile-optimized footer removal without sticky positioning
st.markdown("""
<style>
    /* Standard footer hiding without viewport manipulation */
    footer, 
    .stApp > footer, 
    footer[data-testid="stFooter"],
    div[data-testid="stBottom"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Mobile-specific without fixed positioning */
    @media screen and (max-width: 768px) {
        footer,
        [data-testid="stFooter"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            line-height: 0 !important;
            font-size: 0 !important;
        }
        
        /* Remove footer space without affecting layout */
        .main .block-container {
            padding-bottom: 1rem !important;
        }
        
        /* Target any remaining footer text */
        footer * {
            display: none !important;
        }
    }
    
    /* Hide elements containing streamlit text */
    *:contains("Streamlit"),
    *:contains("streamlit"),
    *:contains("Hosted by") {
        display: none !important;
    }
</style>

<script>
    function removeFooterContent() {
        // Target footer elements and their content
        const footers = document.querySelectorAll('footer, [data-testid="stFooter"]');
        footers.forEach(footer => {
            // Remove content instead of repositioning
            footer.innerHTML = '';
            footer.style.display = 'none';
            footer.style.height = '0px';
            footer.style.margin = '0px';
            footer.style.padding = '0px';
        });
        
        // Remove any text nodes containing streamlit references
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        let textNode;
        const nodesToRemove = [];
        while (textNode = walker.nextNode()) {
            if (textNode.textContent.toLowerCase().includes('streamlit') || 
                textNode.textContent.toLowerCase().includes('hosted by')) {
                nodesToRemove.push(textNode.parentElement);
            }
        }
        
        nodesToRemove.forEach(node => {
            if (node) {
                node.style.display = 'none';
                node.remove();
            }
        });
    }
    
    // Run after DOM loads and periodically on mobile
    document.addEventListener('DOMContentLoaded', removeFooterContent);
    
    // Only run interval on mobile to avoid performance issues
    if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
        setTimeout(removeFooterContent, 100);
        setTimeout(removeFooterContent, 1000);
        setInterval(removeFooterContent, 2000);
    }
</script>
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
    """Initialize AWS S3 client with proper SSL configuration"""
    try:
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID') or st.secrets.get('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY') or st.secrets.get('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION') or st.secrets.get('AWS_REGION', 'ap-southeast-2')
        
        if not aws_access_key or not aws_secret_key:
            st.error("🔑 **AWS credentials not found.** Please configure AWS keys in secrets.")
            st.stop()
        
        # Create S3 client with proper configuration
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region,
            config=boto3.session.Config(
                signature_version='s3v4',
                retries={'max_attempts': 3},
                max_pool_connections=50
            )
        )
        
        # Test connection
        s3_client.list_buckets()
        logger.info(f"S3 client initialized successfully for region: {aws_region}")
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
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME') or st.secrets.get('AWS_BUCKET_NAME')
AWS_REGION = os.getenv('AWS_REGION') or st.secrets.get('AWS_REGION', 'ap-southeast-2')

if not AWS_BUCKET_NAME:
    st.error("❌ **AWS_BUCKET_NAME not configured.** Please set it in secrets.")
    st.stop()

STYLE_PROMPTS = {
    "anime": {
        "name": "📖 Anime",
        "prompt": "In vibrant anime style: cel-shaded, bold lines, expressive eyes, and bright colors."
    },
    "ghibli": {
        "name": "🌿 Ghibli",
        "prompt": "Studio Ghibli style: hand-painted look, soft colors, gentle shading, whimsical animation."
    },
    "fantasy": {
        "name": "🧙‍♂️ Fantasy",
        "prompt": "Fantasy illustration style: magical lighting, rich colors, ornate and enchanting aesthetic."
    },
    "cyberpunk": {
        "name": "🤖 Cyberpunk",
        "prompt": "Cyberpunk style: neon colors, futuristic lighting, high contrast, sci-fi atmosphere."
    },
    "photorealistic": {
        "name": "📸 Realistic",
        "prompt": "Ultra-photorealistic, cinematic lighting, crisp details, natural colors."
    }
}

def upload_image_to_s3(image_bytes, style_name):
    """Upload image to S3 and return public URL"""
    try:
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"styled_{style_name}_{timestamp}.png"
        
        # Create organized S3 key structure
        year = datetime.now().strftime('%Y')
        month = datetime.now().strftime('%m')
        day = datetime.now().strftime('%d')
        s3_key = f"styled-images/{year}/{month}/{day}/{filename}"
        
        # Upload to S3 with proper metadata
        s3_client.put_object(
            Bucket=AWS_BUCKET_NAME,
            Key=s3_key,
            Body=image_bytes,
            ContentType='image/png',
            CacheControl='max-age=31536000',  # 1 year cache
            Metadata={
                'style': style_name,
                'created': timestamp,
                'app': 'ai-style-transfer'
            }
        )
        
        # Generate public URL
        public_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        
        logger.info(f"Image uploaded successfully: {s3_key}")
        return public_url, filename
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"S3 upload failed with error code {error_code}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        return None, None

def create_qr_code_with_url(image_url):
    """Create QR code that links to the S3 hosted image"""
    try:
        qr = segno.make(image_url, error='M')
        qr_buffer = io.BytesIO()
        qr.save(qr_buffer, kind='png', scale=12, border=4, dark='#000000', light='white')
        qr_buffer.seek(0)
        return Image.open(qr_buffer)
    except Exception as e:
        logger.error(f"QR code creation failed: {e}")
        return None

def analyze_image_with_gpt4_vision(image_bytes):
    """Uses GPT-4 Vision to create a text description"""
    try:
        b64_image = base64.b64encode(image_bytes).decode()
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in detail, focusing on pose, facial features, clothing, background, and composition."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}", "detail": "high"}}
                ]
            }],
            max_tokens=400
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return None, f"Image analysis failed: {e}"

def style_transfer_with_dalle3(description, style_prompt):
    """Uses DALL-E 3 to generate a new image"""
    try:
        full_prompt = f"{style_prompt}\n\nScene: {description}"[:4000]
        response = openai_client.images.generate(
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

# Page Rendering Functions
def render_style_selection_page():
    st.markdown('<h1 class="main-header">Welcome to Holomagic.AI</h1>', unsafe_allow_html=True)
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

    if st.session_state.selected_style:
        style_info = STYLE_PROMPTS[st.session_state.selected_style]
        st.success(f"Selected Style: {style_info['name']}")

    camera_photo = st.camera_input("📸 Position yourself and take a selfie")
    
    if camera_photo:
        st.session_state.captured_image_bytes = camera_photo.getvalue()
        st.session_state.current_page = 'result_display'
        st.rerun()

    if st.button("← Back to Style Selection", use_container_width=True):
        st.session_state.current_page = 'style_selection'
        st.rerun()

def render_results_page():
    st.markdown('<h1 class="main-header">Your AI Masterpiece</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-indicator">Step 3 of 3: Download Your Creation</p>', unsafe_allow_html=True)

    if not st.session_state.stylized_image_bytes:
        with st.spinner("🤖 AI is creating your masterpiece..."):
            # Analyze image
            description, error = analyze_image_with_gpt4_vision(st.session_state.captured_image_bytes)
            if error:
                st.error(f"❌ {error}")
                return

            # Generate styled image
            style_prompt = STYLE_PROMPTS[st.session_state.selected_style]['prompt']
            stylized_image, error = style_transfer_with_dalle3(description, style_prompt)
            if error:
                st.error(f"❌ {error}")
                return
            
            # Convert to bytes
            buffer = io.BytesIO()
            stylized_image.save(buffer, format="PNG")
            st.session_state.stylized_image_bytes = buffer.getvalue()

    # Display generated image
    st.image(st.session_state.stylized_image_bytes, use_container_width=True)

    # Upload to S3 and create QR code
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🔄 Create Another", use_container_width=True):
            # Reset session state
            for key in ['selected_style', 'captured_image_bytes', 'stylized_image_bytes']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.current_page = 'style_selection'
            st.rerun()
    
    with col2:
        with st.spinner("📤 Uploading to cloud..."):
            image_url, filename = upload_image_to_s3(
                st.session_state.stylized_image_bytes,
                st.session_state.selected_style
            )
        
        if image_url:
            qr_image = create_qr_code_with_url(image_url)
            if qr_image:
                st.markdown('<div class="qr-section">', unsafe_allow_html=True)
                st.markdown("### 📱 Scan to Download")
                st.image(qr_image, width=200)
                st.markdown("**Scan with your phone**")
                st.download_button(
                    label="⬇️ Download Image",
                    data=st.session_state.stylized_image_bytes,
                    file_name=filename if filename else "stylized_image.png",
                    mime="image/png",
                    use_container_width=True
                )
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.error("Failed to upload to cloud storage")

# Main App Router
if st.session_state.current_page == 'style_selection':
    render_style_selection_page()
elif st.session_state.current_page == 'image_capture':
    render_image_capture_page()
elif st.session_state.current_page == 'result_display':
    render_results_page()
