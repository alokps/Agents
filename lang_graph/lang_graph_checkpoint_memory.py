from typing import Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import Tool
from dotenv import load_dotenv
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver


from helper_utils import base_url, api_key
import requests
import os

from typing import TypedDict

# Load environment variables from .env file
load_dotenv(override=True)

# LangChain Wrapper class for converting functions into Tools
search_tool = Tool(
    name="search",
    func=GoogleSerperAPIWrapper().run,
    description="Useful for when you need to look up current information on the internet.",
)

# Creating a Custom Tool
pushover_token = os.getenv("PUSHOVER_API_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER_KEY")
pushover_url = "https://api.pushover.net/1/messages.json"


def push(text: str) -> str:
    """Sends a push notification using Pushover.

    Args:
        text: The message to send.

    Returns:
        A confirmation string.
    """
    data = {
        "token": pushover_token,
        "user": pushover_user,
        "message": text,
    }
    response = requests.post(pushover_url, data=data)
    if response.status_code == 200:
        return "Push notification sent successfully."
    else:
        return f"Failed to send push notification. Status code: {response.status_code}"


push_tool = Tool(
    name="push_notification",
    func=push,
    description="Sends a push notification to the user's device.",
)

agent_tools = [search_tool, push_tool]


# Step 1: Define the State Object
class State(TypedDict):
    messages: Annotated[list[dict], add_messages]


# Step 2: start the graph builder with this State Class
graph_builder = StateGraph(State)

# Create the Model
model = ChatOpenAI(
    model="gpt-5-mini",
    openai_api_base=base_url,
    openai_api_key=api_key,
    temperature=0,
)

# Add the tools to the model
model_with_tools = model.bind_tools(agent_tools)


# Step 3: Create a Node
def chatbot_node(state: State) -> State:
    return {"messages": [model_with_tools.invoke(state["messages"])]}


graph_builder.add_node("chatbot", chatbot_node)
graph_builder.add_node("agent_tools", ToolNode(tools=agent_tools))

# Step 4: Create Edges
graph_builder.add_conditional_edges(
    "chatbot", tools_condition, {"tools": "agent_tools", "__end__": END}
)

# Any time a tool is called, we return to the chatbot to decide the next step
graph_builder.add_edge("agent_tools", "chatbot")
graph_builder.add_edge(START, "chatbot")

# Compile the graph with Memory Saver
# graph = graph_builder.compile(checkpointer=MemorySaver())
# Connect to a SQLite database for checkpointing
db_path = "langgraph_checkpoint_memory.db"
# Remove existing database to start fresh
if os.path.exists(db_path):
    os.remove(db_path)
conn = sqlite3.connect(db_path, check_same_thread=False)
sql_memory = SqliteSaver(conn)
graph = graph_builder.compile(checkpointer=sql_memory)

# Configuration
config = {"configurable": {"thread_id": "3"}}

# Test the chatbot
if __name__ == "__main__":
    # Create output directory
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Open output file for writing
    output_file = os.path.join(output_dir, "chatbot_output.txt")
    with open(output_file, "w") as f:
        f.write("Testing LangGraph Chatbot with SQLite Checkpointing\n\n")

        # Test message 1
        user_input = "What is the weather in San Francisco?"
        f.write(f"User: {user_input}\n")
        result = graph.invoke(
            {"messages": [{"role": "user", "content": user_input}]}, config=config
        )
        f.write(f"Assistant: {result['messages'][-1].content}\n\n")

        # Test message 2
        user_input2 = "Can you send me a notification?"
        f.write(f"User: {user_input2}\n")
        result = graph.invoke(
            {"messages": [{"role": "user", "content": user_input2}]}, config=config
        )
        f.write(f"Assistant: {result['messages'][-1].content}\n\n")

        # Check state history
        f.write("State History:\n")
        f.write("=" * 80 + "\n")
        for i, state in enumerate(graph.get_state_history(config=config), 1):
            f.write(f"\nState {i}:\n")
            f.write(
                f"  Checkpoint ID: {state.config['configurable']['checkpoint_id']}\n"
            )
            f.write(f"  Messages: {len(state.values.get('messages', []))}\n")
            for j, msg in enumerate(state.values.get("messages", []), 1):
                role = getattr(msg, "type", "unknown")
                content = getattr(msg, "content", "")
                f.write(
                    f"    Message {j} [{role}]: {content[:100]}{'...' if len(str(content)) > 100 else ''}\n"
                )
            f.write("-" * 80 + "\n")

    print(f"Output written to {output_file}")
