from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from database import Database
from scraper import AmulAPI

# Conversation states
WAITING_PINCODE = 1
SELECTING_PRODUCTS = 2

# Initialize database and API
db = Database()
amul_api = AmulAPI()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)

    welcome_message = f"""
*Welcome to Amul Protein Stock Alert Bot!*

Hi {user.first_name}! I'll help you get instant notifications when Amul protein products are available in your area.

*How to use:*
1. Set your pincode using /setpincode
2. Select products to track using /products
3. Get notified when they're in stock!

*Commands:*
/setpincode - Set your delivery pincode
/products - Select products to track
/mystatus - View your subscriptions
/stop - Unsubscribe from all alerts
/help - Show this help message

Let's start! Use /setpincode to set your location.
"""

    # Add inline keyboard for quick options
    keyboard = [
        [InlineKeyboardButton("Set Pincode", callback_data="set_pincode")],
        [InlineKeyboardButton("Select Products", callback_data="products")],
        [InlineKeyboardButton("View Status", callback_data="mystatus")],
        [InlineKeyboardButton("Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, parse_mode="Markdown", reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
*Amul Protein Stock Alert Bot*

*Commands:*
/start - Start the bot
/setpincode - Set your delivery pincode
/products - Browse & select products to track
/mystatus - View your current subscriptions
/instock - Check what's currently in stock
/stop - Unsubscribe from all notifications
/help - Show this help message

*How it works:*
1. Set your pincode (delivery location)
2. Choose which protein products you want to track
3. I'll check stock every 5 minutes
4. When your products are available, you'll get a notification with quantity!

*Note:* Notifications continue until the product is sold out.
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def set_pincode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start pincode setting conversation"""
    user = db.get_user(update.effective_user.id)
    current_pincode = user.get("pincode") if user else None

    message = "Please enter your 6-digit delivery pincode:"
    if current_pincode:
        message = f"Your current pincode is *{current_pincode}*.\n\nEnter a new pincode to change it, or /cancel to keep current:"

    await update.message.reply_text(message, parse_mode="Markdown")
    return WAITING_PINCODE


async def set_pincode_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and validate pincode"""
    pincode = update.message.text.strip()

    # Validate pincode format
    if not pincode.isdigit() or len(pincode) != 6:
        await update.message.reply_text(
            "Invalid pincode. Please enter a valid 6-digit pincode:"
        )
        return WAITING_PINCODE

    # Search pincode on Amul
    await update.message.reply_text("Checking pincode availability...")

    pincode_info = amul_api.search_pincode(pincode)

    if not pincode_info:
        await update.message.reply_text(
            "Sorry, Amul doesn't deliver to this pincode yet.\n"
            "Please try a different pincode:"
        )
        return WAITING_PINCODE

    # Save to database
    db.update_user_pincode(
        update.effective_user.id,
        pincode_info["pincode"],
        pincode_info["substore_id"],
        pincode_info["substore_name"]
    )

    await update.message.reply_text(
        f"✅ *Pincode set successfully!*\n\n"
        f"📍 *Pincode:* {pincode_info['pincode']}\n"
        f"🏪 *Store:* {pincode_info['substore_name']}\n"
        f"🏙️ *City:* {pincode_info.get('city', 'N/A')}\n\n"
        f"*Next Step:*\n"
        f"Use /products to select which protein products you want to track!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("Cancelled. Use /help to see available commands.")
    return ConversationHandler.END


async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available products for subscription"""
    user = db.get_user(update.effective_user.id)

    if not user or not user.get("pincode"):
        await update.message.reply_text(
            "Please set your pincode first using /setpincode"
        )
        return

    # Show loading message
    loading_msg = await update.message.reply_text(
        "⏳ *Fetching available products...*\n\n_This may take 10-15 seconds_",
        parse_mode="Markdown"
    )

    try:
        # Get products from Amul
        products = amul_api.get_protein_products(user["substore_id"])

        if not products:
            await loading_msg.edit_text(
                "❌ Could not fetch products. Please try again later."
            )
            return

        # Save products to database - CRITICAL: must save before checking subscriptions
        for p in products:
            db.upsert_product(
                p["id"],
                p["sku"],
                p["name"],
                p.get("price", 0),
                p.get("image_url", ""),
                p.get("category", ""),
                p.get("in_stock", False),  # Save stock status
                p.get("quantity", 0)        # Save quantity
            )

        # Store products in context for fast UI updates
        context.user_data["products_cache"] = products

        # Get user's current subscriptions
        subscriptions = db.get_user_subscriptions(update.effective_user.id)
        subscribed_skus = [s["product_sku"] for s in subscriptions]

        # Create inline keyboard with products
        keyboard = []
        for product in products:
            status = "✅" if product["sku"] in subscribed_skus else "⬜"
            stock_status = "🟢" if product["in_stock"] else "🔴"
            btn_text = f"{status} {product['name'][:30]} {stock_status}"
            keyboard.append([
                InlineKeyboardButton(
                    btn_text,
                    callback_data=f"toggle_{product['sku']}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("✅ Done", callback_data="products_done")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Replace loading message with product list
        await loading_msg.edit_text(
            "*✅ Select products to track:*\n\n"
            "✅ = Subscribed | ⬜ = Not subscribed\n"
            "🟢 = In Stock | 🔴 = Out of Stock\n\n"
            "_Tap a product to toggle subscription_",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        await loading_msg.edit_text(
            f"❌ Error loading products: {str(e)}\n\nPlease try again."
        )


async def handle_product_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product subscription toggle"""
    query = update.callback_query
    await query.answer()  # Instant acknowledgment without text

    data = query.data

    if data == "products_done":
        subscriptions = db.get_user_subscriptions(query.from_user.id)
        if subscriptions:
            # Get cached products to show current stock status
            cached_products = context.user_data.get("products_cache", [])
            stock_by_sku = {p["sku"]: p for p in cached_products}

            # Build message with stock status
            message = "*✅ Your subscriptions saved!*\n\n"
            message += f"*Current Stock Status:*\n\n"

            in_stock_items = []
            out_stock_items = []

            for sub in subscriptions:
                sku = sub["product_sku"]
                product = stock_by_sku.get(sku)

                if product:
                    if product.get("in_stock", False):
                        in_stock_items.append(f"🟢 {sub['name']} - Qty: {product.get('quantity', 0)}")
                    else:
                        out_stock_items.append(f"🔴 {sub['name']} - Out of stock")
                else:
                    out_stock_items.append(f"⚠️ {sub['name']} - Status unknown")

            if in_stock_items:
                message += "\n".join(in_stock_items) + "\n\n"
            if out_stock_items:
                message += "\n".join(out_stock_items) + "\n\n"

            message += f"🔔 *Monitoring {len(subscriptions)} product(s)*\n\n"
            message += f"*Next Steps:*\n"
            message += f"• Use /mystatus to view subscriptions\n"
            message += f"• Use /instock for updated availability\n"
            message += f"• I'll check stock every 30 seconds and alert you when status changes!"

            await query.edit_message_text(message, parse_mode="Markdown")
        else:
            await query.edit_message_text(
                "⚠️ No products selected.\n\nUse /products to select products to track."
            )
        return

    if data.startswith("toggle_"):
        sku = data.replace("toggle_", "")
        user_id = query.from_user.id

        # Store in context to avoid re-fetching products
        if "products_cache" not in context.user_data:
            # Fallback: get from DB if not in context
            context.user_data["products_cache"] = db.get_all_products()

        cached_products = context.user_data["products_cache"]

        # Check current subscription status - single query
        subscriptions = db.get_user_subscriptions(user_id)
        subscribed_skus = [s["product_sku"] for s in subscriptions]

        # Quick toggle - just update DB, no re-fetch
        if sku in subscribed_skus:
            db.remove_subscription(user_id, sku)
            subscribed_skus.remove(sku)
        else:
            db.add_subscription(user_id, sku)
            db.set_user_active(user_id, True)
            # Mark this subscription as "just added" to prevent immediate alert
            context.user_data[f"new_subscription_{sku}"] = True
            subscribed_skus.append(sku)

        # Rebuild keyboard using CACHED products (no DB query)
        keyboard = []
        for product in cached_products:
            status = "✅" if product["sku"] in subscribed_skus else "⬜"
            in_stock = product.get("in_stock", 0) > 0
            stock_status = "🟢" if in_stock else "🔴"
            btn_text = f"{status} {product['name'][:30]} {stock_status}"
            keyboard.append([
                InlineKeyboardButton(
                    btn_text,
                    callback_data=f"toggle_{product['sku']}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("✅ Done", callback_data="products_done")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception:
            # Fallback: edit full message if reply_markup edit fails
            await query.edit_message_text(
                "*✅ Select products to track:*\n\n"
                "✅ = Subscribed | ⬜ = Not subscribed\n"
                "🟢 = In Stock | 🔴 = Out of Stock\n\n"
                "_Tap a product to toggle subscription_",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )


async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's current status and subscriptions"""
    user = db.get_user(update.effective_user.id)

    if not user:
        await update.message.reply_text(
            "You haven't set up your account yet. Use /start to begin."
        )
        return

    subscriptions = db.get_user_subscriptions(update.effective_user.id)

    status_text = f"""
📊 *Your Status*

📍 *Pincode:* {user.get('pincode', 'Not set')}
🏪 *Store:* {user.get('substore_name', 'Not set')}
🔔 *Notifications:* {'✅ Active' if user.get('is_active') else '⏸️ Paused'}

*Tracked Products ({len(subscriptions)}):*
"""
    if subscriptions:
        for sub in subscriptions:
            status_text += f"• {sub['name']} (₹{sub.get('price', 'N/A')})\n"
    else:
        status_text += "_No products selected_\n"

    status_text += f"\n*Next Steps:*\n"
    status_text += f"• /products - Modify tracked products\n"
    status_text += f"• /instock - Check current availability\n"
    status_text += f"• I check stock every 30 seconds!"

    await update.message.reply_text(status_text, parse_mode="Markdown")


async def check_instock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check what's currently in stock"""
    user = db.get_user(update.effective_user.id)

    if not user or not user.get("pincode"):
        await update.message.reply_text(
            "Please set your pincode first using /setpincode"
        )
        return

    await update.message.reply_text("Checking current stock...")

    products = amul_api.get_in_stock_products(user["substore_id"])

    if not products:
        await update.message.reply_text(
            "No protein products are currently in stock at your location.\n"
            "Use /products to subscribe for notifications when they're available!"
        )
        return

    message = f"*🟢 Products In Stock at {user['pincode']}:*\n\n"
    for p in products:
        message += f"• *{p['name']}*\n"
        message += f"  💰 Price: ₹{p['price']} | 📦 Qty: {p['quantity']}\n"
        message += f"  🛒 [Order Now]({p['product_url']})\n\n"

    message += f"\n*Next Steps:*\n"
    message += f"• Use /products to track these items\n"
    message += f"• I'll alert you when stock changes!"

    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)


async def stop_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop all notifications"""
    user_id = update.effective_user.id

    keyboard = [
        [
            InlineKeyboardButton("Yes, unsubscribe all", callback_data="confirm_stop"),
            InlineKeyboardButton("No, keep them", callback_data="cancel_stop")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Are you sure you want to unsubscribe from all notifications?",
        reply_markup=reply_markup
    )


async def handle_stop_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stop confirmation"""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_stop":
        db.clear_user_subscriptions(query.from_user.id)
        db.set_user_active(query.from_user.id, False)
        await query.edit_message_text(
            "You have been unsubscribed from all notifications.\n"
            "Use /start to subscribe again anytime!"
        )
    else:
        await query.edit_message_text(
            "Your subscriptions remain active."
        )


async def show_sidebar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show sidebar with options"""
    keyboard = [
        [InlineKeyboardButton("Set Pincode", callback_data="set_pincode")],
        [InlineKeyboardButton("Select Products", callback_data="products")],
        [InlineKeyboardButton("View Status", callback_data="mystatus")],
        [InlineKeyboardButton("Help", callback_data="help")],
        [InlineKeyboardButton("Stop Notifications", callback_data="stop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "*Sidebar Options:*\n\nChoose an action:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /instock command or button to check current stock status."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user or not user.get("pincode"):
        await update.message.reply_text(
            "You need to set your pincode first using /setpincode.",
            parse_mode="Markdown"
        )
        return

    subscriptions = db.get_user_subscriptions(user_id)
    if not subscriptions:
        await update.message.reply_text(
            "You are not tracking any products. Use /products to select products to track.",
            parse_mode="Markdown"
        )
        return

    # Send an animation or loading message
    loading_message = await update.message.reply_text(
        "Checking stock status... This may take a few seconds. 🕒",
        parse_mode="Markdown"
    )

    amul_api.init_session()
    products = amul_api.get_protein_products(user["substore_id"])

    if not products:
        await loading_message.edit_text(
            "Unable to fetch stock data at the moment. Please try again later.",
            parse_mode="Markdown"
        )
        return

    stock_by_sku = {p["sku"]: p for p in products}
    status_message = "*Your Tracked Products Stock Status:*\n\n"

    for sub in subscriptions:
        sku = sub["product_sku"]
        product = stock_by_sku.get(sku)
        if product and product["in_stock"]:
            status_message += (
                f"🟢 *{product['name']}*\n"
                f"Quantity: {product['quantity']}\n"
                f"Price: ₹{product['price']}\n"
                f"[Order Now]({product['product_url']})\n\n"
            )
        else:
            status_message += f"🔴 *{sub['product_name']}* is out of stock.\n\n"

    await loading_message.edit_text(status_message, parse_mode="Markdown", disable_web_page_preview=True)


def setup_handlers(application: Application):
    """Set up all bot handlers"""

    # Pincode conversation handler
    pincode_conv = ConversationHandler(
        entry_points=[CommandHandler("setpincode", set_pincode_start)],
        states={
            WAITING_PINCODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_pincode_receive)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(pincode_conv)
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(CommandHandler("mystatus", my_status))
    application.add_handler(CommandHandler("instock", check_instock))
    application.add_handler(CommandHandler("stop", stop_notifications))
    application.add_handler(CommandHandler("instock", check_status))

    # Callback query handlers
    application.add_handler(CallbackQueryHandler(handle_product_toggle, pattern="^toggle_|^products_done$"))
    application.add_handler(CallbackQueryHandler(handle_stop_confirm, pattern="^confirm_stop$|^cancel_stop$"))
