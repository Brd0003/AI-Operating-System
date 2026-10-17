from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from state.schema import OSState
from state.checkpointer import QdrantCheckpointer
from swarm.nodes.router import router_node
from swarm.nodes.planner import planner_node
from swarm.nodes.developer import developer_node
from swarm.nodes.executor import executor_node
from swarm.nodes.evaluator import evaluator_node
from swarm.nodes.research import research_node
from swarm.nodes.memory import memory_node


def route_from_router(state: OSState):
    target = state.get("next_agent", "FINISH")
    if target in ("planner", "developer", "executor", "research"):
        return target
    return END


def route_from_evaluator(state: OSState):
    """
    After the evaluator, decide whether to commit memories.

    - "passed"  → memory_node (distill facts, then END)
    - anything else (timeout, failed) → END directly, skip memory write.

    Memory extraction only runs on successfully completed tasks. There's no
    value in storing facts from timed-out or failed exchanges.
    """
    feedback = state.get("evaluation_feedback", "")
    if feedback == "passed":
        return "memory"
    return END


def build_system_graph():
    workflow = StateGraph(OSState)

    workflow.add_node("router", router_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("developer", developer_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("research", research_node)
    workflow.add_node("memory", memory_node)

    # Entry point is the router
    workflow.set_entry_point("router")
    workflow.add_conditional_edges("router", route_from_router)

    workflow.add_edge("planner", "evaluator")
    workflow.add_edge("developer", "evaluator")
    workflow.add_edge("executor", "evaluator")
    workflow.add_edge("research", "evaluator")

    # Evaluator → memory (on pass) or END (on timeout/fail)
    workflow.add_conditional_edges(
        "evaluator",
        route_from_evaluator,
        {"memory": "memory", END: END},
    )

    # Memory is always a terminal node — it writes facts then exits
    workflow.add_edge("memory", END)

    qdrant_saver = QdrantCheckpointer()
    return workflow.compile(checkpointer=qdrant_saver)


system_agent = build_system_graph()
