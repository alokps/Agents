from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from helper_utils import base_url, api_key
from langchain.tools import tool
from langchain.messages import (
    SystemMessage,
    HumanMessage,
    ToolCall,
    AIMessage,
)
from langchain_core.messages import BaseMessage
from langgraph.func import entrypoint, task

# Step 1: Define tools and model


model = ChatOpenAI(
    model="gpt-5-mini",
    openai_api_base=base_url,
    openai_api_key=api_key,
    temperature=0,
)


# Define tools
@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a * b


@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a + b


@tool
def divide(a: int, b: int) -> float:
    """Divide `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a / b


# Augment the LLM with tools
tools = [add, multiply, divide]
tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)


# Step 2: Define model node
@task
def call_llm(messages: list[BaseMessage]):
    """LLM decides whether to call a tool or not"""
    return model_with_tools.invoke(
        [
            SystemMessage(
                content="You are a helpful assistant tasked with performing arithmetic on a set of inputs."
            )
        ]
        + messages
    )


# Step 3: Define tool node
@task
def call_tool(tool_call: ToolCall):
    """Performs the tool call"""
    tool = tools_by_name[tool_call["name"]]
    return tool.invoke(tool_call)


# Step 4: Define agent
@entrypoint()
def agent(messages: list[BaseMessage]):
    model_response = call_llm(messages).result()

    while True:
        if not model_response.tool_calls:
            break

        # Execute tools
        tool_result_futures = [
            call_tool(tool_call) for tool_call in model_response.tool_calls
        ]
        tool_results = [fut.result() for fut in tool_result_futures]
        messages = add_messages(messages, [model_response, *tool_results])
        model_response = call_llm(messages).result()

    messages = add_messages(messages, model_response)
    return messages


# Invoke and print in a human-readable way
if __name__ == "__main__":
    messages = [
        HumanMessage(content="Get the Average of sum of all prime number from 1 to 50.")
    ]

    # Run the agent once and get the full conversation
    conversation = agent.invoke(messages)

    print("Conversation:")
    for msg in conversation:
        if isinstance(msg, HumanMessage):
            role = "User"
        elif isinstance(msg, AIMessage):
            role = "Assistant"
        else:
            role = msg.__class__.__name__

        print(f"{role}: {msg.content}")
