from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from database import Database
from scraper import AmulAPI
import logging

logger = logging.getLogger(__name__)

# Initialize database and API
db = Database()
amul_api = AmulAPI()

# Global state tracking (more reliable than context.user_data)
USER_STATES = {}


def get_main_menu_keyboard(has_pincode=False):
    """Get modern main menu keyboard"""
    if has_pincode:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🛒 Products", callback_data="cb_products"),
                InlineKeyboardButton("📊 Status", callback_data="cb_mystatus")
            ],
            [
                InlineKeyboardButton("📦 Check Stock", callback_data="cb_instock"),
                InlineKeyboardButton("📍 Change Pin", callback_data="cb_setpincode")
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="cb_help"),
                InlineKeyboardButton("🔕 Stop Alerts", callback_data="cb_stop")
            ]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📍 Set Pincode", callback_data="cb_setpincode")],
            [InlineKeyboardButton("❓ Help", callback_data="cb_help")]
        ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    # Clear any pending state
    user_id = update.effective_user.id
    USER_STATES.pop(user_id, None)

    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)

    existing_user = db.get_user(user.id)
    has_pincode = existing_user and existing_user.get("pincode")

    welcome_message = f"""
╔══════════════════════════════════╗
     🥛 *AMUL PROTEIN ALERTS* 🥛
╚══════════════════════════════════╝

Hey *{user.first_name}*! 👋

I'll notify you *instantly* when Amul protein products are back in stock at your location.

━━━━━━━━━━━━━━━━━━━━━━
📌 *Quick Setup:*
━━━━━━━━━━━━━━━━━━━━━━
1️⃣  Set your delivery pincode
2️⃣  Select products to track
3️⃣  Get instant alerts! 🔔

"""
    if has_pincode:
        welcome_message += f"✅ Your pincode: *{existing_user['pincode']}*\n\n"
        welcome_message += "👇 *Choose an option below:*"
    else:
        welcome_message += "👇 *Let's start by setting your pincode:*"

    reply_markup = get_main_menu_keyboard(has_pincode)
    await update.message.reply_text(welcome_message, parse_mode="Markdown", reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    USER_STATES.pop(update.effective_user.id, None)

    user = db.get_user(update.effective_user.id)
    has_pincode = user and user.get("pincode")

    help_text = """
╔══════════════════════════════════╗
          ❓ *HELP CENTER*
╚══════════════════════════════════╝

*🔹 Commands:*
┌─────────────────────────────
│ /start - Main menu
│ /setpincode - Set location
│ /products - Track products
│ /instock - Check availability
│ /mystatus - Your subscriptions
│ /stop - Pause notifications
│ /help - This help menu
└─────────────────────────────

*🔹 How It Works:*
━━━━━━━━━━━━━━━━━━━━━━
1️⃣ Set your pincode
2️⃣ Choose products to track
3️⃣ I check stock every 30 sec
4️⃣ Get notified when available!

*🔹 Tips:*
• Tap buttons for quick actions
• You can track multiple products
• Alerts stop when items sell out

━━━━━━━━━━━━━━━━━━━━━━
💡 *Need more help?* Just send any message!
"""
    reply_markup = get_main_menu_keyboard(has_pincode)
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)


async def set_pincode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start pincode setting from command"""
    user = db.get_user(update.effective_user.id)
    current_pincode = user.get("pincode") if user else None

    if current_pincode:
        message = f"""
📍 *Change Pincode*

Your current pincode: *{current_pincode}*

━━━━━━━━━━━━━━━━━━━━━━
Enter new 6-digit pincode:
"""
    else:
        message = """
📍 *Set Your Pincode*

━━━━━━━━━━━━━━━━━━━━━━
Enter your 6-digit delivery pincode:

