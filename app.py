import streamlit as st
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from PIL import Image, ImageFilter
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

def process_image(url, target_width, target_height, enhance=True):
    """Process image with error collection."""
    try:
        headers = {"User-Agent": UserAgent().random}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content)).convert("RGB")
        orig_width, orig_height = img.size
        target_aspect = target_width / target_height
        orig_aspect = orig_width / orig_height

        # Maintain existing processing logic
        if orig_aspect > target_aspect:
            new_height = target_height
            new_width = int(orig_width * (target_height / orig_height))
            img = img.resize((new_width, new_height), Image.LANCZOS)
            left = (new_width - target_width) // 2
            img = img.crop((left, 0, left + target_width, target_height))
        else:
            new_width = target_width
            new_height = int(orig_height * (target_width / orig_width))
            img = img.resize((new_width, new_height), Image.LANCZOS)
            top = (new_height - target_height) // 2
            img = img.crop((0, top, target_width, top + target_height))

        if enhance:
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        
        return img, None
    except Exception as e:
        return None, f"Failed to process {url}: {str(e)}"

# Improved UI Layout
st.set_page_config(page_title="Image Scraper", layout="wide")
st.title("📷 Advanced Google Images Scraper")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Settings")
    with st.expander("Scraping Parameters", expanded=True):
        num_images = st.slider("Number of images", 1, 100, 20,
                              help="Choose how many images to scrape from Google")
        
    with st.expander("Processing Options", expanded=True):
        enhance = st.checkbox("Enhance images", True,
                            help="Apply sharpening filter for better quality")
        aspect_ratio = st.radio("Aspect Ratio", ["16:9", "9:16"], index=0,
                               help="Choose orientation for processed images")

# Main Interface
query = st.text_input("🔍 Search Query:", placeholder="Enter your search term...", key="search_input")
target_size = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)

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
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, url in enumerate(urls):
        status_text.markdown(f"🔧 Processing image {i+1}/{len(urls)}...")
        img, error = process_image(url, *target_size, enhance)
        if img:
            processed_images.append(img)
        if error:
            all_errors.append(error)
        progress_bar.progress((i+1)/len(urls))
    
    st.markdown("---")
    if processed_images:
        st.success(f"✅ Successfully processed {len(processed_images)}/{len(urls)} images")
        
        # Dynamic image grid
        cols_per_row = 3
        cols = st.columns(cols_per_row)
        
        for idx, img in enumerate(processed_images):
            with cols[idx % cols_per_row]:
                st.image(img, use_column_width=True)
                img_bytes = BytesIO()
                img.save(img_bytes, format="JPEG", quality=85, optimize=True)
                st.download_button(
                    label=f"⬇️ Download Image {idx+1}",
                    data=img_bytes.getvalue(),
                    file_name=f"{query.replace(' ', '_')}_{idx+1}.jpg",
                    mime="image/jpeg",
                    key=f"download_{idx}"
                )
    else:
        st.error("❌ Failed to process any images. Check settings and try again.")
    
    # Show errors in expander
    if all_errors:
        with st.expander("⚠️ View Errors/Warnings", expanded=False):
            for error in all_errors:
                st.markdown(f"- {error}")

st.markdown("---")
st.caption("Note: This tool is for educational purposes only. Respect website terms of service and copyright laws.")
