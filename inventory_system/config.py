"""
config.py
---------
Central configuration file. Change DB_TYPE to switch database engines.

DB_TYPE = "sqlite"  -> No setup needed. Recommended for quickly running
                        and testing this project (default).
DB_TYPE = "mysql"   -> Requires a running MySQL server + mysql-connector-python
                        installed (pip install mysql-connector-python).
                        Fill in the MYSQL_* settings below.
"""

DB_TYPE = "mysql"   


MYSQL_DB_FILE = "inventory.db"

# --- MySQL settings (used when DB_TYPE = "mysql") ---
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "your_password"
MYSQL_DATABASE = "inventory_db"
MYSQL_PORT = 3306

# --- Business rule settings ---
LOW_STOCK_THRESHOLD = 10   # items with quantity < this are "low stock"
