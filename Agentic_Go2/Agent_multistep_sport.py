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
    """Make the robot walk"""
    motion.walk(duration_s=duration_s, speed_mps=speed_mps)
    return f"Walked for {duration_s}s at {speed_mps} m/s."

@tool
def turn_in_place(duration_s: float = 1.0, angular_z: float = 0.8) -> str:
    """Turn in place"""
    motion.turn_in_place(duration_s=duration_s, angular_z=angular_z)
    direction = "CCW" if angular_z >= 0 else "CW"
    return f"Turned {direction} for {duration_s}s at {angular_z} rad/s."

@tool
def sit(duration_s: float = 3.0) -> str:
    """Make the robot sit down for duration_s seconds, then stand back up."""
    motion.sit(duration_s=duration_s)
    return f"Sat for {duration_s}s."

@tool
def stretch(duration_s: float = 3.0) -> str:
    """Make the robot stretch for duration_s seconds."""
    motion.stretch(duration_s=duration_s)
    return f"Stretched for {duration_s}s."

@tool
def stand_up() -> str:
    """Make the robot stand up."""
    motion.stand_up()
    return "Stood up."

@tool
def stand_down() -> str:
    """Make the robot lower into a resting stance."""
    motion.stand_down()
    return "Stood down."

@tool
def recovery_stand() -> str:
    """Make the robot recover to a normal standing position from any pose."""
    motion.recovery_stand()
    return "Recovery stand complete."

tools = [walk, turn_in_place, sit, stretch, stand_up, stand_down, recovery_stand]
TOOLS_BY_NAME = {t.name: t for t in tools}

# Planner schema
class Step(BaseModel):
    action: Literal["walk", "turn_in_place", "sit", "stretch", "stand_up", "stand_down", "recovery_stand"]
    duration_s: Optional[float] = Field(default=None, ge=0.0)

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
announce_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

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
        "You are a motion planner for a ROS2 robot.\n"
        "Return a plan using ONLY these actions:\n"
        "- walk(duration_s, speed_mps)\n"
        "- turn_in_place(duration_s, angular_z)\n"
        "- sit(duration_s)\n"
        "- stretch(duration_s)\n"
        "- stand_up()\n"
        "- stand_down()\n"
        "- recovery_stand()\n\n"
        "Rules:\n"
        "1. Only include actions needed to satisfy the request.\n"
        "2. Do not invent actions.\n"
        "3. If the user does not specify parameters, use sensible defaults.\n"
        "4. Keep the plan short.\n"
        "5. For conversation-only requests like 'hi', return an empty plan.\n"
    ))
    plan = planner_llm.invoke([system] + state["messages"])
    print_plan(plan)
    return {"plan": plan, "step_idx": 0}

def announce_node(state: AgentState):
    system = SystemMessage(content=(
        "You are a robot assistant. Announce in 1 sentence what you did "
        "based on the plan."
    ))
    response = announce_llm.invoke([system] + state["messages"])
    announcement = response.content
    print(f"\nAgent: {announcement}")
    motion.say(announcement)
    time.sleep(4.0)
    return {}

def execute_step_node(state: AgentState):
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

    tcalls = getattr(response, "tool_calls", None) or []
    if tcalls:
        for tc in tcalls:
            print_tool_call(tc["name"], tc.get("args", {}))

    return {"messages": [response]}

def run_tools_node(state: AgentState):
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

        try:
            result = tool_obj.invoke(args)
        except Exception as e:
            result = f"ERROR running {name}: {e}"

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
builder.add_node("announce", announce_node)
builder.add_node("exec_step", execute_step_node)
builder.add_node("tools", run_tools_node)
builder.add_node("advance", advance_node)

builder.set_entry_point("plan")

builder.add_conditional_edges(
    "plan",
    lambda s: "announce",
    {"announce": "announce"},
)

builder.add_edge("announce", "exec_step")

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

# Run loop
if __name__ == "__main__":
    print("Planner+Executor ready! Type 'exit' to quit.\n")
    state: AgentState = {"messages": [], "plan": None, "step_idx": 0}

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break

        before = len(state["messages"])

        state["messages"].append(HumanMessage(content=user_input))
        state["plan"] = None
        state["step_idx"] = 0

        state = graph.invoke(state)

        new_messages = state["messages"][before:]
        for m in new_messages:
            if isinstance(m, ToolMessage):
                continue
            content = getattr(m, "content", None)
            if content:
                print("\nAgent:", content)