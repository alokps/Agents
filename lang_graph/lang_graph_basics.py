from typing import Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import gradio as gr
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from helper_utils import base_url, api_key

model = ChatOpenAI(
    model="gpt-5-mini",
    openai_api_base=base_url,
    openai_api_key=api_key,
    temperature=0,
)


class State(BaseModel):
    messages: Annotated[list, add_messages]


# Step 2: Start the Graph Builder with this State class
graph_builder = StateGraph(State)


def chatbot_node(old_state: State) -> State:
    response = model.invoke(old_state.messages)
    new_state = State(messages=[response])
    return new_state


graph_builder.add_node("chatbot", chatbot_node)


# Step 4: Create Edges
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)

# Step 5: Compile the Graph
graph = graph_builder.compile()


def chat(user_input: str, history):
    initial_state = State(messages=[{"role": "user", "content": user_input}])
    result = graph.invoke(initial_state)
    print(result)
    return result["messages"][-1].content


gr.ChatInterface(chat).launch(server_name="0.0.0.0", server_port=7869)
