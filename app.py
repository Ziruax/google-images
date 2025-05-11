import streamlit as st
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from fake_useragent import UserAgent
from PIL import Image, ImageFilter
from io import BytesIO
import re
import time
import json

# Configuration
GOOGLE_IMAGE = "https://www.google.com/search?tbm=isch&"
MAX_WORKERS = 5  # For concurrent processing
SESSION_STATE = st.session_state

# Initialize session state variables
if 'errors' not in SESSION_STATE:
    SESSION_STATE.errors = []
if 'processed' not in SESSION_STATE:
    SESSION_STATE.processed = []
if 'metadata' not in SESSION_STATE:
    SESSION_STATE.metadata = {}

def clear_state():
    SESSION_STATE.errors.clear()
    SESSION_STATE.processed.clear()
    SESSION_STATE.metadata.clear()

def get_image_urls(query, num_images=100):
    """High-performance image URL scraping with advanced parsing"""
    clear_state()
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "DNT": "1",
    }
    
    try:
        search_url = f"{GOOGLE_IMAGE}q={query}"
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Extract JSON data from script tags
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        image_data = []
        pattern = re.compile(r'AF_initDataCallback\({key: \'ds:1\', data:(.*?), sideChannel: {}}\);')
        
        for script in scripts:
            if match := pattern.search(script.text):
                try:
                    data = json.loads(match.group(1))
                    images = data[31][0][12][2]
                    image_data.extend(images)
                except (json.JSONDecodeError, IndexError) as e:
                    SESSION_STATE.errors.append(f"JSON parsing error: {str(e)}")
        
        # Extract URLs from JSON structure
        urls = []
        for img in image_data[:num_images]:
            try:
                url = img[1][3][0]
                if url.startswith('http'):
                    urls.append(url)
            except (IndexError, TypeError):
                continue
        
        return list(dict.fromkeys(urls))[:num_images]  # Remove duplicates while preserving order
    
    except Exception as e:
        SESSION_STATE.errors.append(f"Scraping failed: {str(e)}")
        return []

def process_image_wrapper(args):
    """Wrapper for parallel image processing"""
    url, target_size, enhance = args
    try:
        headers = {"User-Agent": UserAgent().random}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        
        # Smart cropping and resizing
        img = ImageOps.exif_transpose(img)  # Fix orientation
        img.thumbnail((target_size[0]*2, target_size[1]*2), Image.LANCZOS)
        
        # Center crop
        left = (img.width - target_size[0])/2
        top = (img.height - target_size[1])/2
        right = (img.width + target_size[0])/2
        bottom = (img.height + target_size[1])/2
        img = img.crop((left, top, right, bottom))
        
        if enhance:
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        
        return img
    except Exception as e:
        SESSION_STATE.errors.append(f"Failed to process {url[:50]}...: {str(e)}")
        return None

def image_to_bytes(img, format='JPEG', quality=85):
    """Optimized image serialization"""
    buffered = BytesIO()
    img.save(buffered, format=format, quality=quality, optimize=True)
    return buffered.getvalue()

# Streamlit UI
st.set_page_config(page_title="Ultra Image Scraper", page_icon="🚀", layout="wide")

with st.sidebar:
    st.title("⚙️ Settings")
    query = st.text_input("🔍 Search Query", help="Enter what you want to search for")
    num_images = st.slider("📷 Number of Images", 1, 200, 50)
    aspect_ratio = st.selectbox("📐 Aspect Ratio", ["16:9", "9:16", "1:1", "4:3"])
    enhance = st.toggle("✨ Enhance Quality", True)
    img_format = st.radio("🖼️ Format", ["JPEG", "PNG"], index=0)
    img_quality = st.slider("🎯 Quality", 1, 100, 85)
    
    if st.button("🚀 Start Scraping", use_container_width=True):
        clear_state()
        SESSION_STATE.metadata['start_time'] = time.time()

# Main content area
st.title("🚀 Ultra Fast Image Scraper")
st.markdown("---")

# Aspect ratio mapping
size_mapping = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1024, 1024),
    "4:3": (1600, 1200)
}
target_size = size_mapping[aspect_ratio]

if 'start_time' in SESSION_STATE.metadata:
    with st.status("🔥 Scraping in progress...", expanded=True) as status:
        # Phase 1: Scraping
        st.write("🌐 Connecting to Google Images...")
        urls = get_image_urls(query, num_images)
        
        # Phase 2: Parallel Processing
        if urls:
            st.write(f"⚡ Processing {len(urls)} images with {MAX_WORKERS} threads...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                args = [(url, target_size, enhance) for url in urls]
                results = list(executor.map(process_image_wrapper, args))
                
            SESSION_STATE.processed = [img for img in results if img is not None]
            status.update(label="✅ Processing complete!", state="complete", expanded=False)

# Show results
if SESSION_STATE.processed:
    st.success(f"✨ Successfully processed {len(SESSION_STATE.processed)} images")
    
    # Performance metrics
    duration = time.time() - SESSION_STATE.metadata['start_time']
    st.metric("⏱️ Total Time", f"{duration:.2f} seconds")
    
    # Image grid
    cols = st.columns(4)
    for idx, img in enumerate(SESSION_STATE.processed):
        with cols[idx % 4]:
            st.image(img, use_column_width=True)
            img_bytes = image_to_bytes(img, img_format, img_quality)
            ext = img_format.lower()
            st.download_button(
                label=f"📥 Download #{idx+1}",
                data=img_bytes,
                file_name=f"{query.replace(' ', '_')}_{idx+1}.{ext}",
                mime=f"image/{ext}",
                use_container_width=True
            )

# Error display system
if SESSION_STATE.errors:
    with st.expander("⚠️ Error Log", expanded=False):
        error_counts = {}
        for error in SESSION_STATE.errors:
            error_counts[error] = error_counts.get(error, 0) + 1
        
        for error, count in error_counts.items():
            st.error(f"{error} (occurred {count} times)")

# UI Enhancements
st.markdown("---")
with st.container():
    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("♻️ Clear Results", on_click=clear_state, use_container_width=True)
    with col2:
        st.button("📊 Show Stats", use_container_width=True, 
                 help="Show detailed performance statistics")
    with col3:
        st.link_button("📚 Documentation", "https://example.com", use_container_width=True)

# Theme customization
st.markdown("""
<style>
    [data-testid=stSidebar] {
        background: linear-gradient(45deg, #1a1a1a, #2a2a2a) !important;
    }
    .stDownloadButton button {
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)
