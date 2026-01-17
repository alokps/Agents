from agents import (
    Agent,
    Runner,
    ModelProvider,
    Model,
    RunConfig,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
    function_tool,
)
from openai import AsyncOpenAI
from helper_utils import base_url, api_key
import asyncio

# Disable tracing for cleaner output
set_tracing_disabled(disabled=True)


class CustomModelProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(
            model=model_name or "gpt-5-mini",
            openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key),
        )


# Adding a Tool
@function_tool
def greetings(message: str) -> str:
    """Add a greeting message ."""
    # In a real implementation, this might generate a random greetings.
    return f"Howdy there {message}"


# Create an agent with the tool
greeting_agent = Agent(
    name="Greeter",
    instructions="You are a friendly greeter, you provide unique greetings.",
    tools=[greetings],
)


async def main():
    result = await Runner.run(
        starting_agent=greeting_agent,
        input="Generate a greeting for John",
        run_config=RunConfig(model_provider=CustomModelProvider()),
    )
    print("Agent Result:", result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
