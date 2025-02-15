# cv_manager.py
import os
import cv2
import numpy as np
import logging
from datetime import datetime
from threading import Thread
import time

from adb_control import capture_screenshot  # assume this returns (filepath, result)

logger = logging.getLogger(__name__)

# Folder for storing template images for matching
DATA_DIR = os.getcwd()
LOOK4_DIR = os.path.join(DATA_DIR, "data", "mappedimages", "look4")
os.makedirs(LOOK4_DIR, exist_ok=True)

# Global CV mode
# Mode 1: Active (1 sec screenshot interval)
# Mode 2: Update (10 min–1 hr interval, configurable)
# Mode 3: Off (no updates)
current_mode = 3  # default mode is off

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
    """Temporarily set active mode (mode 1) for 'duration' seconds then revert to update mode (mode 2)."""
    set_mode(1)
    def revert():
        time.sleep(duration)
        set_mode(2)
    Thread(target=revert, daemon=True).start()

def take_screenshot_cv():
    """Call your adb_control function to take a screenshot and return its filename."""
    path, result = capture_screenshot()
    if path:
        logger.debug("CV module captured screenshot: %s", path)
        return path
    else:
        logger.error("CV module failed to capture screenshot")
        return None

def match_templates(screenshot_path, threshold=0.8):
    """
    Loads the screenshot and compares it against each template in LOOK4_DIR.
    Returns a dict: { template_filename: True/False } depending on whether match >= threshold.
    """
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
    """
    Crop the image from image_path at (x, y, width, height) (in original image coordinates)
    and save it to LOOK4_DIR with new_name.
    """
    image = cv2.imread(image_path)
    if image is None:
        logger.error("Cannot load image for cropping: %s", image_path)
        return None
    cropped = image[y:y+h, x:x+w]
    new_file = os.path.join(LOOK4_DIR, new_name)
    cv2.imwrite(new_file, cropped)
    logger.info("Saved cropped template as: %s", new_file)
    return new_file