_Example: 400001_
"""

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cb_cancel")]]
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # Set state to wait for pincode
    user_id = update.effective_user.id
    USER_STATES[user_id] = "awaiting_pincode"
    logger.info(f"Set USER_STATES[{user_id}] = awaiting_pincode")


async def set_pincode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start pincode setting from callback button"""
    query = update.callback_query
    await query.answer()

    user = db.get_user(query.from_user.id)
    current_pincode = user.get("pincode") if user else None

    if current_pincode:
        message = f"""
📍 *Change Pincode*

Your current pincode: *{current_pincode}*

━━━━━━━━━━━━━━━━━━━━━━
*Type your new 6-digit pincode:*
"""
    else:
        message = """
📍 *Set Your Pincode*

━━━━━━━━━━━━━━━━━━━━━━
*Type your 6-digit delivery pincode:*

_Example: 400063_
"""

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cb_cancel")]]

    try:
        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except:
        await query.message.reply_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # Set state to wait for pincode using global dict
    user_id = query.from_user.id
    USER_STATES[user_id] = "awaiting_pincode"
    logger.info(f"Set USER_STATES[{user_id}] = awaiting_pincode (callback)")


async def process_pincode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the pincode entered by user"""
    pincode = update.message.text.strip()
    user_id = update.effective_user.id

    logger.info(f"Processing pincode: {pincode} for user {user_id}")

    # Validate pincode format
    if not pincode.isdigit() or len(pincode) != 6:
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cb_cancel")]]
        await update.message.reply_text(
            "⚠️ *Invalid pincode!*\n\nPlease enter a valid 6-digit pincode:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return  # Keep awaiting_pincode = True

    # Show loading message
    loading_msg = await update.message.reply_text(
        "🔍 *Checking pincode...*\n\n⏳ _Please wait, this may take 10-15 seconds..._",
        parse_mode="Markdown"
    )

    # Clear the awaiting state
    USER_STATES.pop(user_id, None)

    # Search pincode
    logger.info(f"Searching pincode {pincode}...")
    pincode_info = amul_api.search_pincode(pincode)
    logger.info(f"Pincode search result: {pincode_info}")

    if not pincode_info:
        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="cb_setpincode")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
        ]
        await loading_msg.edit_text(
            f"❌ *Pincode Not Available*\n\n"
            f"Sorry, Amul doesn't deliver to *{pincode}* yet.\n\n"
            f"Try a different pincode.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Save to database
    db.update_user_pincode(
        user_id,
        pincode_info["pincode"],
        pincode_info["substore_id"],
        pincode_info["substore_name"]
    )

    # Success message with next step buttons
    keyboard = [
        [InlineKeyboardButton("🛒 Select Products Now", callback_data="cb_products")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
    ]

    city = pincode_info.get('city', '')
    state = pincode_info.get('state', '')
    location = f"{city}, {state}" if city and state else pincode_info.get('substore_name', 'Available')

    await loading_msg.edit_text(
        f"""
✅ *Pincode Set Successfully!*

━━━━━━━━━━━━━━━━━━━━━━
📍 *Pincode:* `{pincode_info['pincode']}`
🏪 *Area:* {location}
━━━━━━━━━━━━━━━━━━━━━━

🎯 *Next Step:*
Select products you want to track!

👇 *Tap the button below:*
""",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    query = update.callback_query
    await query.answer("Cancelled")

    USER_STATES.pop(query.from_user.id, None)

    user = db.get_user(query.from_user.id)
    has_pincode = user and user.get("pincode")

    await query.edit_message_text(
        "❌ *Cancelled*\n\nChoose an option below:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(has_pincode)
    )


async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available products for subscription"""
    USER_STATES.pop(update.effective_user.id, None)
    user = db.get_user(update.effective_user.id)

    if not user or not user.get("pincode"):
        keyboard = [[InlineKeyboardButton("📍 Set Pincode First", callback_data="cb_setpincode")]]
        await update.message.reply_text(
            "⚠️ *Pincode Required*\n\nPlease set your pincode first!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    loading_msg = await update.message.reply_text(
        "🔄 *Loading Products...*\n\n⏳ _Fetching latest stock data..._",
        parse_mode="Markdown"
    )

    await _show_products_list(loading_msg, user, update.effective_user.id, context)


