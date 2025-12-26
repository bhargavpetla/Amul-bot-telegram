import asyncio
import logging
from telegram.ext import Application
import config
from bot import setup_handlers
from scheduler import StockMonitor

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Called after the Application has been initialized"""
    # Start the stock monitor
    stock_monitor = StockMonitor(application.bot)
    application.bot_data["stock_monitor"] = stock_monitor

    # Run stock monitor in background
    asyncio.create_task(stock_monitor.start())
    logger.info("Stock monitor started in background")


async def post_shutdown(application: Application):
    """Called before the Application shuts down"""
    stock_monitor = application.bot_data.get("stock_monitor")
    if stock_monitor:
        stock_monitor.stop()
    logger.info("Stock monitor stopped")


def main():
    """Main function to run the bot"""
    if not config.BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set!")
        print("Please create a .env file with your Telegram bot token.")
        print("See .env.example for reference.")
        return

    # Create application
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Set up handlers
    setup_handlers(application)

    # Start bot
    logger.info("Starting Amul Stock Alert Bot...")
    print("\n" + "=" * 50)
    print("  Amul Protein Stock Alert Bot")
    print("=" * 50)
    print(f"  Stock check interval: {config.STOCK_CHECK_INTERVAL} minutes")
    print("  Bot is running! Press Ctrl+C to stop.")
    print("=" * 50 + "\n")

    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
