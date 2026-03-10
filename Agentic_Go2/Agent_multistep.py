import time
from typing import Annotated, List, TypedDict, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from dotenv import load_dotenv
load_dotenv()

from ros2_motion import RosMotionController
motion = RosMotionController(cmd_vel_topic="/cmd_vel")
motion.start()

# Tools
@tool
def walk(duration_s: float = 1.0, speed_mps: float = 0.3) -> str:
    """Make the robot walk for duration_s seconds at speed_mps m/s. Speed is postive when walking forwards, and negtive when walking backwards"""
    motion.walk(duration_s=duration_s, speed_mps=speed_mps)
    return f"Walked for {duration_s}s at {speed_mps} m/s."

@tool
def turn_in_place(duration_s: float = 1.0, angular_z: float = 0.8) -> str:
    """Turn in place for duration_s seconds with angular velocity angular_z rad/s. +CCW, -CW."""
    motion.turn_in_place(duration_s=duration_s, angular_z=angular_z)
    direction = "CCW" if angular_z >= 0 else "CW"
    return f"Turned {direction} for {duration_s}s at {angular_z} rad/s."

tools = [walk, turn_in_place]
TOOLS_BY_NAME = {t.name: t for t in tools}

# Planner schema
class Step(BaseModel):
    action: Literal["walk", "turn_in_place"]
    duration_s: float = Field(default=1.0, ge=0.0)
    speed_mps: Optional[float] = None
    angular_z: Optional[float] = None

class Plan(BaseModel):
    steps: List[Step]


# State
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    plan: Optional[Plan]
    step_idx: int

# LLMs
planner_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(Plan)
executor_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools)

# Debug helpers
def print_plan(plan: Plan):
    print("\n PLAN:")
    for i, st in enumerate(plan.steps, start=1):
        print(f"  {i}. {st.model_dump()}")

def print_step(step_idx: int, step: Step):
    print(f"\n  STEP {step_idx+1}: {step.model_dump()}")

def print_tool_call(name: str, args: Dict[str, Any]):
    print(f" TOOL CALL: {name}({args})")

def print_tool_result(name: str, result: str):
    print(f" TOOL RESULT ({name}): {result}")

# Nodes
def plan_node(state: AgentState):
    system = SystemMessage(content=(
        "You are a motion planning assistant for a ROS2-controlled robot.\n"
        "Convert the user's request into a short sequence of steps using ONLY:\n"
        "- walk(duration_s, speed_mps)\n"
        "- turn_in_place(duration_s, angular_z)\n"
        "Use angular_z < 0 for right turn, > 0 for left turn.\n"
        "Prefer 0.3 m/s and 0.8 rad/s if user doesn't specify.\n"
    ))
    plan = planner_llm.invoke([system] + state["messages"])

    return {"plan": plan, "step_idx": 0}

def execute_step_node(state: AgentState):
    """Ask the model to execute exactly one step by calling the right tool."""
    assert state["plan"] is not None
    idx = state["step_idx"]

    if idx >= len(state["plan"].steps):
        return {}

    step = state["plan"].steps[idx]
    print_step(idx, step)

    system = SystemMessage(content=(
        "You are executing ONE step of a robot motion plan.\n"
        "Call exactly one tool corresponding to the step. Do not add extra steps."
    ))
    user = HumanMessage(content=f"Execute step: {step.model_dump()}")

    response = executor_llm.invoke([system, user])

    # Print what the model requested (tool calls) if present
    tcalls = getattr(response, "tool_calls", None) or []
    if tcalls:
        for tc in tcalls:
            print_tool_call(tc["name"], tc.get("args", {}))

    return {"messages": [response]}

def run_tools_node(state: AgentState):
    """Execute the tool calls from the last assistant message, printing calls + results."""
    if not state["messages"]:
        return {}

    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    if not tool_calls:
        return {}

    new_msgs: List[BaseMessage] = []

    for tc in tool_calls:
        name = tc["name"]
        args = tc.get("args", {}) or {}
        call_id = tc.get("id")

        tool_obj = TOOLS_BY_NAME.get(name)
        if tool_obj is None:
            result = f"ERROR: Unknown tool '{name}'"
            print_tool_result(name, result)
            new_msgs.append(ToolMessage(content=result, tool_call_id=call_id))
            continue

        # Actually run the tool
        try:
            result = tool_obj.invoke(args)
        except Exception as e:
            result = f"ERROR running {name}: {e}"

        # Print + append ToolMessage (this is what lets the model continue)
        print_tool_result(name, str(result))
        new_msgs.append(ToolMessage(content=str(result), tool_call_id=call_id))

    return {"messages": new_msgs}

def advance_node(state: AgentState):
    return {"step_idx": state["step_idx"] + 1}

def done_router(state: AgentState):
    if state["plan"] is None:
        return "plan"

    if state["step_idx"] >= len(state["plan"].steps):
        return END

    last = state["messages"][-1] if state["messages"] else None
    if last is not None and getattr(last, "tool_calls", None):
        return "tools"

    return "exec_step"

# Graph
builder = StateGraph(AgentState)

builder.add_node("plan", plan_node)
builder.add_node("exec_step", execute_step_node)
builder.add_node("tools", run_tools_node) 
builder.add_node("advance", advance_node)

builder.set_entry_point("plan")

builder.add_conditional_edges(
    "plan",
    lambda s: "exec_step",
    {"exec_step": "exec_step"},
)

builder.add_conditional_edges(
    "exec_step",
    done_router,
    {
        "tools": "tools",
        "exec_step": "exec_step",
        "plan": "plan",
        END: END,
    }
)

builder.add_edge("tools", "advance")
builder.add_edge("advance", "exec_step")

graph = builder.compile()


# Run loop (prints incremental messages too)
if __name__ == "__main__":
    print("Planner+Executor ready! Type 'exit' to quit.\n")
    state: AgentState = {"messages": [], "plan": None, "step_idx": 0}
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break

        # Track how many messages existed pre-run so we can print only the new ones
        before = len(state["messages"])

        state["messages"].append(HumanMessage(content=user_input))
        state["plan"] = None
        state["step_idx"] = 0

        state = graph.invoke(state)

        # Print any final assistant message content (if it produced one)
        new_messages = state["messages"][before:]
        for m in new_messages:
            # Skip ToolMessages (we already printed tool results)
            if isinstance(m, ToolMessage):
                continue
            content = getattr(m, "content", None)
            if content:
                print("\nAgent:", content)