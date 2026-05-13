from sqlalchemy import select, text
from app.database.connection import AsyncSessionLocal
from app.database.models import User, Category, Expense
from app.graph.state import AgentState
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

QUERY_TEMPLATES = {
    "total_all_time": """
        SELECT SUM(amount) AS total, COUNT(*) AS count, currency
        FROM expenses
        WHERE user_id = :user_id
        GROUP BY currency
    """,
    "average_per_transaction": """
        SELECT
            ROUND(AVG(amount)::numeric, 2) AS average_per_transaction,
            ROUND(SUM(amount)::numeric, 2) AS total_spent,
            COUNT(*) AS transaction_count,
            ROUND(MIN(amount)::numeric, 2) AS min_transaction,
            ROUND(MAX(amount)::numeric, 2) AS max_transaction,
            currency
        FROM expenses
        WHERE user_id = :user_id
        GROUP BY currency
    """,
    "average_by_category": """
        SELECT c.name AS category,
            ROUND(AVG(e.amount)::numeric, 2) AS average,
            ROUND(SUM(e.amount)::numeric, 2) AS total,
            COUNT(*) AS count
        FROM expenses e JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = :user_id
        GROUP BY c.name ORDER BY average DESC
    """,
    "total_by_category": """
        SELECT c.name, ROUND(SUM(e.amount)::numeric, 2) AS total
        FROM expenses e JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = :user_id AND e.created_at >= :since
        GROUP BY c.name ORDER BY total DESC
    """,
    "total_this_month": """
        SELECT ROUND(SUM(amount)::numeric, 2) AS total, currency FROM expenses
        WHERE user_id = :user_id
          AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
        GROUP BY currency
    """,
    "total_today": """
        SELECT ROUND(SUM(amount)::numeric, 2) AS total, currency FROM expenses
        WHERE user_id = :user_id
          AND DATE_TRUNC('day', created_at) = DATE_TRUNC('day', NOW())
        GROUP BY currency
    """,
    "total_this_week": """
        SELECT ROUND(SUM(amount)::numeric, 2) AS total, currency FROM expenses
        WHERE user_id = :user_id
          AND created_at >= DATE_TRUNC('week', NOW())
        GROUP BY currency
    """,
    "recent_expenses": """
        SELECT item, amount, currency, created_at FROM expenses
        WHERE user_id = :user_id ORDER BY created_at DESC LIMIT :limit
    """,
}

def _select_query(user_message: str, user_id: int) -> tuple[str, dict]:
    """Select the appropriate query template based on keywords in the user message."""
    msg = user_message.lower()

    # Average / mean queries — must come before general keyword checks
    if any(k in msg for k in ["average", "avg", "mean", "per transaction", "rate"]):
        if any(k in msg for k in ["category", "categories", "breakdown"]):
            return "average_by_category", {"user_id": user_id}
        return "average_per_transaction", {"user_id": user_id}

    if any(k in msg for k in ["today"]):
        return "total_today", {"user_id": user_id}

    if any(k in msg for k in ["this week", "week"]):
        return "total_this_week", {"user_id": user_id}

    if any(k in msg for k in ["this month", "month"]):
        return "total_this_month", {"user_id": user_id}

    if any(k in msg for k in ["category", "categories", "breakdown", "by category"]):
        return "total_by_category", {
            "user_id": user_id,
            "since": datetime.utcnow() - timedelta(days=30)
        }

    if any(k in msg for k in ["last", "recent", "show", "list"]):
        return "recent_expenses", {"user_id": user_id, "limit": 5}

    if any(k in msg for k in ["history"]):
        return "recent_expenses", {"user_id": user_id, "limit": 10}

    # Default: total all time for generic "how much" questions
    if any(k in msg for k in ["how much", "total", "so far", "spent", "all"]):
        return "total_all_time", {"user_id": user_id}

    # Fallback
    return "recent_expenses", {"user_id": user_id, "limit": 5}


async def execute_operation(state: AgentState) -> AgentState:
    async with AsyncSessionLocal() as session:
        try:
            # 1. Ensure User exists (upsert)
            user_stmt = select(User).where(User.telegram_id == state["telegram_id"])
            user_result = await session.execute(user_stmt)
            db_user = user_result.scalar_one_or_none()

            if not db_user:
                db_user = User(telegram_id=state["telegram_id"])
                session.add(db_user)
                await session.flush()

            # 2. Handle Intent
            if state.get("intent") == "log_expense":
                data = state.get("extracted_data")
                if not data:
                    return {**state, "response": "I couldn't find the expense details to log."}

                # Resolve category
                cat_stmt = select(Category).where(Category.name == data["category"])
                cat_result = await session.execute(cat_stmt)
                db_category = cat_result.scalar_one_or_none()

                if not db_category:
                    return {**state, "response": f"Unknown category '{data['category']}'. Please try again."}

                new_expense = Expense(
                    user_id=state["telegram_id"],
                    category_id=db_category.id,
                    item=data["item"],
                    amount=data["amount"],
                    currency=data.get("currency", "EGP")
                )
                session.add(new_expense)
                await session.commit()
                return {**state, "operation_status": "success"}

            elif state.get("intent") == "query_finance":
                # Use state values if explicitly set, else auto-select from message
                query_key = state.get("query_key") or None
                params = state.get("query_params") or None  # Use 'or' not default= to handle explicit None

                if not query_key or not params:
                    query_key, params = _select_query(
                        state.get("user_message", ""),
                        state["telegram_id"]
                    )

                template = QUERY_TEMPLATES.get(query_key)
                if not template:
                    return {**state, "response": "I'm not sure how to query that. Try asking for your monthly total or recent expenses."}

                result = await session.execute(text(template), params)
                sql_result = [dict(row._mapping) for row in result.all()]

                if not sql_result or all(v is None for row in sql_result for v in row.values()):
                    return {**state, "response": "No expenses found yet! Start by logging one."}

                return {**state, "sql_result": sql_result, "query_key": query_key}

            elif state.get("intent") == "delete_entry":
                # Only execute after HITL confirmation
                if not state.get("pending_confirmation", True):
                    last_expense_stmt = (
                        select(Expense)
                        .where(Expense.user_id == state["telegram_id"])
                        .order_by(Expense.created_at.desc())
                        .limit(1)
                    )
                    last_expense_res = await session.execute(last_expense_stmt)
                    last_expense = last_expense_res.scalar_one_or_none()

                    if last_expense:
                        await session.delete(last_expense)
                        await session.commit()
                        return {**state, "operation_status": "success"}
                    else:
                        return {**state, "response": "No expenses found to delete."}

            return state

        except Exception as e:
            logger.error(f"Database error: {e}")
            return {**state, "error": str(e), "response": "Sorry, I encountered a database error. Please try again."}