async def show_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show products from callback"""
    query = update.callback_query
    await query.answer()

    USER_STATES.pop(query.from_user.id, None)
    user = db.get_user(query.from_user.id)

    if not user or not user.get("pincode"):
        keyboard = [[InlineKeyboardButton("📍 Set Pincode First", callback_data="cb_setpincode")]]
        await query.edit_message_text(
            "⚠️ *Pincode Required*\n\nPlease set your pincode first!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await query.edit_message_text(
        "🔄 *Loading Products...*\n\n⏳ _Fetching latest stock data..._",
        parse_mode="Markdown"
    )

    await _show_products_list(query, user, query.from_user.id, context, is_callback=True)


async def _show_products_list(msg, user, user_id, context, is_callback=False):
    """Helper to show products list"""
    try:
        amul_api.set_pincode(user["pincode"], user["substore_id"])
        products = amul_api.get_protein_products(user["substore_id"])

        if not products:
            keyboard = [
                [InlineKeyboardButton("🔄 Retry", callback_data="cb_products")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
            ]
            if is_callback:
                await msg.edit_message_text(
                    "❌ *Could not load products*\n\nPlease try again.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await msg.edit_text(
                    "❌ *Could not load products*\n\nPlease try again.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            return

        # Save products to database
        for p in products:
            db.upsert_product(
                p["id"], p["sku"], p["name"],
                p.get("price", 0), p.get("image_url", ""),
                p.get("category", ""),
                p.get("in_stock", False), p.get("quantity", 0)
            )

        context.user_data["products_cache"] = products

        subscriptions = db.get_user_subscriptions(user_id)
        subscribed_skus = [s["product_sku"] for s in subscriptions]

        # Create modern keyboard
        keyboard = []
        for product in products:
            is_subscribed = product["sku"] in subscribed_skus
            is_in_stock = product.get("in_stock", False)

            sub_icon = "✅" if is_subscribed else "⬜"
            stock_icon = "🟢" if is_in_stock else "🔴"

            name = product['name'][:28]
            btn_text = f"{sub_icon} {name} {stock_icon}"

            keyboard.append([
                InlineKeyboardButton(btn_text, callback_data=f"toggle_{product['sku']}")
            ])

        keyboard.append([
            InlineKeyboardButton("✅ Save & Continue", callback_data="products_done"),
            InlineKeyboardButton("🔄 Refresh", callback_data="cb_products")
        ])
        keyboard.append([
            InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        message = f"""
╔══════════════════════════════════╗
        🛒 *SELECT PRODUCTS*
╚══════════════════════════════════╝

📍 Pincode: *{user['pincode']}*

━━━━━━━━━━━━━━━━━━━━━━
✅ = Tracking  │  ⬜ = Not tracking
🟢 = In Stock  │  🔴 = Out of Stock
━━━━━━━━━━━━━━━━━━━━━━

