import os
import logging
import threading
import time
import sqlite3
import datetime
from flask import Flask, render_template, redirect, url_for, flash, jsonify, request, abort, send_from_directory
import macro_manager
import adb_control
import image_mapping
import db_manager
import user_manager
import load_manager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Starting main web UI application...")

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change for production

# --------------------- Routes ---------------------

@app.route("/")
def index():
    return redirect(url_for("adb_tab"))

@app.route("/status")
def status():
    status_dict = adb_control.get_adb_status()
    status_dict['sql_online'] = db_manager.test_sql_connection()
    autosync_enabled, autosync_interval = db_manager.load_autosync()
    status_dict['autosync_enabled'] = autosync_enabled
    status_dict['autosync_interval'] = autosync_interval
    return jsonify(status_dict)

@app.route("/adb", methods=["GET", "POST"])
def adb_tab():
    if request.method == "POST":
        action = request.form.get("action")
        adb_control.adb_connect()
        if action == "install":
            result = adb_control.install_app()
        elif action == "start":
            result = adb_control.start_app()
        elif action == "stop":
            result = adb_control.stop_app()
        elif action == "restart":
            result = adb_control.stop_app() + "\n" + adb_control.start_app()
        elif action == "uninstall":
            result = adb_control.uninstall_app()
        elif action == "login":
            selected_user = request.form.get("user_select")
            if selected_user:
                user = user_manager.get_user(selected_user)
                if user:
                    result = adb_control.login_macro_normal(user["username"], user["password"])
                else:
                    result = "Selected user not found."
        elif action == "capture":
            cap_path, cap_result = adb_control.capture_screenshot()
            result = f"Screenshot saved as {os.path.basename(cap_path)}"
        flash(result)
        return redirect(url_for("adb_tab"))
    users = user_manager.load_users()
    macros = macro_manager.load_macros()  # load all macros
    latest_screenshot = adb_control.get_latest_screenshot()
    return render_template("adb_tab.html", latest_screenshot=latest_screenshot, users=users, macro_list=macros)

# New endpoint for serving images
@app.route("/mapped_image/<filename>")
def mapped_image(filename):
    mapped_dir = os.path.join(os.getcwd(), "data", "mappedimages")
    # send_from_directory will serve the file if it exists.
    return send_from_directory(mapped_dir, filename)

@app.route("/add_user", methods=["POST"])
def add_user():
    new_username = request.form.get("new_username")
    new_password = request.form.get("new_password")
    if not new_username or not new_password:
        flash("Both username and password are required.")
    else:
        if user_manager.add_user(new_username, new_password):
            flash(f"User {new_username} added successfully.")
        else:
            flash("User already exists.")
    return redirect(url_for("adb_tab"))

@app.route("/add_macro", methods=["POST"])
def add_macro():
    name = request.form.get("macro_name")
    description = request.form.get("macro_description")
    commands = request.form.get("macro_commands")
    if not name or not commands:
        flash("Name and commands are required.")
    else:
        success, msg = macro_manager.add_macro(name, description, commands)
        flash(msg)
    return redirect(url_for("adb_tab"))
# New endpoint to run a macro
@app.route("/run_macro", methods=["POST"])
def run_macro():
    macro_name = request.form.get("macro_name")
    macros = macro_manager.load_macros()
    selected_macro = next((m for m in macros if m["name"] == macro_name), None)
    if not selected_macro:
        flash("Macro not found.")
    else:
        output = ""
        for cmd in selected_macro["commands"].splitlines():
            cmd = cmd.strip()
            if not cmd:
                continue
            if cmd.lower().startswith("sleep ") or cmd.lower().startswith("wait "):
                try:
                    parts = cmd.split()
                    seconds = float(parts[1])
                    import time
                    time.sleep(seconds)
                    output += f"Slept for {seconds} seconds.\n"
                except Exception as e:
                    output += f"Error executing sleep command: {e}\n"
            else:
                out = adb_control.run_adb_command(cmd)
                output += out + "\n"
        flash("Macro executed. Output: " + output)
    return redirect(url_for("adb_tab"))

@app.route("/edit_macro", methods=["POST"])
def edit_macro():
    old_name = request.form.get("old_macro_name")
    new_name = request.form.get("macro_name")
    new_description = request.form.get("macro_description")
    new_commands = request.form.get("macro_commands")
    action = request.form.get("action_type")  # "save" or "delete"
    if action == "save":
        success, msg = macro_manager.update_macro(old_name, new_name, new_description, new_commands)
    elif action == "delete":
        success, msg = macro_manager.delete_macro(old_name)
    else:
        success, msg = False, "Invalid action."
    flash(msg)
    return redirect(url_for("adb_tab"))


# (Keep your autosync thread and other routes as before)
@app.route("/pull_db", methods=["POST"])
def pull_db():
    dest, result = adb_control.pull_database()
    if dest:
        db_manager.record_last_pull()
        flash("Database pulled successfully.")
    else:
        flash("Failed to pull database. " + (result or ""))
    return redirect(url_for("db_tab"))

