"""
db.py
------
Database utility module for the Inventory Management System.

Supports TWO backends, controlled by config.py:
  1. "sqlite"  -> uses Python's built-in sqlite3 module (zero setup,
                  great for development / testing / running this
                  project immediately without installing a DB server)
  2. "mysql"   -> uses mysql-connector-python against a real MySQL
                  server (the "Recommended for Enterprise Projects"
                  option in the project brief)

Only this file needs to change if you switch database backends -
app.py talks only to the functions below, never to sqlite3 /
mysql-connector directly. That is the whole point of separating
db.py from app.py: swap the engine without touching business logic.
"""

import sqlite3
from datetime import datetime

import config

# mysql-connector is only imported if actually needed, so the project
# still runs with zero extra installs when DB_TYPE = "sqlite".
if config.DB_TYPE == "mysql":
    import mysql.connector
    from mysql.connector import Error as MySQLError


def create_connection():
    """
    Create and return a database connection based on config.DB_TYPE.
    Raises a RuntimeError with a clear message if the connection fails.
    """
    try:
        if config.DB_TYPE == "sqlite":
            conn = sqlite3.connect(config.SQLITE_DB_FILE)
            conn.execute("PRAGMA foreign_keys = ON")
            return conn

        elif config.DB_TYPE == "mysql":
            conn = mysql.connector.connect(
                host=config.MYSQL_HOST,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                database=config.MYSQL_DATABASE,
                port=config.MYSQL_PORT,
            )
            return conn

        else:
            raise RuntimeError(
                f"Unknown DB_TYPE '{config.DB_TYPE}' in config.py. "
                "Use 'sqlite' or 'mysql'."
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"SQLite connection error: {e}")
    except Exception as e:
        # Covers MySQLError too, without a hard import dependency
        # when running in sqlite-only mode.
        raise RuntimeError(f"Database connection error: {e}")


def placeholder():
    """
    SQLite uses '?' placeholders, MySQL uses '%s'.
    app.py calls this so the same query-building code works on
    either backend without an if/else at every call site.
    """
    return "?" if config.DB_TYPE == "sqlite" else "%s"


def init_db():
    """
    Create the 'products' table if it does not already exist.
    Schema matches the project spec:
        product_id  VARCHAR/INT   Primary key, unique
        name        VARCHAR       Product name
        category    VARCHAR       Category like electronics, food
        quantity    INT           Current stock quantity
        price       DECIMAL(10,2) Price per unit
        added_on    TIMESTAMP     Auto timestamp
    """
    conn = create_connection()
    try:
        cur = conn.cursor()
        if config.DB_TYPE == "sqlite":
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id  TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    category    TEXT,
                    quantity    INTEGER NOT NULL,
                    price       REAL NOT NULL,
                    added_on    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:  # mysql
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id  VARCHAR(50) PRIMARY KEY,
                    name        VARCHAR(255) NOT NULL,
                    category    VARCHAR(100),
                    quantity    INT NOT NULL,
                    price       DECIMAL(10,2) NOT NULL,
                    added_on    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()
    finally:
        conn.close()


def execute_query(query, params=None):
    """
    Run an INSERT / UPDATE / DELETE query.
    Returns the number of affected rows.
    """
    conn = create_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def fetch_all(query, params=None):
    """Run a SELECT query and return all matching rows as a list of tuples."""
    conn = create_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        return cur.fetchall()
    finally:
        conn.close()


def fetch_one(query, params=None):
    """Run a SELECT query and return the first matching row (or None)."""
    conn = create_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        return cur.fetchone()
    finally:
        conn.close()
