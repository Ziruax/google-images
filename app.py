import streamlit as st
from google_images_download import google_images_download
from PIL import Image, ImageFilter
import requests
from io import BytesIO
import zipfile

# Initialize google images download
response = google_images_download.googleimagesdownload()

def get_image_urls(query, num_images=10):
    """Fetch image URLs from Google Images based on the query."""
    if num_images < 1 or num_images > 50:
        st.error("Number of images must be between 1 and 50.")
        return []
    arguments = {
        "keywords": query,
        "limit": num_images,
        "no_download": True,
        "print_urls": False,
        "format": "jpg"  # Ensure only JPG images for consistency
    }
    try:
        result = response.download(arguments)
        # Check if result is a tuple (paths, errors) or a dictionary
        if isinstance(result, tuple):
            paths, errors = result
            if errors:
                st.warning(f"Some errors occurred while fetching images: {errors}")
            if not paths.get(query):
                st.warning("No images found for the query.")
                return []
            return paths[query]
        else:
            # Handle dictionary case (older behavior)
            if not result.get(query):
                st.warning("No images found for the query.")
                return []
            return result[query]
    except Exception as e:
        st.error(f"Error fetching images: {str(e)}")
        return []

def process_image(url, target_width, target_height, enhance=True):
    """Download, resize, crop, and optionally enhance the image."""
    try:
        response = requests.get(url, timeout=10)
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
    num_images = st.number_input("Number of images to fetch", min_value=1, max_value=50, value=10)
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
