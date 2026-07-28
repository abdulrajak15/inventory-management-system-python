"""
app.py
------
Inventory Management System - main application.

A database-driven console app to manage inventory: add / update /
delete / view products, generate reports (low-stock + summary),
and bulk-update products from a CSV file.

Run with:  python app.py
"""

import csv
import os
import sys
from datetime import datetime

import config
import db


# --------------------------------------------------------------------------
# Custom exceptions - make validation failures easy to catch and report
# cleanly instead of leaking raw tracebacks to the user.
# --------------------------------------------------------------------------
class ValidationError(Exception):
    """Raised when user input fails a business-rule validation."""
    pass


# --------------------------------------------------------------------------
# InventoryManager - all business logic lives here (OOP requirement).
# app.py's menu loop only calls methods on this class; db.py only
# knows how to talk to the database, never about business rules.
# --------------------------------------------------------------------------
class InventoryManager:

    def __init__(self):
        db.init_db()

    # ---------------------- Validation helpers ----------------------

    @staticmethod
    def _validate_quantity(value):
        try:
            qty = int(value)
        except (TypeError, ValueError):
            raise ValidationError("Quantity must be a whole number.")
        if qty < 0:
            raise ValidationError("Quantity cannot be negative.")
        return qty

    @staticmethod
    def _validate_price(value):
        try:
            price = float(value)
        except (TypeError, ValueError):
            raise ValidationError("Price must be a valid number.")
        if price <= 0:
            raise ValidationError("Price must be greater than 0.")
        return round(price, 2)

    @staticmethod
    def _validate_text(value, field_name):
        if value is None or not str(value).strip():
            raise ValidationError(f"{field_name} cannot be empty.")
        return str(value).strip()

    def _product_exists(self, product_id):
        p = db.placeholder()
        row = db.fetch_one(
            f"SELECT product_id FROM products WHERE product_id = {p}",
            (product_id,),
        )
        return row is not None

    # ---------------------- CRUD: Add ----------------------

    def add_product(self, product_id, name, category, quantity, price):
        """
        Add a new product.
        Validations: product_id unique, quantity/price valid numbers.
        """
        product_id = self._validate_text(product_id, "Product ID")
        name = self._validate_text(name, "Name")
        category = self._validate_text(category, "Category")
        quantity = self._validate_quantity(quantity)
        price = self._validate_price(price)

        if self._product_exists(product_id):
            raise ValidationError(f"Product ID '{product_id}' already exists.")

        p = db.placeholder()
        db.execute_query(
            f"""INSERT INTO products (product_id, name, category, quantity, price)
                VALUES ({p}, {p}, {p}, {p}, {p})""",
            (product_id, name, category, quantity, price),
        )
        return True

    # ---------------------- CRUD: Update ----------------------

    def update_product(self, product_id, name=None, category=None,
                        quantity=None, price=None):
        """
        Update only the fields that are provided (not None/empty).
        Returns the updated row.
        """
        if not self._product_exists(product_id):
            raise ValidationError(f"Product ID '{product_id}' not found.")

        updates = {}
        if name not in (None, ""):
            updates["name"] = self._validate_text(name, "Name")
        if category not in (None, ""):
            updates["category"] = self._validate_text(category, "Category")
        if quantity not in (None, ""):
            updates["quantity"] = self._validate_quantity(quantity)
        if price not in (None, ""):
            updates["price"] = self._validate_price(price)

        if not updates:
            raise ValidationError("No fields provided to update.")

        p = db.placeholder()
        set_clause = ", ".join(f"{col} = {p}" for col in updates)
        params = list(updates.values()) + [product_id]
        db.execute_query(
            f"UPDATE products SET {set_clause} WHERE product_id = {p}",
            params,
        )
        return self.get_product(product_id)

    # ---------------------- CRUD: Delete ----------------------

    def delete_product(self, product_id):
        if not self._product_exists(product_id):
            raise ValidationError(f"Product ID '{product_id}' not found.")
        p = db.placeholder()
        db.execute_query(
            f"DELETE FROM products WHERE product_id = {p}", (product_id,)
        )
        return True

    # ---------------------- CRUD: View ----------------------

    def get_product(self, product_id):
        p = db.placeholder()
        return db.fetch_one(
            f"SELECT product_id, name, category, quantity, price, added_on "
            f"FROM products WHERE product_id = {p}",
            (product_id,),
        )

    def view_inventory(self):
        return db.fetch_all(
            "SELECT product_id, name, category, quantity, price, added_on "
            "FROM products ORDER BY product_id"
        )

    # ---------------------- Reports ----------------------

    def low_stock_report(self, threshold=None):
        threshold = threshold if threshold is not None else config.LOW_STOCK_THRESHOLD
        p = db.placeholder()
        return db.fetch_all(
            f"SELECT product_id, name, category, quantity, price "
            f"FROM products WHERE quantity < {p} ORDER BY quantity ASC",
            (threshold,),
        )

    def inventory_summary(self):
        rows = self.view_inventory()
        total_products = len(rows)
        total_stock = sum(row[3] for row in rows)
        total_value = sum(row[3] * row[4] for row in rows)
        return {
            "total_products": total_products,
            "total_stock": total_stock,
            "total_value": round(total_value, 2),
        }

    def save_reports_to_files(self):
        """Writes low_stock.txt and summary.txt into reports/ (per spec)."""
        os.makedirs("reports", exist_ok=True)

        low_stock = self.low_stock_report()
        with open(os.path.join("reports", "low_stock.txt"), "w") as f:
            f.write(f"Low Stock Report (threshold < {config.LOW_STOCK_THRESHOLD})\n")
            f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n")
            f.write("-" * 60 + "\n")
            if not low_stock:
                f.write("No low-stock items.\n")
            for pid, name, category, qty, price in low_stock:
                f.write(f"{pid} | {name} | {category} | qty={qty} | price={price}\n")

        summary = self.inventory_summary()
        with open(os.path.join("reports", "summary.txt"), "w") as f:
            f.write("Inventory Summary\n")
            f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n")
            f.write("-" * 60 + "\n")
            f.write(f"Total number of products : {summary['total_products']}\n")
            f.write(f"Total stock count        : {summary['total_stock']}\n")
            f.write(f"Total inventory value    : {summary['total_value']}\n")

    # ---------------------- Bulk Update (CSV) ----------------------

    def bulk_update_from_csv(self, filepath):
        """
        Reads a CSV with columns: product_id,name,category,quantity,price
        For each row: INSERT if product_id is new, UPDATE if it exists.
        Returns a summary dict of results. Bad rows are skipped and
        reported, not allowed to crash the whole batch.
        """
        if not os.path.exists(filepath):
            raise ValidationError(f"CSV file not found: {filepath}")

        inserted, updated, failed = 0, 0, []

        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            required_cols = {"product_id", "name", "category", "quantity", "price"}
            if not required_cols.issubset(set(reader.fieldnames or [])):
                raise ValidationError(
                    f"CSV must contain columns: {', '.join(sorted(required_cols))}"
                )

            for line_num, row in enumerate(reader, start=2):  # header is line 1
                try:
                    pid = row["product_id"]
                    if self._product_exists(pid):
                        self.update_product(
                            pid, row["name"], row["category"],
                            row["quantity"], row["price"],
                        )
                        updated += 1
                    else:
                        self.add_product(
                            pid, row["name"], row["category"],
                            row["quantity"], row["price"],
                        )
                        inserted += 1
                except ValidationError as e:
                    failed.append((line_num, row.get("product_id", "?"), str(e)))

        return {"inserted": inserted, "updated": updated, "failed": failed}


