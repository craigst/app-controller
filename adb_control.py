import os
import subprocess
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuration values
ADB_DEVICE = "192.168.1.96:5555"
APK_NAME = "BCATrack.apk"
APK_PACKAGE = "com.bca.bcatrack"
SLEEP_TIME = 1

# Directories
BASE_DIR = os.getcwd()
APK_DIR = os.path.join(BASE_DIR, "data", "apk")
MAPPED_IMAGES_DIR = os.path.join(BASE_DIR, "data", "mappedimages")
CURRENT_DB_DIR = os.path.join(BASE_DIR, "data", "currentdatabase")
for d in [APK_DIR, MAPPED_IMAGES_DIR, CURRENT_DB_DIR]:
    os.makedirs(d, exist_ok=True)
    logger.debug(f"Ensured directory exists: {d}")

def run_adb_command(cmd, sleep=SLEEP_TIME):
    full_cmd = cmd if isinstance(cmd, str) else " ".join(cmd)
    logger.debug(f"Executing command: {full_cmd}")
    try:
        result = subprocess.run(full_cmd, shell=True, text=True, capture_output=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"Error running command: {result.stderr}")
        time.sleep(sleep)
        return result.stdout.strip()
    except Exception as e:
        logger.exception(f"Command execution failed: {e}")
        return None

def adb_connect():
    devices = run_adb_command("adb devices")
    if devices is None or ADB_DEVICE not in devices or "offline" in devices:
        logger.debug(f"ADB device {ADB_DEVICE} not connected; attempting to connect.")
        run_adb_command(f"adb connect {ADB_DEVICE}")
    else:
        logger.debug(f"ADB device {ADB_DEVICE} already connected.")

def is_app_installed():
    output = run_adb_command("adb shell pm list packages")
    installed = APK_PACKAGE in output if output else False
    logger.debug(f"Is app installed? {installed}")
    return installed

def install_app():
    if not is_app_installed():
        apk_path = os.path.join(APK_DIR, APK_NAME)
        if not os.path.exists(apk_path):
            logger.debug(f"APK not found at {apk_path}. Downloading...")
            run_adb_command(f"wget -O \"{apk_path}\" https://ha.evoonline.co.uk/local/BCATrack.apk")
        result = run_adb_command(f"adb install \"{apk_path}\"")
        # Grant permissions
        perms = [
            f"adb shell pm grant {APK_PACKAGE} android.permission.READ_EXTERNAL_STORAGE",
            f"adb shell pm grant {APK_PACKAGE} android.permission.WRITE_EXTERNAL_STORAGE",
            f"adb shell appops set {APK_PACKAGE} READ_EXTERNAL_STORAGE allow",
            f"adb shell appops set {APK_PACKAGE} WRITE_EXTERNAL_STORAGE allow",
        ]
        for p in perms:
            run_adb_command(p)
        logger.debug("App installed and permissions granted.")
        return result
    else:
        logger.debug("App already installed.")
        return "App already installed."

def start_app():
    logger.debug("Starting app...")
    return run_adb_command(f"adb shell am start -n {APK_PACKAGE}/com.lansa.ui.Activity")

def stop_app():
    logger.debug("Stopping app...")
    return run_adb_command(f"adb shell am force-stop {APK_PACKAGE}")

def uninstall_app():
    if is_app_installed():
        logger.debug("Uninstalling app...")
        return run_adb_command(f"adb shell pm uninstall {APK_PACKAGE}")
    else:
        logger.debug("App not installed; nothing to uninstall.")
        return "App not installed."

def login_macro_normal(username, password):
    cmds = [
        "adb shell input keyevent 61",
        f'adb shell input text "{username}"',
        "adb shell input keyevent 61",
        f'adb shell input text "{password}"',
        "adb shell input tap 702 1311"
    ]
    output = ""
    for cmd in cmds:
        out = run_adb_command(cmd)
        output += out + "\n"
    logger.debug("Normal login macro executed.")
    return output

def capture_screenshot():
    # Always save as "latest.jpg"
    screenshot_path = os.path.join(MAPPED_IMAGES_DIR, "latest.jpg")
    cmd_capture = (
        f"adb shell screencap -p /sdcard/screen.jpg && "
        f"adb pull /sdcard/screen.jpg \"{screenshot_path}\" && "
        "adb shell rm /sdcard/screen.jpg"
    )
    result = run_adb_command(cmd_capture)
    logger.debug(f"Screenshot captured to {screenshot_path}")
    return screenshot_path, result

def get_latest_screenshot():
    screenshot_path = os.path.join(MAPPED_IMAGES_DIR, "latest.jpg")
    if os.path.exists(screenshot_path):
        return "latest.jpg"
    return None

def pull_database():
    """
    Pull the BCA app database from the device.
    Since the file is in a protected location, we first copy it to /sdcard using root privileges.
    This version uses su 0.
    """
    source_path = "/data/data/com.bca.bcatrack/cache/cache/data/sql.db"
    intermediate_path = "/sdcard/sql.db"
    dest_path = os.path.join(CURRENT_DB_DIR, "sql.db")
    
    cmd_copy = f'adb shell "su 0 cp {source_path} {intermediate_path}"'
    result_copy = run_adb_command(cmd_copy)
    logger.debug(f"Copy result: {result_copy}")
    
    cmd_pull = f'adb pull {intermediate_path} "{dest_path}"'
    result_pull = run_adb_command(cmd_pull)
    logger.debug(f"Pull result: {result_pull}")
    
    cmd_rm = f'adb shell "su 0 rm {intermediate_path}"'
    result_rm = run_adb_command(cmd_rm)
    logger.debug(f"Remove intermediate result: {result_rm}")
    
    if os.path.exists(dest_path):
        logger.debug(f"Database pulled successfully to {dest_path}")
        return dest_path, result_pull
    else:
        logger.error(f"Failed to pull database from {source_path} to {dest_path}. Result: {result_pull}")
        return None, result_pull


def get_adb_status():
    status = {}
    adb_version = run_adb_command("adb version")
    status['adb_installed'] = bool(adb_version)
    devices = run_adb_command("adb devices")
    if devices and ADB_DEVICE in devices and "device" in devices:
        status['phone_online'] = True
    else:
        status['phone_online'] = False
    status['app_installed'] = is_app_installed()
    pid = run_adb_command(f"adb shell pidof {APK_PACKAGE}")
    status['app_running'] = bool(pid.strip()) if pid else False
    return status
