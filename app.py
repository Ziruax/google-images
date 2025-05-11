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

GOOGLE_IMAGE = "https://www.google.com/search?tbm=isch&"

# Session state management
if 'errors' not in st.session_state:
    st.session_state.errors = []
if 'processed' not in st.session_state:
    st.session_state.processed = []

def clear_errors():
    st.session_state.errors = []

def get_image_urls(query, num_images=50):
    """Improved Google Images scraper with JSON parsing"""
    try:
        ua = UserAgent()
        headers = {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
        }
        
        response = requests.get(f"{GOOGLE_IMAGE}q={query}", headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract JSON data from script tags
        scripts = soup.find_all('script')
        image_urls = []
        image_pattern = re.compile(r'\[\"https?://[^"]+\.(?:jpg|jpeg|png|webp)')
        
        for script in scripts:
            if 'AF_initDataCallback' in script.text:
                try:
                    json_str = script.text.split('AF_initDataCallback(')[1].split('data:')[1].split(', sideChannel:')[0].strip()
                    data = json.loads(json_str)
                    # Navigate through JSON structure to find image URLs
                    for item in data[31][0][12][2]:
                        try:
                            url = item[1][3][0]
                            if url.startswith('http'):
                                image_urls.append(url)
                        except (IndexError, TypeError):
                            continue
                except Exception as e:
                    st.session_state.errors.append(f"JSON parse error: {str(e)}")
                    continue
        
        # Fallback to img tag extraction
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src') or img.get('data-src')
            if src and src.startswith('http'):
                image_urls.append(src.split('?')[0])
        
        # Remove duplicates while preserving order
        seen = set()
        return [x for x in image_urls if not (x in seen or seen.add(x))][:num_images]
    
    except Exception as e:
        st.session_state.errors.append(f"Scraping failed: {str(e)}")
        return []

def process_image(url):
    """Fast image processing with error handling"""
    try:
        headers = {"User-Agent": UserAgent().random}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content)).convert("RGB")
        img = img.resize(target_size, Image.LANCZOS)
        
        if enhance:
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        
        return img
    except Exception as e:
        st.session_state.errors.append(f"Image processing failed: {str(e)}")
        return None

# Streamlit UI
st.set_page_config(page_title="Ultra Image Scraper", layout="wide")
st.title("🔍 Google Images Scraper Pro")

# Main search section
with st.container():
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Search query:", key="search_input", placeholder="Enter search term...")
    with col2:
        st.write("\n")
        if st.button("🚀 Start Scraping", use_container_width=True):
            clear_errors()
            st.session_state.processed = []

# Sidebar filters
with st.sidebar:
    st.header("⚙️ Settings")
    num_images = st.slider("Number of images", 1, 100, 20)
    target_size = st.selectbox("Image size:", 
                             options=[(1920, 1080), (1080, 1920), (1024, 1024)],
                             format_func=lambda x: f"{x[0]}x{x[1]}")
    enhance = st.checkbox("Enhance images", True)
    st.markdown("---")
    st.caption("Advanced Options")
    max_workers = st.slider("Processing threads", 1, 8, 4)

# Results display
if query and st.session_state.get('processed') is None:
    with st.spinner(f"🔎 Searching Google for '{query}'..."):
        urls = get_image_urls(query, num_images)
        
    if urls:
        with st.spinner(f"⚡ Processing {len(urls)} images..."):
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(process_image, urls))
            
            st.session_state.processed = [img for img in results if img is not None]
            
        if not st.session_state.processed:
            st.error("No images processed successfully. Check error log.")
    else:
        st.error("No images found. Try different search terms.")

# Display processed images
if st.session_state.processed:
    st.success(f"✅ Successfully processed {len(st.session_state.processed)} images")
    
    cols = st.columns(4)
    for idx, img in enumerate(st.session_state.processed):
        with cols[idx % 4]:
            st.image(img, use_column_width=True)
            img_bytes = BytesIO()
            img.save(img_bytes, format="JPEG", quality=85)
            st.download_button(
                label=f"📥 Image {idx+1}",
                data=img_bytes.getvalue(),
                file_name=f"{query.replace(' ', '_')}_{idx+1}.jpg",
                mime="image/jpeg",
                key=f"dl_{idx}"
            )

# Error display system
if st.session_state.errors:
    with st.expander("⚠️ Error Log", expanded=False):
        for error in list(set(st.session_state.errors))[:10]:  # Show unique errors
            st.error(error)
        if len(st.session_state.errors) > 10:
            st.warning(f"Showing first 10 of {len(st.session_state.errors)} errors")
        if st.button("Clear Errors", on_click=clear_errors):
            pass

# Style enhancements
st.markdown("""
<style>
    [data-testid=stSidebar] {
        background: #f0f2f6 !important;
    }
    .stDownloadButton > button {
        width: 100% !important;
    }
    .st-emotion-cache-1kyxrkd {
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)
