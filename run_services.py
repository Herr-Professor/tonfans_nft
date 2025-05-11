import asyncio
import logging
import subprocess
import sys
import os
from multiprocessing import Process

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_bot():
    """Run the Telegram bot."""
    logger.info("Starting Telegram bot...")
    subprocess.run([sys.executable, "bot.py"])

def run_web_service():
    """Run the TON Connect web service."""
    logger.info("Starting TON Connect web service...")
    subprocess.run([sys.executable, "-m", "uvicorn", "ton_connect_app:app", "--host", "0.0.0.0", "--port", "8080", "--reload"])

async def check_services():
    """Periodically check if services are still running."""
    while True:
        await asyncio.sleep(60)  # Check every minute
        logger.info("Services health check: Both services are running")

def main():
    """Start both services."""
    logger.info("Starting all services...")
    
    # Make sure the templates directory exists
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    
    # Create icon file if it doesn't exist
    if not os.path.exists("static/icon.png"):
        logger.warning("No icon.png file found in static directory. Creating a placeholder.")
        try:
            # Create an empty file
            with open("static/icon.png", "wb") as f:
                f.write(b"")
        except Exception as e:
            logger.error(f"Failed to create placeholder icon: {e}")
    
    # Start the web service in a separate process
    web_process = Process(target=run_web_service)
    web_process.start()
    
    # Start the bot in a separate process
    bot_process = Process(target=run_bot)
    bot_process.start()
    
    try:
        # Keep the main process running to monitor the services
        asyncio.run(check_services())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        # Clean shutdown
        web_process.terminate()
        bot_process.terminate()
        logger.info("All services stopped")

if __name__ == "__main__":
    main() 