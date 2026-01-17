from dotenv import load_dotenv
from agents import (
    Agent,
    Runner,
    ModelProvider,
    Model,
    RunConfig,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
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
        self._sales_agent_1 = Agent(
            name="Professional Sales Agent",
            instructions=self._sales_agent_1_instructions,
        )
        self._sales_agent_2 = Agent(
            name="Humorous Sales Agent", instructions=self._sales_agent_2_instructions
        )
        self._sales_agent_3 = Agent(
            name="Concise Sales Agent", instructions=self._sales_agent_3_instructions
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

        async with aiofiles.open(
            "outputs/sales_agent_outputs.txt", "w", encoding="utf-8"
        ) as f:
            for output in outputs:
                await f.write(output + "\n\n")


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


if __name__ == "__main__":
    sales_agent_system = SimpleSalesAgentSystem()
    asyncio.run(sales_agent_system.run_all_sales_agents())