👆 _Tap a product to toggle tracking_
"""

        if is_callback:
            await msg.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await msg.edit_text(message, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error showing products: {e}")
        keyboard = [
            [InlineKeyboardButton("🔄 Retry", callback_data="cb_products")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
        ]
        error_msg = f"❌ *Error loading products*\n\n_{str(e)[:100]}_"
        if is_callback:
            await msg.edit_message_text(error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg.edit_text(error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_product_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product subscription toggle"""
    query = update.callback_query
    await query.answer("Updating...", show_alert=False)

    data = query.data

    if data == "products_done":
        subscriptions = db.get_user_subscriptions(query.from_user.id)

        if subscriptions:
            cached_products = context.user_data.get("products_cache", [])
            stock_by_sku = {p["sku"]: p for p in cached_products}

            in_stock_items = []
            out_stock_items = []

            for sub in subscriptions:
                sku = sub["product_sku"]
                product = stock_by_sku.get(sku)
                name = sub.get('name', sub.get('product_name', 'Unknown'))[:25]

                if product and product.get("in_stock", False):
                    qty = product.get('quantity', 0)
                    in_stock_items.append(f"🟢 {name} (Qty: {qty})")
                else:
                    out_stock_items.append(f"🔴 {name}")

            message = """
╔══════════════════════════════════╗
      ✅ *SUBSCRIPTIONS SAVED*
╚══════════════════════════════════╝

"""
            if in_stock_items:
                message += "*🟢 In Stock Now:*\n"
                message += "\n".join(in_stock_items) + "\n\n"

            if out_stock_items:
                message += "*🔴 Out of Stock:*\n"
                message += "\n".join(out_stock_items) + "\n\n"

            message += f"""━━━━━━━━━━━━━━━━━━━━━━
🔔 *Tracking {len(subscriptions)} product(s)*

⚡ I'll check every 30 seconds
📲 You'll get instant alerts!
"""

            keyboard = [
                [
                    InlineKeyboardButton("📦 Check Stock", callback_data="cb_instock"),
                    InlineKeyboardButton("📊 My Status", callback_data="cb_mystatus")
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
            ]

            await query.edit_message_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [
                [InlineKeyboardButton("🛒 Select Products", callback_data="cb_products")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
            ]
            await query.edit_message_text(
                "⚠️ *No Products Selected*\n\nYou need to select at least one product to track.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    if data.startswith("toggle_"):
        sku = data.replace("toggle_", "")
        user_id = query.from_user.id
        user = db.get_user(user_id)

        if "products_cache" not in context.user_data:
            context.user_data["products_cache"] = db.get_all_products()

        cached_products = context.user_data["products_cache"]
        subscriptions = db.get_user_subscriptions(user_id)
        subscribed_skus = [s["product_sku"] for s in subscriptions]

        # Toggle subscription
        if sku in subscribed_skus:
            db.remove_subscription(user_id, sku)
            subscribed_skus.remove(sku)
        else:
            db.add_subscription(user_id, sku)
            db.set_user_active(user_id, True)
            subscribed_skus.append(sku)

        # Rebuild keyboard
        keyboard = []
        for product in cached_products:
            is_subscribed = product["sku"] in subscribed_skus
            is_in_stock = product.get("in_stock", False)

            sub_icon = "✅" if is_subscribed else "⬜"
            stock_icon = "🟢" if is_in_stock else "🔴"

            name = product['name'][:28]
            btn_text = f"{sub_icon} {name} {stock_icon}"

            keyboard.append([
                InlineKeyboardButton(btn_text, callback_data=f"toggle_{product['sku']}")
            ])

        keyboard.append([
            InlineKeyboardButton("✅ Save & Continue", callback_data="products_done"),
            InlineKeyboardButton("🔄 Refresh", callback_data="cb_products")
        ])
        keyboard.append([
            InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception:
            pass


async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's current status"""
    USER_STATES.pop(update.effective_user.id, None)
    await _show_status(update.message, update.effective_user.id)


async def my_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show status from callback"""
    query = update.callback_query
    await query.answer()
    USER_STATES.pop(query.from_user.id, None)
    await _show_status(query, query.from_user.id, is_callback=True)


async def _show_status(msg, user_id, is_callback=False):
    """Helper to show status"""
    user = db.get_user(user_id)

    if not user:
        keyboard = [[InlineKeyboardButton("🚀 Get Started", callback_data="cb_start")]]
        text = "⚠️ *Not Registered*\n\nTap below to get started!"
        if is_callback:
            await msg.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    subscriptions = db.get_user_subscriptions(user_id)

    status_icon = "✅ Active" if user.get('is_active') else "⏸️ Paused"

    status_text = f"""
╔══════════════════════════════════╗
         📊 *YOUR STATUS*
╚══════════════════════════════════╝

*📍 Location:*
┌─────────────────────────────
│ Pincode: `{user.get('pincode', 'Not set')}`
│ Area: {user.get('substore_name', 'Not set')}
└─────────────────────────────

*🔔 Notifications:* {status_icon}

*🛒 Tracked Products ({len(subscriptions)}):*
"""

    if subscriptions:
        for i, sub in enumerate(subscriptions, 1):
            name = sub.get('name', sub.get('product_name', 'Unknown'))[:30]
            price = sub.get('price', 'N/A')
            status_text += f"│ {i}. {name}\n│    ₹{price}\n"
    else:
        status_text += "│ _No products selected_\n"

    status_text += """
━━━━━━━━━━━━━━━━━━━━━━
"""

    keyboard = [
        [
            InlineKeyboardButton("🛒 Products", callback_data="cb_products"),
            InlineKeyboardButton("📦 Stock", callback_data="cb_instock")
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
    ]

    if is_callback:
        await msg.edit_message_text(status_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg.reply_text(status_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def check_instock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check what's currently in stock"""
    USER_STATES.pop(update.effective_user.id, None)
    loading_msg = await update.message.reply_text(
        "📦 *Checking Stock...*\n\n⏳ _Fetching live data..._",
        parse_mode="Markdown"
    )
    await _check_stock(loading_msg, update.effective_user.id, context)


async def check_instock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check stock from callback"""
    query = update.callback_query
    await query.answer()
    USER_STATES.pop(query.from_user.id, None)

    await query.edit_message_text(
        "📦 *Checking Stock...*\n\n⏳ _Fetching live data..._",
        parse_mode="Markdown"
    )
    await _check_stock(query, query.from_user.id, context, is_callback=True)


async def _check_stock(msg, user_id, context, is_callback=False):
    """Helper to check stock"""
    user = db.get_user(user_id)

    if not user or not user.get("pincode"):
        keyboard = [[InlineKeyboardButton("📍 Set Pincode", callback_data="cb_setpincode")]]
        text = "⚠️ *Pincode Required*\n\nPlease set your pincode first!"
        if is_callback:
            await msg.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    try:
        amul_api.set_pincode(user["pincode"], user["substore_id"])
        products = amul_api.get_in_stock_products(user["substore_id"])

        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="cb_instock"),
                InlineKeyboardButton("🛒 Track", callback_data="cb_products")
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
        ]

        if not products:
            text = f"""
╔══════════════════════════════════╗
         📦 *STOCK STATUS*
╚══════════════════════════════════╝

📍 Pincode: *{user['pincode']}*

━━━━━━━━━━━━━━━━━━━━━━
🔴 *All products out of stock*

Don't worry! I'll notify you
instantly when they're available.
━━━━━━━━━━━━━━━━━━━━━━
"""
            if is_callback:
                await msg.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await msg.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        message = f"""
╔══════════════════════════════════╗
         📦 *STOCK STATUS*
╚══════════════════════════════════╝

📍 Pincode: *{user['pincode']}*

━━━━━━━━━━━━━━━━━━━━━━
🟢 *{len(products)} Product(s) In Stock:*
━━━━━━━━━━━━━━━━━━━━━━

"""
        for p in products:
            message += f"""┌─────────────────────────────
│ *{p['name'][:30]}*
│ 💰 ₹{p['price']} │ 📦 Qty: {p['quantity']}
│ 🛒 [Order Now]({p['product_url']})
└─────────────────────────────

"""

        if is_callback:
            await msg.edit_message_text(message, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg.edit_text(message, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Stock check error: {e}")
        keyboard = [
            [InlineKeyboardButton("🔄 Retry", callback_data="cb_instock")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="cb_start")]
        ]
        text = "❌ *Error checking stock*\n\nPlease try again."
        if is_callback:
            await msg.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def stop_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop all notifications"""
    USER_STATES.pop(update.effective_user.id, None)
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Stop All", callback_data="confirm_stop"),
            InlineKeyboardButton("❌ No, Keep", callback_data="cancel_stop")
        ]
    ]
    await update.message.reply_text(
        "⚠️ *Stop Notifications?*\n\n"
        "This will unsubscribe you from all product alerts.\n\n"
        "Are you sure?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop from callback"""
    query = update.callback_query
    await query.answer()
    USER_STATES.pop(query.from_user.id, None)

    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Stop", callback_data="confirm_stop"),
            InlineKeyboardButton("❌ No, Keep", callback_data="cancel_stop")
        ]
    ]
    await query.edit_message_text(
        "⚠️ *Stop Notifications?*\n\n"
        "This will unsubscribe you from all product alerts.\n\n"
        "Are you sure?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_stop_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stop confirmation"""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_stop":
        db.clear_user_subscriptions(query.from_user.id)
        db.set_user_active(query.from_user.id, False)

        keyboard = [[InlineKeyboardButton("🚀 Start Again", callback_data="cb_start")]]
        await query.edit_message_text(
            "✅ *Notifications Stopped*\n\n"
            "You've been unsubscribed from all alerts.\n\n"
            "Tap below to start again anytime!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        user = db.get_user(query.from_user.id)
        has_pincode = user and user.get("pincode")
        await query.edit_message_text(
            "✅ *Notifications Active*\n\n"
            "Your subscriptions remain active.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(has_pincode)
        )


async def handle_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu callback"""
    query = update.callback_query
    await query.answer()
    USER_STATES.pop(query.from_user.id, None)

    user = db.get_user(query.from_user.id)
    has_pincode = user and user.get("pincode")

    welcome = f"""
╔══════════════════════════════════╗
     🥛 *AMUL PROTEIN ALERTS* 🥛
╚══════════════════════════════════╝

"""
    if has_pincode:
        welcome += f"📍 Pincode: *{user['pincode']}*\n\n"
    welcome += "👇 *Choose an option:*"

    await query.edit_message_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(has_pincode)
    )


async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help callback"""
    query = update.callback_query
    await query.answer()
    USER_STATES.pop(query.from_user.id, None)

    user = db.get_user(query.from_user.id)
    has_pincode = user and user.get("pincode")

    help_text = """
╔══════════════════════════════════╗
          ❓ *HELP CENTER*
╚══════════════════════════════════╝

*🔹 How It Works:*
1️⃣ Set your pincode
2️⃣ Choose products to track
3️⃣ I check stock every 30 sec
4️⃣ Get notified when available!

*🔹 Tips:*
• Tap buttons for quick actions
• You can track multiple products
"""
    await query.edit_message_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(has_pincode)
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    current_state = USER_STATES.get(user_id)
    logger.info(f"Received text '{text}' from user {user_id}, state={current_state}, USER_STATES={USER_STATES}")

    # Check if we're waiting for a pincode
    if current_state == "awaiting_pincode":
        logger.info(f"Processing as pincode input for user {user_id}")
        await process_pincode(update, context)
        return

    # Default response - show menu
    user = db.get_user(user_id)
    has_pincode = user and user.get("pincode")

    await update.message.reply_text(
        "👋 *Need help?*\n\nUse the buttons below or type /help",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(has_pincode)
    )


def setup_handlers(application: Application):
    """Set up all bot handlers"""

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setpincode", set_pincode_command))
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(CommandHandler("mystatus", my_status))
    application.add_handler(CommandHandler("instock", check_instock))
    application.add_handler(CommandHandler("stop", stop_notifications))
    application.add_handler(CommandHandler("cancel", lambda u, c: cancel_callback(u, c)))

    # Callback query handlers - ORDER MATTERS!
    application.add_handler(CallbackQueryHandler(set_pincode_callback, pattern="^cb_setpincode$"))
    application.add_handler(CallbackQueryHandler(cancel_callback, pattern="^cb_cancel$"))
    application.add_handler(CallbackQueryHandler(show_products_callback, pattern="^cb_products$"))
    application.add_handler(CallbackQueryHandler(my_status_callback, pattern="^cb_mystatus$"))
    application.add_handler(CallbackQueryHandler(check_instock_callback, pattern="^cb_instock$"))
    application.add_handler(CallbackQueryHandler(stop_callback, pattern="^cb_stop$"))
    application.add_handler(CallbackQueryHandler(handle_start_callback, pattern="^cb_start$"))
    application.add_handler(CallbackQueryHandler(handle_help_callback, pattern="^cb_help$"))
    application.add_handler(CallbackQueryHandler(handle_product_toggle, pattern="^toggle_|^products_done$"))
    application.add_handler(CallbackQueryHandler(handle_stop_confirm, pattern="^confirm_stop$|^cancel_stop$"))

    # Text message handler - MUST BE LAST
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("All handlers registered successfully")