# --------------------------------------------------------------------------
# Console UI helpers
# --------------------------------------------------------------------------

def print_table(rows, headers):
    if not rows:
        print("  (no records found)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    line = "  " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  " + "-" * (len(line) - 2))
    for row in rows:
        print("  " + " | ".join(str(val).ljust(widths[i]) for i, val in enumerate(row)))


def prompt(text, allow_blank=False):
    while True:
        val = input(text).strip()
        if val or allow_blank:
            return val
        print("  This field is required.")


def menu_add(manager):
    print("\n--- Add Product ---")
    try:
        pid = prompt("Product ID: ")
        name = prompt("Name: ")
        category = prompt("Category: ")
        qty = prompt("Quantity: ")
        price = prompt("Price: ")
        manager.add_product(pid, name, category, qty, price)
        print("✔ Product added successfully.")
    except ValidationError as e:
        print(f"✘ Error: {e}")


def menu_update(manager):
    print("\n--- Update Product ---")
    pid = prompt("Product ID to update: ")
    existing = manager.get_product(pid)
    if not existing:
        print(f"✘ Product ID '{pid}' not found.")
        return
    print("  Current values:", existing)
    print("  Leave a field blank to keep it unchanged.")
    try:
        name = prompt("New Name: ", allow_blank=True)
        category = prompt("New Category: ", allow_blank=True)
        qty = prompt("New Quantity: ", allow_blank=True)
        price = prompt("New Price: ", allow_blank=True)
        updated = manager.update_product(pid, name, category, qty, price)
        print("✔ Product updated:", updated)
    except ValidationError as e:
        print(f"✘ Error: {e}")


