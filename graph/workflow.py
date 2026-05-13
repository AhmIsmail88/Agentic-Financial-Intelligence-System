from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from app.graph.state import AgentState
from app.agents.router import route_request
from app.agents.extractor import extract_data
from app.agents.db_agent import execute_operation
from app.agents.analyst import summarize_response

def build_graph():
    workflow = StateGraph(AgentState)

    # Define Nodes
    workflow.add_node("router", route_request)
    workflow.add_node("extractor", extract_data)
    workflow.add_node("db_agent", execute_operation)
    workflow.add_node("analyst", summarize_response)

    # Logic for HITL confirmation
    def confirm_delete(state: AgentState):
        if state.get("pending_confirmation"):
            # This is where the graph pauses and waits for user input
            # In a real telegram bot, we send a message with buttons
            # and wait for the callback which will call resume.
            confirm = interrupt("Do you really want to delete this?")
            return {**state, "pending_confirmation": False if confirm else True}
        return state

    workflow.add_node("confirm_delete", confirm_delete)

    # Define Edges
    workflow.set_entry_point("router")

    def route_decision(state: AgentState):
        if state.get("needs_clarification"):
            return "end"
        
        intent = state.get("intent")
        if intent == "log_expense":
            return "extractor"
        elif intent == "query_finance":
            return "db_agent"
        elif intent == "delete_entry":
            return "confirm_delete"
        else:
            return "end"

    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "extractor": "extractor",
            "db_agent": "db_agent",
            "confirm_delete": "confirm_delete",
            "end": END
        }
    )

    workflow.add_edge("extractor", "db_agent")
    workflow.add_edge("confirm_delete", "db_agent")
    workflow.add_edge("db_agent", "analyst")
    workflow.add_edge("analyst", END)

    # Checkpointer is mandatory for interrupt/resume
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

app_graph = build_graph()
