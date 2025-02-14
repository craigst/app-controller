import os
import json
import logging

logger = logging.getLogger(__name__)
BASE_DIR = os.getcwd()
CONFIG_DIR = os.path.join(BASE_DIR, "data", "config")
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
MACROS_FILE = os.path.join(CONFIG_DIR, "macros.json")

def load_macros():
    if os.path.exists(MACROS_FILE):
        try:
            with open(MACROS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error loading macros: " + str(e))
            return []
    else:
        return []

def save_macros(macros):
    with open(MACROS_FILE, "w") as f:
        json.dump(macros, f, indent=2)

def add_macro(name, description, commands):
    macros = load_macros()
    for macro in macros:
        if macro["name"] == name:
            return False, "Macro with that name already exists."
    new_macro = {"name": name, "description": description, "commands": commands}
    macros.append(new_macro)
    save_macros(macros)
    return True, "Macro added successfully."

def update_macro(old_name, new_name, new_description, new_commands):
    macros = load_macros()
    updated = False
    for macro in macros:
        if macro["name"] == old_name:
            macro["name"] = new_name
            macro["description"] = new_description
            macro["commands"] = new_commands
            updated = True
            break
    if updated:
        save_macros(macros)
        return True, "Macro updated successfully."
    else:
        return False, "Macro not found."

def delete_macro(macro_name):
    macros = load_macros()
    new_macros = [m for m in macros if m["name"] != macro_name]
    if len(new_macros) < len(macros):
        save_macros(new_macros)
        return True, "Macro deleted successfully."
    else:
        return False, "Macro not found."
