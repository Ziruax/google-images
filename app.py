import streamlit as st
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from PIL import Image, ImageFilter
from io import BytesIO
import re
import time

GOOGLE_IMAGE = "https://www.google.com/search?tbm=isch&"

def get_image_urls(query, num_images=50):
    """Fetch image URLs from Google Images using improved scraping techniques."""
    if num_images < 1 or num_images > 100:
        st.error("Number of images must be between 1 and 100.")
        return []
    
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
            
            # Extract from JSON structures in script tags
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
            time.sleep(1.5)

            if len(image_urls) < num_images and start >= 100:
                st.warning(f"Found {len(image_urls)} images. Google may have limited results.")
                break

        return list(set(image_urls))[:num_images]
    
    except Exception as e:
        st.error(f"Error fetching images: {str(e)}")
        return []

def process_image(url, target_width, target_height, enhance=True):
    """Improved image processing with better error handling."""
    try:
        headers = {"User-Agent": UserAgent().random}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content)).convert("RGB")
        orig_width, orig_height = img.size
        target_aspect = target_width / target_height
        orig_aspect = orig_width / orig_height

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
        
        return img
    except Exception as e:
        st.error(f"Failed to process {url}: {str(e)}")
        return None

def image_to_bytes(img):
    """Convert PIL image to bytes with quality optimization."""
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=85, optimize=True)
    return buffered.getvalue()

# Streamlit UI
st.title("Google Images Scraper & Processor")

with st.sidebar:
    st.header("Configuration")
    num_images = st.slider("Number of images to fetch", 1, 100, 50)
    enhance = st.checkbox("Enhance image quality", True)
    aspect_ratio = st.radio("Aspect Ratio", ["16:9", "9:16"], index=0)

query = st.text_input("Search query:", key="search_input")
target_size = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)

if st.button("Search and Process"):
    if not query:
        st.warning("Please enter a search query!")
    else:
        with st.spinner("Scraping Google Images..."):
            urls = get_image_urls(query, num_images)
        
        if not urls:
            st.error("No images found. Try a different query.")
            st.stop()
        
        processed_images = []
        progress_bar = st.progress(0)
        
        for i, url in enumerate(urls):
            with st.spinner(f"Processing image {i+1}/{len(urls)}..."):
                img = process_image(url, *target_size, enhance)
                if img:
                    processed_images.append(img)
            progress_bar.progress((i+1)/len(urls))
        
        if processed_images:
            st.success(f"Successfully processed {len(processed_images)} images")
            cols = st.columns(3)
            
            for idx, img in enumerate(processed_images):
                with cols[idx % 3]:
                    st.image(img, use_column_width=True)
                    img_bytes = image_to_bytes(img)
                    st.download_button(
                        label=f"Download Image {idx+1}",
                        data=img_bytes,
                        file_name=f"{query.replace(' ', '_')}_{idx+1}.jpg",
                        mime="image/jpeg",
                        key=f"download_{idx}"
                    )
        else:
            st.error("Failed to process any images. Try different settings.")