@app.route("/image", methods=["GET", "POST"])
def image_tab():
    if request.method == "POST":
        if "screenshot" in request.files:
            file = request.files["screenshot"]
            filename = image_mapping.save_uploaded_image(file)
            flash(f"Saved screenshot as {filename}.")
        elif request.form.get("coords"):
            coords = request.form.get("coords")
            flash(f"Coordinates captured: {coords}.")
        return redirect(url_for("image_tab"))
    latest = image_mapping.get_latest_image()
    macros = macro_manager.load_macros()
    new_timestamp = datetime.datetime.now().timestamp()
    return render_template("image_tab.html", latest=latest, macro_list=macros, new_timestamp=new_timestamp)

@app.route("/latest_image")
def latest_image():
    from image_mapping import get_latest_image
    filename = get_latest_image()
    return jsonify({"filename": filename})

@app.route("/loads", methods=["GET"])
def loads_tab():
    week_ending = request.args.get("weekEnding")
    if not week_ending:
        # Default: upcoming Sunday (or today if Sunday)
        week_ending = datetime.datetime.today().strftime("%Y-%m-%d")
    loads = load_manager.get_loads_for_week(week_ending)
    return render_template("loads_tab.html", loads=loads, week_ending=week_ending)
@app.route("/db", methods=["GET", "POST"])
def db_tab():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "backup":
            note = request.form.get("note") or ""
            backup_filename = db_manager.backup_database(note)
            if backup_filename:
                flash(f"Backup created: {backup_filename}")
            else:
                flash("Backup failed. Ensure the database has been pulled from the device.")
        return redirect(url_for("db_tab"))
    conn = None
    try:
        conn = sqlite3.connect(db_manager.METADATA_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, note, filename FROM backups ORDER BY timestamp DESC")
        backups = cursor.fetchall()
    except Exception as e:
        backups = []
    finally:
        if conn is not None:
            conn.close()
    # Get the last modification time of the sql.db file in currentdatabase
    if os.path.exists(db_manager.DB_PATH):
        last_pull = datetime.datetime.fromtimestamp(os.path.getmtime(db_manager.DB_PATH)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_pull = "Never"
    return render_template("db_tab.html", backups=backups, last_pull=last_pull)


@app.route("/sql", methods=["GET", "POST"])
def sql_tab():
    if request.method == "POST":
        action = request.form.get("action")
        pg_host = request.form.get("pg_host", "")
        pg_port = request.form.get("pg_port", "5432")
        pg_database = request.form.get("pg_database", "")
        pg_username = request.form.get("pg_username", "")
        pg_password = request.form.get("pg_password", "")
        db_manager.save_sql_config(pg_host, pg_port, pg_database, pg_username, pg_password)
        if action == "test":
            if db_manager.test_sql_connection():
                flash("Successfully connected to PostgreSQL.")
            else:
                flash("Failed to connect to PostgreSQL.")
        elif action == "sync":
            dest, result = adb_control.pull_database()
            if dest:
                db_manager.record_last_pull()
                flash("Database pulled successfully. " + db_manager.sync_to_postgresql())
            else:
                flash("Failed to pull database: " + (result or ""))
        elif action == "autosync":
            autosync_enabled = request.form.get("autosync") == "on"
            interval = int(request.form.get("interval", "5"))
            db_manager.set_autosync(autosync_enabled, interval)
            flash(f"Autosync {'enabled' if autosync_enabled else 'disabled'}, interval set to {interval} minutes.")
        return redirect(url_for("sql_tab"))
    sql_conf = db_manager.load_sql_config()
    autosync_enabled, autosync_interval = db_manager.load_autosync()
    return render_template("sql_tab.html", sql_conf=sql_conf, autosync_enabled=autosync_enabled, autosync_interval=autosync_interval)

# --------------------- Background autosync thread ---------------------
def autosync_thread():
    while True:
        autosync_enabled, interval = db_manager.load_autosync()
        if autosync_enabled:
            logger.debug("Autosync: Pulling updated DB and syncing to SQL...")
            adb_control.adb_connect()
            dest, _ = adb_control.pull_database()  # Pull latest DB
            if dest:
                db_manager.sync_to_postgresql()
                db_manager.record_last_pull()
        time.sleep(interval * 60)

@app.route("/delete_backup/<int:backup_id>", methods=["POST"])
def delete_backup(backup_id):
    try:
        conn = sqlite3.connect(db_manager.METADATA_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM backups WHERE id = ?", (backup_id,))
        row = cursor.fetchone()
        if row:
            backup_file = os.path.join(db_manager.MANUAL_BACKUP_DIR, row[0])
            if os.path.exists(backup_file):
                os.remove(backup_file)
            cursor.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
            conn.commit()
            flash("Backup deleted successfully.")
        else:
            flash("Backup not found.")
    except Exception as e:
        flash("Error deleting backup: " + str(e))
    finally:
        if conn:
            conn.close()
    return redirect(url_for("db_tab"))


threading.Thread(target=autosync_thread, daemon=True).start()

if __name__ == "__main__":
    logger.debug("Starting Flask server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
