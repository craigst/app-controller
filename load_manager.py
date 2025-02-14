import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os

from db_manager import load_sql_config  # or wherever load_sql_config() is defined

logger = logging.getLogger(__name__)

def connect_db():
    sql_conf = load_sql_config()
    host = sql_conf.get("PG_HOST", "")
    port = sql_conf.get("PG_PORT", "5432")
    dbname = sql_conf.get("PG_DATABASE", "")
    user = sql_conf.get("PG_USERNAME", "")
    password = sql_conf.get("PG_PASSWORD", "")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            cursor_factory=RealDictCursor
        )
        logger.info("Connected to PostgreSQL for loads.")
        return conn
    except Exception as e:
        logger.exception("Failed to connect to PostgreSQL for loads: %s", e)
        return None

def get_loads_for_week(week_ending):
    """
    Return collection loads (jobs with dwjtype='C') for the 7-day period ending on 'week_ending' (YYYY-MM-DD).
    Also attaches .destination = name from the matching 'D' row (same dwjload) if found.
    """
    try:
        end_date = datetime.strptime(week_ending, "%Y-%m-%d")
        start_date = end_date - timedelta(days=6)
        conn = connect_db()
        if not conn:
            return []
        with conn.cursor() as cur:
            # 1) Fetch collection loads:
            query_c = """
                SELECT *
                FROM jobs
                WHERE dwjtype = 'C'
                  AND dwjdate BETWEEN %s AND %s
                ORDER BY dwjdate DESC
            """
            start_str = start_date.strftime("%Y%m%d")  # e.g. '20250101'
            end_str = end_date.strftime("%Y%m%d")      # e.g. '20250107'
            cur.execute(query_c, (start_str, end_str))
            loads = cur.fetchall()

            # 2) For each collection load, look up the corresponding 'D' row
            #    that shares the same dwjload (i.e. same load number).
            for ld in loads:
                load_id = ld.get("dwjload")
                if not load_id:
                    ld["destination"] = None
                    continue

                # Query for the 'D' row (delivery job) with the same dwjload
                query_d = """
                    SELECT dwjname
                    FROM jobs
                    WHERE dwjtype = 'D'
                      AND dwjload = %s
                    LIMIT 1
                """
                cur.execute(query_d, (load_id,))
                dest_row = cur.fetchone()
                if dest_row:
                    ld["destination"] = dest_row.get("dwjname")
                else:
                    ld["destination"] = None
        conn.close()
        return loads
    except Exception as e:
        logger.exception("Error fetching loads for week ending %s: %s", week_ending, e)
        return []
