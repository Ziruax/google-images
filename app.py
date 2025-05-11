import streamlit as st
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from googlesearch import search
from PIL import Image, ImageFilter
from io import BytesIO
import zipfile
import time
import re

def get_image_urls(query, num_images=50):
    """Fetch image URLs from Google Images using web scraping."""
    if num_images < 1 or num_images > 50:
        st.error("Number of images must be between 1 and 50.")
        return []
    
    ua = UserAgent()
    headers = {"User-Agent": ua.random}
    image_urls = []
    
    try:
        # Use googlesearch-python to get Google Images search URL
        search_query = f"{query} site:*.jpg"  # Restrict to JPG images
        search_url = None
        for url in search(search_query, tld="com", num=1, stop=1, pause=2, tbm="isch"):
            search_url = url
            break
        
        if not search_url:
            st.warning("No search results found for the query.")
            return []
        
        # Fetch the Google Images page
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract image URLs from img tags
        img_tags = soup.find_all("img")
        for img in img_tags:
            src = img.get("src")
            if src and src.startswith("http") and src.endswith(".jpg"):
                image_urls.append(src)
                if len(image_urls) >= num_images:
                    break
        
        # Extract additional image URLs from script tags (JSON-like data)
        scripts = soup.find_all("script")
        for script in scripts:
            if "AF_initDataCallback" in script.text:
                # Extract JSON-like data containing image URLs
                matches = re.findall(r'"(https?://[^"]+\.jpg)"', script.text)
                for url in matches:
                    if url not in image_urls:
                        image_urls.append(url)
                        if len(image_urls) >= num_images:
                            break
            if len(image_urls) >= num_images:
                break
        
        # Simulate scrolling by making additional requests if needed
        if len(image_urls) < num_images:
            st.warning(f"Only found {len(image_urls)} images. Google may require scrolling or has limited results.")
        
        if not image_urls:
            st.warning("No images found for the query.")
            return []
        
        return image_urls[:num_images]
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching images: {e}")
        return []
    except Exception as e:
        st.error(f"Error processing search results: {e}")
        return []

def process_image(url, target_width, target_height, enhance=True):
    """Download, resize, crop, and optionally enhance the image."""
    try:
        ua = UserAgent()
        headers = {"User-Agent": ua.random}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        
        # Calculate original aspect ratio
        orig_width, orig_height = img.size
        orig_aspect = orig_width / orig_height
        target_aspect = target_width / target_height
        
        # Resize and crop based on aspect ratio
        if orig_aspect > target_aspect:
            new_height = target_height
            new_width = int(new_height * orig_aspect)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            left = (new_width - target_width) / 2
            right = left + target_width
            img = img.crop((left, 0, right, new_height))
        else:
            new_width = target_width
            new_height = int(new_width / orig_aspect)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            top = (new_height - target_height) / 2
            bottom = top + target_height
            img = img.crop((0, top, new_width, bottom))
        
        # Apply sharpening filter if enhancement is enabled
        if enhance:
            img = img.filter(ImageFilter.SHARPEN)
        return img
    except requests.exceptions.RequestException as e:
        st.error(f"Error downloading image {url}: {e}")
        return None
    except Exception as e:
        st.error(f"Error processing image {url}: {e}")
        return None

def image_to_bytes(img):
    """Convert PIL image to bytes for download."""
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return buffered.getvalue()

# Streamlit app layout
st.title("Google Images Downloader and Processor")

# Sidebar for controls
with st.sidebar:
    st.header("Settings")
    num_images = st.number_input("Number of images to fetch", min_value=1, max_value=50, value=50)
    enhance_images = st.checkbox("Enhance images (sharpen)", value=True)
    if st.button("Clear"):
        st.session_state.clear()
        st.experimental_rerun()

# User input for search query
query = st.text_input("Enter search query:")
if st.button("Search"):
    with st.spinner(f"Fetching {num_images} images..."):
        image_urls = get_image_urls(query, num_images)
    if image_urls:
        st.session_state.image_urls = image_urls
    else:
        st.session_state.image_urls = []
else:
    image_urls = st.session_state.get("image_urls", [])

# Display images for selection
if image_urls:
    st.write("### Select Images to Process")
    num_cols = min(3, len(image_urls))  # Dynamic columns based on image count
    cols = st.columns(num_cols)
    selected_images = []
    for i, url in enumerate(image_urls):
        with cols[i % num_cols]:
            try:
                st.image(url, use_column_width=True)
                if st.checkbox("Select", key=f"select_{url}"):
                    selected_images.append(url)
            except:
                st.warning(f"Failed to display image {i+1}")
    
    # Aspect ratio selection
    aspect_ratio = st.radio("Select aspect ratio:", ("16:9 (landscape)", "9:16 (portrait)"), index=0)
    if aspect_ratio == "16:9 (landscape)":
        target_width, target_height = 1920, 1080
    else:
        target_width, target_height = 1080, 1920
    
    # Process selected images
    if st.button("Process"):
        if not selected_images:
            st.warning("Please select at least one image to process.")
        else:
            with st.spinner("Processing images..."):
                processed_images = []
                for url in selected_images:
                    img = process_image(url, target_width, target_height, enhance_images)
                    if img:
                        processed_images.append(img)
            if processed_images:
                st.success(f"Successfully processed {len(processed_images)} images.")
                # Create zip file for download
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for i, img in enumerate(processed_images):
                        img_bytes = image_to_bytes(img)
                        zip_file.writestr(f"image_{i+1}.jpg", img_bytes)
                zip_buffer.seek(0)
                st.download_button(
                    label="Download All Images",
                    data=zip_buffer,
                    file_name="processed_images.zip",
                    mime="application/zip"
                )
                # Display processed images in a grid
                num_display_cols = min(3, len(processed_images))
                display_cols = st.columns(num_display_cols)
                for i, img in enumerate(processed_images):
                    with display_cols[i % num_display_cols]:
                        st.image(img, caption=f"Image {i+1}", use_column_width=True)
            else:
                st.error("No images were processed successfully.")
else:
    if query:
        st.info("No images to display. Try searching again.")
