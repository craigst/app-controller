import os
import sqlite3
import configparser
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_batch

logger = logging.getLogger(__name__)

# Directories and file paths
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, "data")
CURRENT_DB_DIR = os.path.join(DATA_DIR, "currentdatabase")
MANUAL_BACKUP_DIR = os.path.join(DATA_DIR, "manual_backup")
CONFIG_DIR = os.path.join(DATA_DIR, "config")
for d in [CURRENT_DB_DIR, MANUAL_BACKUP_DIR, CONFIG_DIR]:
    os.makedirs(d, exist_ok=True)

# Now use "sql.db" as the current database file.
DB_PATH = os.path.join(CURRENT_DB_DIR, "sql.db")
METADATA_DB = os.path.join(CONFIG_DIR, "backup_metadata.db")
SQL_CONFIG_FILE = os.path.join(CONFIG_DIR, "sql_config.ini")

def init_backup_metadata_db():
    conn = sqlite3.connect(METADATA_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp TEXT,
            note TEXT
        );
    """)
    conn.commit()
    conn.close()
    logger.debug("Initialized backup metadata DB.")

init_backup_metadata_db()

def backup_database(note=""):
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found at {DB_PATH}. Please pull the DB from device first.")
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.db"
    backup_path = os.path.join(MANUAL_BACKUP_DIR, backup_filename)
    try:
        with open(DB_PATH, "rb") as src, open(backup_path, "wb") as dst:
            dst.write(src.read())
        conn = sqlite3.connect(METADATA_DB)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO backups (filename, timestamp, note) VALUES (?, ?, ?)",
                       (backup_filename, timestamp, note))
        conn.commit()
        conn.close()
        logger.debug("Backup created successfully.")
        return backup_filename
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None

def record_last_pull():
    last_pull_file = os.path.join(CONFIG_DIR, "last_pull.txt")
    with open(last_pull_file, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def load_last_pull():
    last_pull_file = os.path.join(CONFIG_DIR, "last_pull.txt")
    if os.path.exists(last_pull_file):
        with open(last_pull_file, "r") as f:
            return f.read().strip()
    return "Never"

def load_sql_config():
    config = configparser.ConfigParser()
    if os.path.exists(SQL_CONFIG_FILE):
        config.read(SQL_CONFIG_FILE)
    else:
        config['SQL'] = {
            'PG_HOST': '',
            'PG_PORT': '5432',
            'PG_DATABASE': '',
            'PG_USERNAME': '',
            'PG_PASSWORD': ''
        }
        with open(SQL_CONFIG_FILE, 'w') as f:
            config.write(f)
    return config['SQL']

def save_sql_config(pg_host, pg_port, pg_database, pg_username, pg_password):
    config = configparser.ConfigParser()
    config['SQL'] = {
        'PG_HOST': pg_host,
        'PG_PORT': pg_port,
        'PG_DATABASE': pg_database,
        'PG_USERNAME': pg_username,
        'PG_PASSWORD': pg_password
    }
    with open(SQL_CONFIG_FILE, 'w') as f:
        config.write(f)

class DatabaseManagerSync:
    def __init__(self, host, port, dbname, user, password):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.conn = None
    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host, port=self.port, database=self.dbname,
                user=self.user, password=self.password
            )
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            return False
    def close(self):
        if self.conn:
            self.conn.close()

def sync_to_postgresql():
    sql_conf = load_sql_config()
    host = sql_conf.get('PG_HOST')
    port = sql_conf.get('PG_PORT', '5432')
    dbname = sql_conf.get('PG_DATABASE')
    user = sql_conf.get('PG_USERNAME')
    password = sql_conf.get('PG_PASSWORD')
    if not all([host, dbname, user, password]):
        return "SQL configuration incomplete."
    db_sync = DatabaseManagerSync(host, port, dbname, user, password)
    if not db_sync.connect():
        return "Failed to connect to PostgreSQL."
    try:
        cursor = db_sync.conn.cursor()
        with sqlite3.connect(DB_PATH) as sqlite_conn:
            sqlite_cursor = sqlite_conn.cursor()
            # Sync DWJJOB table as 'jobs'
            sqlite_cursor.execute("PRAGMA table_info(DWJJOB)")
            job_columns = [col[1] for col in sqlite_cursor.fetchall()]
            if not job_columns:
                return "No DWJJOB table found in SQLite DB."
            job_columns_str = ", ".join(job_columns)
            placeholders = ", ".join(["%s"] * len(job_columns))
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS jobs (
                    {', '.join([f'{col} TEXT' for col in job_columns])},
                    PRIMARY KEY (dwjkey)
                );
            """)
            sqlite_cursor.execute(f"SELECT {job_columns_str} FROM DWJJOB")
            jobs = sqlite_cursor.fetchall()
            if jobs:
                execute_batch(
                    cursor,
                    f"""
                    INSERT INTO jobs ({job_columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT (dwjkey) DO UPDATE SET
                    {', '.join([f'{col} = EXCLUDED.{col}' for col in job_columns if col != 'dwjkey'])};
                    """,
                    jobs
                )
            # Sync DWVVEH table as 'vehicles'
            sqlite_cursor.execute("PRAGMA table_info(DWVVEH)")
            vehicle_columns = [col[1] for col in sqlite_cursor.fetchall()]
            if not vehicle_columns:
                return "No DWVVEH table found in SQLite DB."
            vehicle_columns_str = ", ".join(vehicle_columns)
            placeholders = ", ".join(["%s"] * len(vehicle_columns))
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS vehicles (
                    {', '.join([f'{col} TEXT' for col in vehicle_columns])},
                    PRIMARY KEY (dwvkey)
                );
            """)
            sqlite_cursor.execute(f"SELECT {vehicle_columns_str} FROM DWVVEH")
            vehicles = sqlite_cursor.fetchall()
            if vehicles:
                execute_batch(
                    cursor,
                    f"""
                    INSERT INTO vehicles ({vehicle_columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT (dwvkey) DO UPDATE SET
                    {', '.join([f'{col} = EXCLUDED.{col}' for col in vehicle_columns if col != 'dwvkey'])};
                    """,
                    vehicles
                )
        db_sync.conn.commit()
        return "Data synced to PostgreSQL successfully."
    except Exception as e:
        return f"Sync failed: {e}"
    finally:
        db_sync.close()

def test_sql_connection():
    sql_conf = load_sql_config()
    host = sql_conf.get('PG_HOST')
    port = sql_conf.get('PG_PORT', '5432')
    dbname = sql_conf.get('PG_DATABASE')
    user = sql_conf.get('PG_USERNAME')
    password = sql_conf.get('PG_PASSWORD')
    if not all([host, dbname, user, password]):
        return False
    db_sync = DatabaseManagerSync(host, port, dbname, user, password)
    result = db_sync.connect()
    if result:
        db_sync.close()
    return result

def set_autosync(enabled, interval_minutes):
    config_file = os.path.join(CONFIG_DIR, "autosync.ini")
    config = configparser.ConfigParser()
    config['AUTOSYNC'] = {'enabled': str(enabled), 'interval': str(interval_minutes)}
    with open(config_file, 'w') as f:
        config.write(f)

def load_autosync():
    config_file = os.path.join(CONFIG_DIR, "autosync.ini")
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
        enabled = config['AUTOSYNC'].getboolean('enabled', fallback=False)
        interval = config['AUTOSYNC'].getint('interval', fallback=5)
    else:
        enabled = False
        interval = 5
    return enabled, interval
