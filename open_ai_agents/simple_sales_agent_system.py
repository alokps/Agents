from dotenv import load_dotenv
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
from openai.types.responses import ResponseTextDeltaEvent
from openai import AsyncOpenAI
import sendgrid
import os
from sendgrid.helpers.mail import Mail, Email, To, Content
from helper_utils import base_url, api_key

import asyncio
import aiofiles

# Load environment variables from .env file
load_dotenv(override=True)


def send_test_email(subject: str, content: str) -> int:
    sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
    from_email = Email(os.getenv("FROM_EMAIL"))
    to_email = To(os.getenv("TO_EMAIL"))
    content = Content("text/plain", content)
    mail = Mail(from_email, to_email, subject, content).get()
    response = sg.client.mail.send.post(request_body=mail)
    return response.status_code


@function_tool
def send_email() -> int:
    return send_test_email(
        "Send Sales Email",
        "This is a sales email sent to clients.",
    )


set_tracing_disabled(disabled=True)


class CustomModelProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(
            model="gpt-5-mini",
            openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key),
        )


model_provider = CustomModelProvider()


class SalesAgentWorkflow:
    def __init__(self):
        self._sales_agent_1_instructions = "You are a sales agent working for ComplAI, \
a company that provides a SaaS tool for ensuring SOC2 compliance and preparing for audits, powered by AI. \
You write professional, serious cold emails."
        self._sales_agent_2_instructions = "You are a humorous, engaging sales agent working for ComplAI, \
a company that provides a SaaS tool for ensuring SOC2 compliance and preparing for audits, powered by AI. \
You write witty, engaging cold emails that are likely to get a response."
        self._sales_agent_3_instructions = "You are a busy sales agent working for ComplAI, \
a company that provides a SaaS tool for ensuring SOC2 compliance and preparing for audits, powered by AI. \
You write concise, to the point cold emails."
        self._sales_email_picker_instructions = "You pick the best cold sales email from the given options. \
Imagine you are a customer and pick the one you are most likely to respond to. \
Do not give an explanation; reply with the selected email only."
        self._email_output = []
        self._best_email_output = ""

        self._sales_agent_1 = Agent(
            name="professional_sales_agent",
            instructions=self._sales_agent_1_instructions,
        )
        self._sales_agent_2 = Agent(
            name="humorous_sales_agent", instructions=self._sales_agent_2_instructions
        )
        self._sales_agent_3 = Agent(
            name="concise_sales_agent", instructions=self._sales_agent_3_instructions
        )
        self._sales_email_picker = Agent(
            name="sales_email_picker",
            instructions=self._sales_email_picker_instructions,
        )

    async def run_single_agent(
        self, agent: Agent, input: str, run_config: RunConfig
    ) -> str:
        result = Runner.run_streamed(
            starting_agent=agent, input=input, run_config=run_config
        )
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(
                event.data, ResponseTextDeltaEvent
            ):
                print(event.data.delta, end="", flush=True)

    async def run_all_agents(self, input: str, run_config: RunConfig):
        results = await asyncio.gather(
            Runner.run(self._sales_agent_1, input, run_config=run_config),
            Runner.run(self._sales_agent_2, input, run_config=run_config),
            Runner.run(self._sales_agent_3, input, run_config=run_config),
        )

        outputs = [result.final_output for result in results]

        self._email_output.extend(outputs)

        async with aiofiles.open(
            "outputs/sales_agent_outputs.txt", "w", encoding="utf-8"
        ) as f:
            for output in outputs:
                await f.write(output + "\n\n")

    async def best_email_picker(self, run_config: RunConfig) -> str:
        emails = "Cold sales emails:\n\n" + "\n\nEmail:\n\n".join(self._email_output)
        best_email_result = await Runner.run(
            starting_agent=self._sales_email_picker,
            input=emails,
            run_config=run_config,
        )
        self._best_email_output = best_email_result.final_output
        print(f"\n\nBest Sales Email:\n\n{best_email_result.final_output}")


class SalesManager:
    def __init__(self):
        self.tools = []
        self._sales_manager_instructions = """
You are a Sales Manager at ComplAI. Your goal is to find the single best cold sales email using the sales_agent tools.
 
Follow these steps carefully:
1. Generate Drafts: Use all three sales_agent tools to generate three different email drafts. Do not proceed until all three drafts are ready.
 
2. Evaluate and Select: Review the drafts and choose the single best email using your judgment of which one is most effective.
 
3. Use the send_email tool to send the best email (and only the best email) to the user.
 
Crucial Rules:
- You must use the sales agent tools to generate the drafts — do not write them yourself.
- You must send ONE email using the send_email tool — never more than one.
"""
        self._sales_manager_agent = Agent(
            name="Sales Manager Agent",
            instructions=self._sales_manager_instructions,
            tools=self.tools,
        )

    async def run_manager(self, input: str, run_config: RunConfig):
        result = await Runner.run(
            starting_agent=self._sales_manager_agent,
            input=input,
            run_config=run_config,
        )
        print(f"\n\nSales Manager Result:\n\n{result.final_output}")


class SimpleSalesAgentSystem:
    def __init__(self):
        set_tracing_disabled(disabled=True)
        self._model_provider = CustomModelProvider()
        self._run_config = RunConfig(model_provider=self._model_provider)
        self._sales_workflow = SalesAgentWorkflow()
        if not self.check_sendgrid_client():
            raise RuntimeError("SendGrid client is not configured properly.")

    def check_sendgrid_client(self) -> bool:
        status_code = send_test_email(
            "Check SendGrid Client",
            "This email checks if the SendGrid client is working.",
        )
        return 202 == status_code

    async def run_sales_agent_workflow(self):
        sales_input = "Generate a cold email to a CTO of a mid-sized tech company about ComplAI's SOC2 compliance tool."
        print("\n--- Running Professional Sales Agent ---\n")
        await self._sales_workflow.run_single_agent(
            agent=self._sales_workflow._sales_agent_1,
            input=sales_input,
            run_config=self._run_config,
        )

    async def run_all_sales_agents(self):
        sales_input = "Generate a cold email to a CTO of a mid-sized tech company about ComplAI's SOC2 compliance tool."
        print("\n--- Running All Sales Agents ---\n")
        await self._sales_workflow.run_all_agents(
            input=sales_input, run_config=self._run_config
        )

    async def pick_best_email(self):
        await self.run_all_sales_agents()
        print("\n--- Picking Best Sales Email ---\n")
        await self._sales_workflow.best_email_picker(run_config=self._run_config)


if __name__ == "__main__":
    sales_agent_system = SimpleSalesAgentSystem()
    sales_manager = SalesManager()
    description = "Write a cold sales email"
    sales_manager.tools.extend(
        [
            sales_agent_system._sales_workflow._sales_agent_1.as_tool(
                tool_name="professional_sales_agent",
                tool_description=description,
                run_config=sales_agent_system._run_config,
            ),
            sales_agent_system._sales_workflow._sales_agent_2.as_tool(
                tool_name="humorous_sales_agent",
                tool_description=description,
                run_config=sales_agent_system._run_config,
            ),
            sales_agent_system._sales_workflow._sales_agent_3.as_tool(
                tool_name="concise_sales_agent",
                tool_description=description,
                run_config=sales_agent_system._run_config,
            ),
            send_email,
        ]
    )
    message = "Send a cold sales email addressed to 'Dear CEO'"
    asyncio.run(
        sales_manager.run_manager(
            input=message,
            run_config=sales_agent_system._run_config,
        )
    )
