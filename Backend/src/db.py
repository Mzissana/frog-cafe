import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # psycopg2 может принимать URL напрямую начиная с версии 2.7
    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)

    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET search_path TO frog_cafe")

    return conn

