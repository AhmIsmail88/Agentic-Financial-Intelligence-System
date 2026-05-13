from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict, total=False):
    # Required fields
    thread_id: str
    user_message: str
    telegram_id: int

    # Conversation history
    conversation_history: list

    # Routing
    intent: Literal["log_expense", "query_finance", "delete_entry", "unknown"] | None

    # Extraction
    extracted_data: dict | None

    # Query finance
    query_key: str | None
    query_params: dict | None
    sql_result: list | None

    # Control flow
    needs_clarification: bool
    clarification_question: str | None
    pending_confirmation: bool
    confirmation_action: dict | None
    operation_status: str | None

    # Output
    response: str | None
    error: str | None
