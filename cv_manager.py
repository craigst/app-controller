import os
import cv2
import numpy as np
import logging
from datetime import datetime
from threading import Thread
import time
from adb_control import capture_screenshot  # assumes returns (filepath, result)

logger = logging.getLogger(__name__)

# Folder for storing template images for matching
DATA_DIR = os.getcwd()
LOOK4_DIR = os.path.join(DATA_DIR, "data", "mappedimages", "look4")
os.makedirs(LOOK4_DIR, exist_ok=True)

# Global CV mode: 1 = Active (updates every 5 sec), 2 = Update (configurable), 3 = Off.
current_mode = 3

def set_mode(mode):
    global current_mode
    if mode in [1, 2, 3]:
        current_mode = mode
        logger.info("CV mode set to %s", current_mode)
    else:
        logger.error("Invalid CV mode specified: %s", mode)

def get_mode():
    return current_mode

def start_active_mode(duration=10):
    set_mode(1)
    def revert():
        time.sleep(duration)
        set_mode(2)
    Thread(target=revert, daemon=True).start()

def take_screenshot_cv():
    path, result = capture_screenshot()
    if path and os.path.exists(path):
        logger.debug("CV module captured screenshot: %s", path)
        return path
    else:
        logger.error("CV module failed to capture screenshot")
        return None

def match_templates(screenshot_path, threshold=0.8):
    matches = {}
    screenshot = cv2.imread(screenshot_path, cv2.IMREAD_GRAYSCALE)
    if screenshot is None:
        logger.error("Cannot load screenshot for template matching: %s", screenshot_path)
        return matches
    for file in os.listdir(LOOK4_DIR):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            template_path = os.path.join(LOOK4_DIR, file)
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue
            if screenshot.shape[0] < template.shape[0] or screenshot.shape[1] < template.shape[1]:
                continue
            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            logger.debug("Template %s match value: %f", file, max_val)
            matches[file] = (max_val >= threshold)
    return matches

def crop_template(image_path, x, y, w, h, new_name):
    image = cv2.imread(image_path)
    if image is None:
        logger.error("Cannot load image for cropping: %s", image_path)
        return None
    if x < 0 or y < 0 or (x + w) > image.shape[1] or (y + h) > image.shape[0]:
        logger.error("Crop coordinates out of bounds for image: %s", image_path)
        return None
    cropped = image[y:y+h, x:x+w]
    if cropped.size == 0:
        logger.error("Cropped image is empty. Check your crop coordinates.")
        return None
    new_file = os.path.join(LOOK4_DIR, new_name)
    if cv2.imwrite(new_file, cropped):
        logger.info("Saved cropped template as: %s", new_file)
        return new_file
    else:
        logger.error("Failed to write cropped image to file: %s", new_file)
        return None

def delete_template(template_name):
    file_path = os.path.join(LOOK4_DIR, template_name)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info("Deleted template: %s", file_path)
            return True
        except Exception as e:
            logger.error("Error deleting template %s: %s", file_path, e)
            return False
    else:
        logger.error("Template file not found for deletion: %s", file_path)
        return False
