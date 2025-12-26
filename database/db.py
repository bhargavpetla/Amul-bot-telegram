import sqlite3
from typing import Optional
from contextlib import contextmanager
import config


class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    pincode TEXT,
                    substore_id TEXT,
                    substore_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Products table (cache of available products)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id TEXT PRIMARY KEY,
                    sku TEXT UNIQUE,
                    name TEXT,
                    price REAL,
                    image_url TEXT,
                    category TEXT,
                    in_stock INTEGER DEFAULT 0,
                    quantity INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User subscriptions (which products user wants to track)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_sku TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, product_sku)
                )
            """)

            # Stock alerts (to track what was notified)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_sku TEXT,
                    quantity INTEGER,
                    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            conn.commit()

    # User operations
    def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Add a new user or update existing"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, username, first_name))
            conn.commit()
            return True

    def get_user(self, user_id: int) -> Optional[dict]:
        """Get user by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Retrieve user details by user ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_user_pincode(self, user_id: int, pincode: str, substore_id: str, substore_name: str) -> bool:
        """Update user's pincode and substore"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET pincode = ?, substore_id = ?, substore_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (pincode, substore_id, substore_name, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def set_user_active(self, user_id: int, is_active: bool) -> bool:
        """Activate or deactivate user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (1 if is_active else 0, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_active_users(self) -> list:
        """Get all active users with pincode set"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users
                WHERE is_active = 1 AND pincode IS NOT NULL
            """)
            return [dict(row) for row in cursor.fetchall()]

    # Product operations
    def upsert_product(self, product_id: str, sku: str, name: str, price: float,
                       image_url: str = None, category: str = None, in_stock: bool = False, quantity: int = 0) -> bool:
        """Insert or update a product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products (product_id, sku, name, price, image_url, category, in_stock, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    name = excluded.name,
                    price = excluded.price,
                    image_url = excluded.image_url,
                    category = excluded.category,
                    in_stock = excluded.in_stock,
                    quantity = excluded.quantity,
                    updated_at = CURRENT_TIMESTAMP
            """, (product_id, sku, name, price, image_url, category, 1 if in_stock else 0, quantity))
            conn.commit()
            return True

    def get_all_products(self) -> list:
        """Get all cached products"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def get_product_by_sku(self, sku: str) -> Optional[dict]:
        """Get product by SKU"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # Subscription operations
    def add_subscription(self, user_id: int, product_sku: str) -> bool:
        """Subscribe user to a product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO subscriptions (user_id, product_sku, is_active)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, product_sku) DO UPDATE SET
                    is_active = 1
            """, (user_id, product_sku))
            conn.commit()
            return True

    def remove_subscription(self, user_id: int, product_sku: str) -> bool:
        """Unsubscribe user from a product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE subscriptions SET is_active = 0
                WHERE user_id = ? AND product_sku = ?
            """, (user_id, product_sku))
            conn.commit()
            return cursor.rowcount > 0

    def get_user_subscriptions(self, user_id: int) -> list:
        """Get all active subscriptions for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, p.name, p.price, p.image_url
                FROM subscriptions s
                LEFT JOIN products p ON s.product_sku = p.sku
                WHERE s.user_id = ? AND s.is_active = 1
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_subscribers_for_product(self, product_sku: str) -> list:
        """Get all active users subscribed to a product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.* FROM users u
                JOIN subscriptions s ON u.user_id = s.user_id
                WHERE s.product_sku = ? AND s.is_active = 1 AND u.is_active = 1
            """, (product_sku,))
            return [dict(row) for row in cursor.fetchall()]

    def clear_user_subscriptions(self, user_id: int) -> bool:
        """Remove all subscriptions for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE subscriptions SET is_active = 0
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            return True

    # Stock alert operations
    def add_stock_alert(self, user_id: int, product_sku: str, quantity: int) -> bool:
        """Record a stock alert sent"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO stock_alerts (user_id, product_sku, quantity)
                VALUES (?, ?, ?)
            """, (user_id, product_sku, quantity))
            conn.commit()
            return True

    def get_last_alert(self, user_id: int, product_sku: str) -> Optional[dict]:
        """Get last alert for user and product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM stock_alerts
                WHERE user_id = ? AND product_sku = ?
                ORDER BY notified_at DESC LIMIT 1
            """, (user_id, product_sku))
            row = cursor.fetchone()
            return dict(row) if row else None
