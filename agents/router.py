from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.graph.state import AgentState

class RouterOutput(BaseModel):
    intent: Literal["log_expense", "query_finance", "delete_entry", "unknown"] = Field(
        description="The classified intent of the user's message."
    )
    clarification_needed: bool = Field(
        description="Whether the intent is unclear and requires clarification."
    )
    clarification_question: str | None = Field(
        description="A friendly question to ask the user if clarification is needed."
    )

async def route_request(state: AgentState) -> AgentState:
    # Use OpenRouter if key is provided, otherwise fallback to OpenAI
    api_key = settings.openrouter_api_key or settings.openai_api_key
    base_url = settings.openrouter_base_url if settings.openrouter_api_key else None
    
    llm = ChatOpenAI(
        model=settings.router_model, 
        api_key=api_key,
        base_url=base_url
    )
    structured_llm = llm.with_structured_output(RouterOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a highly intelligent finance assistant router. 
Your task is to classify the user's intent into one of the following categories:
1. 'log_expense': When the user wants to record a new expense (e.g., "spent 50 on coffee", "lunch for 100").
2. 'query_finance': When the user asks about their spending, totals, or history (e.g., "how much did I spend today?", "show my last 5 expenses").
3. 'delete_entry': When the user wants to remove or delete an expense (e.g., "delete my last expense", "remove the coffee entry").
4. 'unknown': If the intent is completely unrelated to finance or too vague to classify.

If the user's message is ambiguous, set clarification_needed to true and provide a helpful question.
DO NOT hallucinate intents. If unsure, choose 'unknown' or ask for clarification."""),
        ("placeholder", "{history}"),
        ("human", "{user_message}")
    ])
    
    chain = prompt | structured_llm
    
    # We pass the conversation history to maintain context
    result = await chain.ainvoke({
        "history": state.get("conversation_history", []),
        "user_message": state["user_message"]
    })
    
    return {
        **state,
        "intent": result.intent,
        "needs_clarification": result.clarification_needed,
        "clarification_question": result.clarification_question,
        "conversation_history": state.get("conversation_history", []) + [("user", state["user_message"])]
    }
