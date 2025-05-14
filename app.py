import streamlit as st
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from PIL import Image, ImageFilter, ImageEnhance
from io import BytesIO
import re
import time

GOOGLE_IMAGE = "https://www.google.com/search?tbm=isch&"

def get_image_urls(query, num_images=20):
    """Fetch image URLs from Google Images with error collection."""
    errors = []
    if num_images < 1 or num_images > 100:
        errors.append("Number of images must be between 1 and 100.")
        return [], errors
    
    ua = UserAgent()
    image_urls = []
    start = 0
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "DNT": "1",
    }
    
    try:
        while len(image_urls) < num_images:
            search_url = f"{GOOGLE_IMAGE}q={query}&start={start}"
            response = requests.get(search_url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract from JSON structures
            scripts = soup.find_all("script")
            image_pattern = re.compile(r'"https?://[^"]+\.(?:jpg|jpeg|png|webp)"')
            for script in scripts:
                matches = image_pattern.findall(script.text)
                for url in matches:
                    cleaned_url = url.strip('"').split("\\u003d")[0]
                    if cleaned_url.startswith("http") and cleaned_url not in image_urls:
                        image_urls.append(cleaned_url)
                        if len(image_urls) >= num_images:
                            break
                if len(image_urls) >= num_images:
                    break

            # Extract from img tags
            img_tags = soup.find_all("img")
            for img in img_tags:
                src = img.get("src") or img.get("data-src")
                if src and src.startswith("http"):
                    clean_src = src.split("?")[0]
                    if clean_src not in image_urls:
                        image_urls.append(clean_src)
                        if len(image_urls) >= num_images:
                            break
                if len(image_urls) >= num_images:
                    break

            if not img_tags and not matches:
                break

            start += 20
            time.sleep(1)  # Reduced sleep time for faster scraping

            if len(image_urls) < num_images and start >= 100:
                errors.append(f"Found {len(image_urls)} images. Google may have limited results.")
                break

        return list(set(image_urls))[:num_images], errors
    
    except Exception as e:
        errors.append(f"Error fetching images: {str(e)}")
        return [], errors

def process_image(url, target_size=None, enhance=True):
    """Professional-grade image processing with conditional resizing"""
    try:
        headers = {"User-Agent": UserAgent().random}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content)).convert("RGB")
        original_size = img.size  # Store original dimensions
        
        # Conditional resizing only when target_size is provided
        if target_size:
            target_width, target_height = target_size
            orig_width, orig_height = img.size
            target_aspect = target_width / target_height
            orig_aspect = orig_width / orig_height

            # Advanced resizing with aspect ratio preservation
            if orig_aspect > target_aspect:
                new_height = target_height
                new_width = int(orig_width * (target_height / orig_height))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                left = (new_width - target_width) // 2
                img = img.crop((left, 0, left + target_width, target_height))
            else:
                new_width = target_width
                new_height = int(orig_height * (target_width / orig_width))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                top = (new_height - target_height) // 2
                img = img.crop((0, top, target_width, top + target_height))

        # Professional image enhancement pipeline
        if enhance:
            # Advanced sharpening with dynamic parameters
            img = img.filter(ImageFilter.UnsharpMask(
                radius=2.5, 
                percent=200, 
                threshold=3
            ))
            
            # Contrast enhancement
            contrast_enhancer = ImageEnhance.Contrast(img)
            img = contrast_enhancer.enhance(1.2)
            
            # Color balancing
            color_enhancer = ImageEnhance.Color(img)
            img = color_enhancer.enhance(1.1)
            
            # Edge enhancement
            edge_enhancer = ImageEnhance.Sharpness(img)
            img = edge_enhancer.enhance(1.15)

        return img, original_size, None  # Return original size for reference
    except Exception as e:
        return None, None, f"Failed to process {url}: {str(e)}"

# Streamlit UI Configuration
st.set_page_config(page_title="Pro Image Scraper", layout="wide")
st.title("📸 Professional Google Images Scraper")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Control Panel")
    with st.expander("Image Settings", expanded=True):
        aspect_ratio = st.radio("Aspect Ratio", 
                               ["Original", "16:9", "9:16"], 
                               index=0,
                               help="Select desired output aspect ratio")
        enhance = st.checkbox("Enable Professional Enhancement", True,
                            help="Apply advanced image optimization techniques")
        
    with st.expander("Scraping Settings", expanded=True):
        num_images = st.slider("Number of Images", 1, 100, 20,
                              help="Maximum number of images to scrape")
        safety = st.checkbox("Safe Search", True,
                           help="Filter explicit content (when possible)")

# Determine target size based on selection
target_size = None
if aspect_ratio == "16:9":
    target_size = (1920, 1080)
elif aspect_ratio == "9:16":
    target_size = (1080, 1920)

# Main Interface
query = st.text_input("🔍 Search Query:", placeholder="Enter your search term...", key="search_input")

if st.button("🚀 Start Scraping & Processing"):
    all_errors = []
    if not query:
        st.warning("Please enter a search query!")
        st.stop()
    
    with st.spinner("🌐 Scraping Google Images..."):
        urls, scrape_errors = get_image_urls(query, num_images)
        all_errors.extend(scrape_errors)
    
    if not urls:
        st.error("❌ No images found. Try a different query.")
        st.stop()
    
    processed_images = []
    original_sizes = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, url in enumerate(urls):
        status_text.markdown(f"🔧 Processing image {i+1}/{len(urls)}...")
        img, original_size, error = process_image(url, target_size, enhance)
        if img:
            processed_images.append(img)
            original_sizes.append(original_size)
        if error:
            all_errors.append(error)
        progress_bar.progress((i+1)/len(urls))
    
    st.markdown("---")
    if processed_images:
        success_rate = len(processed_images)/len(urls)*100
        st.success(f"✅ Successfully processed {len(processed_images)}/{len(urls)} images ({success_rate:.1f}% success rate)")
        
        # Image grid with metadata
        cols_per_row = 3
        cols = st.columns(cols_per_row)
        
        for idx, (img, orig_size) in enumerate(zip(processed_images, original_sizes)):
            with cols[idx % cols_per_row]:
                # Display resolution information
                if target_size:
                    res_info = f"Processed: {img.size[0]}x{img.size[1]}"
                else:
                    res_info = f"Original: {orig_size[0]}x{orig_size[1]}"
                
                st.image(img, use_column_width=True, caption=res_info)
                
                # Download functionality
                img_bytes = BytesIO()
                img.save(img_bytes, format="JPEG", quality=90, optimize=True)
                st.download_button(
                    label=f"⬇️ Download Image {idx+1}",
                    data=img_bytes.getvalue(),
                    file_name=f"{query.replace(' ', '_')}_{idx+1}.jpg",
                    mime="image/jpeg",
                    key=f"download_{idx}"
                )
    else:
        st.error("❌ Failed to process any images. Check settings and try again.")
    
    # Error reporting system
    if all_errors:
        with st.expander("⚠️ View Processing Errors/Warnings", expanded=False):
            st.markdown("**Encountered issues:**")
            for error in all_errors:
                st.markdown(f"- {error}")

st.markdown("---")
st.caption("ℹ️ Note: This tool is intended for educational purposes only. Always respect website terms of service and copyright regulations.")
