import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

DATA_DIR = os.getcwd()
MAPPED_IMAGES_DIR = os.path.join(DATA_DIR, "data", "mappedimages")
os.makedirs(MAPPED_IMAGES_DIR, exist_ok=True)

def save_uploaded_image(file):
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = os.path.join(MAPPED_IMAGES_DIR, filename)
    file.save(filepath)
    logger.debug(f"Saved uploaded image to {filepath}")
    return filename

def get_latest_image():
    # Prefer the live screenshot "latest.jpg"
    latest_path = os.path.join(MAPPED_IMAGES_DIR, "latest.jpg")
    if os.path.exists(latest_path):
        return "latest.jpg"
    images = [f for f in os.listdir(MAPPED_IMAGES_DIR) if f.lower().endswith(('.jpg','.png'))]
    if images:
        return sorted(images)[-1]
    return None
