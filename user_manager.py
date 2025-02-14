import os
import json
import logging

logger = logging.getLogger(__name__)

DATA_DIR = os.getcwd()
CONFIG_DIR = os.path.join(DATA_DIR, "data", "config")
os.makedirs(CONFIG_DIR, exist_ok=True)
USERS_FILE = os.path.join(CONFIG_DIR, "users.json")

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try:
                users = json.load(f)
            except json.JSONDecodeError:
                users = []
    else:
        users = []
    return users

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def add_user(username, password):
    users = load_users()
    for user in users:
        if user["username"] == username:
            logger.error("User already exists.")
            return False
    users.append({"username": username, "password": password})
    save_users(users)
    return True

def get_user(username):
    users = load_users()
    for user in users:
        if user["username"] == username:
            return user
    return None
