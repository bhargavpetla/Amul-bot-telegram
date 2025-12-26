import asyncio
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from database import Database
from scraper import AmulAPI
import config


class StockMonitor:
    """Background stock monitoring service"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.db = Database()
        self.running = False
        # Cache for tracking stock state per user
        self._stock_cache = {}  # {(user_id, sku): {"in_stock": bool, "quantity": int}}

    async def start(self):
        """Start the stock monitoring loop"""
        self.running = True
        print(f"Stock monitor started. Checking every {config.STOCK_CHECK_INTERVAL} minutes.")

        while self.running:
            try:
                await self.check_all_stocks()
            except Exception as e:
                print(f"Stock check error: {e}")

            # Wait for next interval
            await asyncio.sleep(config.STOCK_CHECK_INTERVAL * 60)

    def stop(self):
        """Stop the stock monitoring loop"""
        self.running = False
        print("Stock monitor stopped.")

    async def check_all_stocks(self):
        """Check stock for all active users"""
        print(f"[{datetime.now()}] Running stock check...")

        # Get all active users with pincode
        active_users = self.db.get_active_users()

        if not active_users:
            print("No active users to check.")
            return

        # Group users by substore to minimize API calls
        substore_users = {}
        for user in active_users:
            substore_id = user.get("substore_id")
            if substore_id:
                if substore_id not in substore_users:
                    substore_users[substore_id] = []
                substore_users[substore_id].append(user)

        # Check each substore
        for substore_id, users in substore_users.items():
            try:
                await self._check_substore_stock(substore_id, users)
                # Small delay between substores to avoid rate limiting
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error checking substore {substore_id}: {e}")

    async def _check_substore_stock(self, substore_id: str, users: list):
        """Check stock for a specific substore"""
        amul_api = AmulAPI()
        amul_api.init_session()

        # Use the first user's pincode to fetch products
        amul_api.pincode = users[0].get("pincode")

        # Get all products for this substore
        products = amul_api.get_protein_products(substore_id)

        if not products:
            print(f"No products fetched for substore {substore_id}")
            return

        # Update database cache with fresh stock data
        for p in products:
            self.db.upsert_product(
                p["id"],
                p["sku"],
                p["name"],
                p.get("price", 0),
                p.get("image_url", ""),
                p.get("category", ""),
                p.get("in_stock", False),
                p.get("quantity", 0)
            )

        # Create lookup by SKU
        stock_by_sku = {p["sku"]: p for p in products}

        # Check each user's subscriptions
        for user in users:
            subscriptions = self.db.get_user_subscriptions(user["user_id"])

            if not subscriptions:
                continue

            for sub in subscriptions:
                sku = sub["product_sku"]
                product = stock_by_sku.get(sku)

                if not product:
                    print(f"Product {sku} not found in latest stock for substore {substore_id}")
                    continue

                await self._process_stock_update(user, product)

    async def _process_stock_update(self, user: dict, product: dict):
        """Process stock update and send notification if needed"""
        user_id = user["user_id"]
        sku = product["sku"]
        cache_key = (user_id, sku)

        current_in_stock = product["in_stock"]
        current_quantity = product["quantity"]

        # First time seeing this product for this user - initialize cache
        if cache_key not in self._stock_cache:
            self._stock_cache[cache_key] = {
                "in_stock": current_in_stock,
                "quantity": current_quantity,
                "initialized": True
            }

            # DON'T send alert on first check - user just subscribed
            # They already know the current stock status from the UI
            # We only alert on CHANGES from this baseline
            return

        # Get previous state from cache
        prev_state = self._stock_cache[cache_key]
        prev_in_stock = prev_state["in_stock"]
        prev_quantity = prev_state["quantity"]

        # Update cache
        self._stock_cache[cache_key] = {
            "in_stock": current_in_stock,
            "quantity": current_quantity,
            "initialized": True
        }

        # Determine if we should notify (ONLY on actual state changes)
        should_notify = False
        notification_type = None
        quantity_change = current_quantity - prev_quantity

        if current_in_stock and not prev_in_stock:
            # Product just came back in stock (was out, now in)
            should_notify = True
            notification_type = "back_in_stock"
        elif current_in_stock and prev_in_stock and current_quantity != prev_quantity:
            # Stock quantity changed (still in stock)
            # NOTIFY ON ALL CHANGES - user wants real-time updates!
            if quantity_change > 0:
                should_notify = True
                notification_type = "stock_increased"
            elif quantity_change < 0 and current_quantity <= 10:
                # Stock decreased and running low
                should_notify = True
                notification_type = "low_stock"
            elif quantity_change < 0:
                # Stock decreased but still plenty available
                should_notify = True
                notification_type = "stock_decreased"
        elif not current_in_stock and prev_in_stock:
            # Product just went out of stock (was in, now out)
            should_notify = True
            notification_type = "sold_out"

        if should_notify:
            await self._send_notification(user, product, notification_type, quantity_change)

    async def _send_notification(self, user: dict, product: dict, notification_type: str, quantity_change: int = 0):
        """Send stock notification to user"""
        user_id = user["user_id"]

        if notification_type == "back_in_stock":
            message = (
                f"🟢 *STOCK ALERT!*\n\n"
                f"*{product['name']}*\n"
                f"is now available!\n\n"
                f"📍 Pincode: {user['pincode']}\n"
                f"📦 Quantity: {product['quantity']} units\n"
                f"💰 Price: ₹{product['price']}\n\n"
                f"🛒 [Order Now]({product['product_url']})\n\n"
                f"_Hurry! Limited stock available._"
            )
        elif notification_type == "stock_increased":
            change_text = f"+{quantity_change}" if quantity_change > 0 else str(quantity_change)
            message = (
                f"📦 *STOCK UPDATE*\n\n"
                f"*{product['name']}*\n"
                f"Stock increased! ({change_text})\n\n"
                f"📍 Pincode: {user['pincode']}\n"
                f"📦 Quantity: {product['quantity']} units\n"
                f"💰 Price: ₹{product['price']}\n\n"
                f"🛒 [Order Now]({product['product_url']})"
            )
        elif notification_type == "stock_decreased":
            message = (
                f"📉 *STOCK DECREASED*\n\n"
                f"*{product['name']}*\n"
                f"Stock reduced ({quantity_change})\n\n"
                f"📍 Pincode: {user['pincode']}\n"
                f"📦 Remaining: {product['quantity']} units\n"
                f"💰 Price: ₹{product['price']}\n\n"
                f"🛒 [Order Now]({product['product_url']})"
            )
        elif notification_type == "low_stock":
            message = (
                f"⚠️ *LOW STOCK WARNING*\n\n"
                f"*{product['name']}*\n"
                f"Only {product['quantity']} left!\n\n"
                f"📍 Pincode: {user['pincode']}\n"
                f"💰 Price: ₹{product['price']}\n\n"
                f"🛒 [Order Now]({product['product_url']})\n\n"
                f"_Order soon before it's gone!_"
            )
        elif notification_type == "sold_out":
            message = (
                f"🔴 *SOLD OUT*\n\n"
                f"*{product['name']}*\n"
                f"is now out of stock.\n\n"
                f"📍 Pincode: {user['pincode']}\n\n"
                f"_I'll notify you when it's back!_"
            )
        else:
            return

        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

            # Record the alert
            self.db.add_stock_alert(user_id, product["sku"], product["quantity"])
            print(f"Notification sent to {user_id} for {product['sku']} ({notification_type})")

        except TelegramError as e:
            print(f"Failed to send notification to {user_id}: {e}")
            # If user blocked the bot, deactivate them
            if "blocked" in str(e).lower():
                self.db.set_user_active(user_id, False)
