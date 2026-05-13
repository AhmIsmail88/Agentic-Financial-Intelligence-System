import os
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from app.config import settings
from app.graph.state import AgentState

FIXED_CATEGORIES = Literal[
    "Food", "Transport", "Utilities", "Entertainment",
    "Electronics", "Health", "Education", "Shopping",
    "Housing", "Other"
]

class ExpenseSchema(BaseModel):
    item: str = Field(description="The item or service purchased")
    # Using float instead of Decimal to avoid the look-around regex that crashes
    # grammar-enforcing providers (NVIDIA, Qwen free tier, etc.)
    amount: float | None = Field(
        default=None,
        description="The numeric cost of the item as a plain number, e.g. 150.0. Null if not mentioned."
    )
    currency: str = Field(
        default="EGP",
        description="The currency code. Default is EGP (Egyptian Pound)."
    )
    category: FIXED_CATEGORIES = Field(
        description="The category that best fits this expense."
    )

# --- Model Setup ---
api_key = settings.openrouter_api_key or settings.openai_api_key
base_url = settings.openrouter_base_url if settings.openrouter_api_key else None

# Set environment variables so PydanticAI picks them up automatically
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key
if base_url:
    os.environ["OPENAI_BASE_URL"] = base_url

model = OpenAIModel(settings.extractor_model)

# --- PydanticAI Agent ---
extractor_agent = Agent(
    model,
    output_type=ExpenseSchema,
    system_prompt=(
        "You are a financial data extraction expert. "
        "Extract the expense details from the user's message and return them as structured data.\n\n"
        "Rules:\n"
        "- 'item': What was purchased (e.g. 'pizza', 'taxi ride', 'electricity bill').\n"
        "- 'amount': The numeric cost as a float (e.g. 150.0). Set to null ONLY if no amount is mentioned.\n"
        "- 'currency': The currency mentioned (e.g. EGP, USD). Default to 'EGP' if not specified.\n"
        "- 'category': Must be EXACTLY one of: Food, Transport, Utilities, Entertainment, "
        "Electronics, Health, Education, Shopping, Housing, Other.\n"
        "  Examples: pizza→Food, taxi→Transport, rent→Housing, electricity→Utilities, "
        "phone→Electronics, doctor→Health, book→Education, clothes→Shopping.\n"
        "- Do NOT guess the amount if it is not explicitly stated. Leave it as null.\n"
        "- Do NOT invent categories outside the allowed list."
    )
)

async def extract_data(state: AgentState) -> AgentState:
    history_str = "\n".join([
        f"{m.type}: {m.content}" if hasattr(m, 'type') else str(m)
        for m in state.get("conversation_history", [])
    ])

    try:
        result = await extractor_agent.run(
            f"Conversation context:\n{history_str}\n\nUser Message: {state['user_message']}"
        )

        # Support both .result (new PydanticAI) and .data (old PydanticAI)
        data: ExpenseSchema = getattr(result, 'output', getattr(result, 'result', getattr(result, 'data', None)))

        needs_clarification = False
        clarification_question = None

        if data is None:
            return {
                **state,
                "needs_clarification": True,
                "clarification_question": "I couldn't extract expense details. Could you rephrase? e.g. 'Spent 150 EGP on pizza'"
            }

        if data.amount is None:
            needs_clarification = True
            clarification_question = f"How much did you spend on {data.item}?"

        return {
            **state,
            "extracted_data": data.model_dump(),
            "needs_clarification": needs_clarification,
            "clarification_question": clarification_question
        }

    except Exception as e:
        print(f"DEBUG - Extraction Error: {e}")
        return {
            **state,
            "error": str(e),
            "needs_clarification": True,
            "clarification_question": "I couldn't understand that expense. Try: 'Spent 150 EGP on pizza'"
        }
