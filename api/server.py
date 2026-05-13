from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application
from app.config import settings
from app.interface.telegram_handler import setup_handlers
from app.database.connection import init_db
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize PTB Application
ptb_app = Application.builder().token(settings.telegram_token).build()
setup_handlers(ptb_app)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(url=settings.webhook_url)
    await ptb_app.start()
    logger.info(f"Webhook set to {settings.webhook_url}")
    yield
    # Shutdown
    await ptb_app.bot.delete_webhook()
    await ptb_app.stop()
    await ptb_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        logger.info("--- Received Webhook ---")
        data = await request.json()
        logger.info(f"Update data: {data}")
        
        update = Update.de_json(data, ptb_app.bot)
        logger.info(f"Processing update {update.update_id}")
        
        await ptb_app.process_update(update)
        
        logger.info(f"Successfully processed update {update.update_id}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
