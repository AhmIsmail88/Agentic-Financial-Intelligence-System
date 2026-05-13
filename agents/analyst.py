from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings
from app.graph.state import AgentState

SYSTEM_PROMPT = """You are a helpful and friendly personal finance analyst.
Your task is to provide natural, engaging, and professional responses to the user.
DO NOT perform any mathematical calculations. All numbers come from the database.
Keep responses concise but warm and premium in feel."""

async def summarize_response(state: AgentState) -> AgentState:
    # If there's an error, return it directly — no LLM needed
    if state.get("error"):
        return {**state, "response": f"I ran into a bit of trouble. Please try again."}

    # Build the human message content as a plain string (avoids LangChain template parsing)
    intent = state.get("intent")
    operation_status = state.get("operation_status")
    extracted = state.get("extracted_data")
    sql_result = state.get("sql_result")
    user_message = state.get("user_message", "")

    if intent == "log_expense" and operation_status == "success" and extracted:
        # Format dict manually to avoid curly-brace parsing issues
        item = extracted.get("item", "item")
        amount = extracted.get("amount", "")
        currency = extracted.get("currency", "EGP")
        category = extracted.get("category", "")
        human_text = (
            f"The user just successfully logged this expense:\n"
            f"- Item: {item}\n"
            f"- Amount: {amount} {currency}\n"
            f"- Category: {category}\n\n"
            f"Write a friendly, brief confirmation message (1-2 sentences). "
            f"Add a relevant emoji."
        )
    elif intent == "delete_entry" and operation_status == "success":
        human_text = (
            "The user successfully deleted their last expense entry. "
            "Write a brief, professional confirmation message."
        )
    elif sql_result:
        # Safely convert to string — no dict curly braces exposed to LangChain template
        results_str = str(sql_result)
        human_text = (
            f"The user asked: '{user_message}'\n\n"
            f"Here are the database results:\n{results_str}\n\n"
            f"Summarize this in natural language. DO NOT do any math yourself."
        )
    else:
        return {**state, "response": "I couldn't find any data for that request. Try asking differently!"}

    # Use OpenRouter if key is provided, otherwise fallback to OpenAI
    api_key = settings.openrouter_api_key or settings.openai_api_key
    base_url = settings.openrouter_base_url if settings.openrouter_api_key else None

    llm = ChatOpenAI(
        model=settings.analyst_model,
        api_key=api_key,
        base_url=base_url
    )

    # Use plain message objects — completely bypasses LangChain template variable parsing
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_text)
    ]

    result = await llm.ainvoke(messages)
    assistant_msg = result.content

    return {
        **state,
        "response": assistant_msg,
        "conversation_history": state.get("conversation_history", []) + [("assistant", assistant_msg)]
    }