def menu_delete(manager):
    print("\n--- Delete Product ---")
    pid = prompt("Product ID to delete: ")
    existing = manager.get_product(pid)
    if not existing:
        print(f"✘ Product ID '{pid}' not found.")
        return
    print("  Product:", existing)
    confirm = prompt("Type 'yes' to confirm deletion: ")
    if confirm.lower() == "yes":
        manager.delete_product(pid)
        print("✔ Product deleted.")
    else:
        print("  Deletion cancelled.")


def menu_view(manager):
    print("\n--- Inventory ---")
    rows = manager.view_inventory()
    print_table(rows, ["ID", "Name", "Category", "Qty", "Price", "Added On"])


def menu_reports(manager):
    print("\n--- Reports ---")
    low_stock = manager.low_stock_report()
    print(f"\nLow Stock Report (qty < {config.LOW_STOCK_THRESHOLD}):")
    print_table(low_stock, ["ID", "Name", "Category", "Qty", "Price"])

    summary = manager.inventory_summary()
    print("\nInventory Summary:")
    print(f"  Total number of products : {summary['total_products']}")
    print(f"  Total stock count        : {summary['total_stock']}")
    print(f"  Total inventory value    : {summary['total_value']}")

    manager.save_reports_to_files()
    print("\n  (Saved to reports/low_stock.txt and reports/summary.txt)")


def menu_bulk_update(manager):
    print("\n--- Bulk Update ---")
    filepath = prompt("CSV file path (e.g. bulk_update.csv): ")
    try:
        result = manager.bulk_update_from_csv(filepath)
        print(f"✔ Inserted: {result['inserted']}, Updated: {result['updated']}")
        if result["failed"]:
            print(f"✘ {len(result['failed'])} row(s) failed:")
            for line_num, pid, err in result["failed"]:
                print(f"    line {line_num} (product_id={pid}): {err}")
    except ValidationError as e:
        print(f"✘ Error: {e}")


MENU_TEXT = """
========================================
   INVENTORY MANAGEMENT SYSTEM
========================================
1. Add Product
2. Update Product
3. Delete Product
4. View Inventory
5. Reports
6. Bulk Update
7. Exit
========================================
"""


def main():
    manager = InventoryManager()
    actions = {
        "1": lambda: menu_add(manager),
        "2": lambda: menu_update(manager),
        "3": lambda: menu_delete(manager),
        "4": lambda: menu_view(manager),
        "5": lambda: menu_reports(manager),
        "6": lambda: menu_bulk_update(manager),
    }

    while True:
        print(MENU_TEXT)
        choice = input("Enter your choice (1-7): ").strip()

        if choice == "7":
            print("Goodbye!")
            break

        action = actions.get(choice)
        if action is None:
            print("✘ Invalid choice. Please select 1-7.")
            continue

        try:
            action()
        except RuntimeError as e:
            # Database connection / query errors surface here
            print(f"✘ Database error: {e}")
        except Exception as e:
            # Catch-all so one bad interaction never crashes the app
            print(f"✘ Unexpected error: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
        sys.exit(0)
