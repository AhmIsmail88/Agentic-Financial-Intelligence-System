import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.graph.workflow import app_graph
from langgraph.types import Command
from app.config import settings

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Handling /start command")
    await update.message.reply_text("Hi! I'm your Agentic Finance Assistant. Send me your expenses or ask about your spending!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Handling message: {update.message.text}")
    text = update.message.text
    user_id = update.effective_user.id
    
    config = {"configurable": {"thread_id": str(user_id)}}
    
    # Run the graph with a fully initialized state
    initial_state = {
        "user_message": text,
        "telegram_id": user_id,
        "thread_id": str(user_id),
        "conversation_history": [],
        "intent": None,
        "extracted_data": None,
        "query_key": None,
        "query_params": None,
        "sql_result": None,
        "needs_clarification": False,
        "clarification_question": None,
        "pending_confirmation": False,
        "confirmation_action": None,
        "operation_status": None,
        "response": None,
        "error": None,
    }
    
    try:
        result = await app_graph.ainvoke(initial_state, config=config)
        
        if result.get("needs_clarification"):
            await update.message.reply_text(result["clarification_question"])
        elif result.get("intent") == "delete_entry" and result.get("response") is None:
            # This means it's interrupted at confirm_delete
            keyboard = [
                [
                    InlineKeyboardButton("Yes, delete it", callback_data="delete_confirm"),
                    InlineKeyboardButton("No, keep it", callback_data="delete_cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Are you sure you want to delete your last expense?", reply_markup=reply_markup)
        else:
            await update.message.reply_text(result.get("response", "I'm not sure how to help with that."))
            
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text("Oops, something went wrong. Please try again.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    config = {"configurable": {"thread_id": str(user_id)}}
    
    if query.data == "delete_confirm":
        # Resume graph with confirmation
        result = await app_graph.ainvoke(Command(resume=True), config=config)
        await query.edit_message_text(result.get("response", "Deleted."))
    else:
        # Resume graph with cancellation
        result = await app_graph.ainvoke(Command(resume=False), config=config)
        await query.edit_message_text("Deletion cancelled.")

def setup_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
