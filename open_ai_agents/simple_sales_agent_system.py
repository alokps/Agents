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
    input_guardrail,
    GuardrailFunctionOutput,
)
from agents.exceptions import InputGuardrailTripwireTriggered
from openai.types.responses import ResponseTextDeltaEvent
from openai import AsyncOpenAI
import sendgrid
import os
from pydantic import BaseModel
from sendgrid.helpers.mail import Mail, Email, To, Content
from helper_utils import base_url, api_key
from typing import List

import asyncio
import aiofiles

# Load environment variables from .env file
load_dotenv(override=True)

current_model_name = "gpt-5-mini"

def send_test_email(
    subject: str, content: str, content_type: str = "text/plain"
) -> int:
    sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
    from_email = Email(os.getenv("FROM_EMAIL"))
    to_email = To(os.getenv("TO_EMAIL"))
    content = Content(content_type, content)
    mail = Mail(from_email, to_email, subject, content).get()
    response = sg.client.mail.send.post(request_body=mail)
    return response.status_code


@function_tool
def send_email() -> int:
    return send_test_email(
        "Send plain Sales Email",
        "This is a Plain sales email sent to clients.",
    )


@function_tool
def send_html_email() -> int:
    return send_test_email(
        "Send Html Sales Email",
        "This is a Html sales email sent to clients.",
        content_type="text/html",
    )


set_tracing_disabled(disabled=True)


class NameCheckOutput(BaseModel):
    is_name_in_message: bool
    name: str


class CustomModelProvider(ModelProvider):
    global current_model_name

    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(
            model=current_model_name,
            openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key),
        )


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
        self._subject_instructions = "You can write a subject for a cold sales email. \
You are given a message and you need to write a subject for an email that is likely to get a response."
        self._html_email_instructions = "You can convert a text email body to an HTML email body. \
You are given a text email body which might have some markdown \
and you need to convert it to an HTML email body with simple, clear, compelling layout and design."
        self._email_formatter_instructions = "You are an email formatter and sender. You receive the body of an email to be sent. \
You first use the subject_writer tool to write a subject for the email, then use the html_converter tool to convert the body to HTML. \
Finally, you use the send_html_email tool to send the email with the subject and HTML body."

        self._email_output = []
        self._best_email_output = ""
        self._tools = []

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
        self._subject_writer = Agent(
            name="subject_writer", instructions=self._subject_instructions
        )
        self._html_email_converter = Agent(
            name="html_email_converter", instructions=self._html_email_instructions
        )
        self._guardrail_agent = Agent(
            name="Agent which checks for name presence in message",
            instructions="Check if the user is including someone's personal name in what they want you to do.",
            output_type=NameCheckOutput,
        )
        
        # Create the guardrail function as an instance attribute
        @input_guardrail
        async def guardrail_against_names_in_message(
            ctx, agent, input
        ) -> GuardrailFunctionOutput:
            result = await Runner.run(
                starting_agent=self._guardrail_agent,
                input=input,
                run_config=RunConfig(model_provider=CustomModelProvider()),
                context=ctx.context,
            )
            # result.final_output is already a NameCheckOutput object, not JSON
            is_name_in_message = result.final_output.is_name_in_message
            return GuardrailFunctionOutput(
                output_info={"found_name": str(result.final_output)},
                tripwire_triggered=is_name_in_message)
        
        self.guardrail_against_names_in_message = guardrail_against_names_in_message

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

    def add_tools(self, run_config: RunConfig) -> str:
        self._tools.extend(
            [
                self._subject_writer.as_tool(
                    tool_name="subject_writer",
                    tool_description="Writes a subject for a cold sales email given the email body.",
                    run_config=run_config,
                ),
                self._html_email_converter.as_tool(
                    tool_name="html_email_converter",
                    tool_description="Converts a text email body to an HTML email body.",
                    run_config=run_config,
                ),
                send_html_email,
            ]
        )
        self._email_agent = Agent(
            name="email_formatter_sender",
            instructions=self._email_formatter_instructions,
            tools=self._tools,
            handoff_description="Formats and sends the email using the provided tools.",
        )


class SalesManager:
    def __init__(self, with_handsoff: bool = False):
        self.with_handsoff = with_handsoff
        self.tools = []
        self.handsoff = []
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
        self._sales_manager_handoff_instructions = """
You are a Sales Manager at ComplAI. Your goal is to find the single best cold sales email using the sales_agent tools.
 
Follow these steps carefully:
1. Generate Drafts: Use all three sales_agent tools to generate three different email drafts. Do not proceed until all three drafts are ready.
 
2. Evaluate and Select: Review the drafts and choose the single best email using your judgment of which one is most effective.
You can use the tools multiple times if you're not satisfied with the results from the first try.
 
3. Handoff for Sending: Pass ONLY the winning email draft to the 'Email Manager' agent. The Email Manager will take care of formatting and sending.
 
Crucial Rules:
- You must use the sales agent tools to generate the drafts — do not write them yourself.
- You must hand off exactly ONE email to the Email Manager — never more than one.
"""
        self._sales_manager_agent = Agent(
            name="Sales Manager Agent",
            instructions=self._sales_manager_instructions,
            tools=self.tools,
        )
        self._sales_manager_handoff_agent = Agent(
            name="Sales Manager Handoff Agent",
            instructions=self._sales_manager_handoff_instructions,
            tools=self.tools,
            handoffs=self.handsoff,
        )

    async def run_manager(self, input: str, run_config: RunConfig):
        result = await Runner.run(
            starting_agent=self._sales_manager_agent,
            input=input,
            run_config=run_config,
        )
        async with aiofiles.open(
            "outputs/sales_manager_tools_outputs.txt", "w", encoding="utf-8"
        ) as f:
            await f.write(result.final_output + "\n\n")
            print("\n\nOutput is placed in outputs/sales_manager_tools_outputs.txt\n\n")

    async def run_handoff_manager(
        self, input: str, run_config: RunConfig, tools: List, handoffs: List, guardrails: List
    ):
        self.tools = tools
        self.handsoff = handoffs
        print(f"If this input: \n{input}\n contains a name , the guardrail will be triggered.")
        self._sales_manager_handoff_agent.input_guardrails = guardrails
        result = await Runner.run(
            starting_agent=self._sales_manager_handoff_agent,
            input=input,
            run_config=run_config,
        )
        async with aiofiles.open(
            "outputs/sales_manager_handoff_outputs.txt", "w", encoding="utf-8"
        ) as f:
            await f.write(result.final_output + "\n\n")
            print(
                "\n\nOutput is placed in outputs/sales_manager_handoff_outputs.txt\n\n"
            )


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
    current_model_name = (
        input(
            "Enter the model name to use from the following options (default: gpt-5-mini):\
gpt-5-mini, claude-sonnet-4-5, gemini-2.5-pro: "
        )
        .strip()
        .lower()
    )
    current_model_name = str(current_model_name)
    if not current_model_name:
        current_model_name = "gpt-5-mini"
    print(f"Using model: {current_model_name}")
    handsoff_flag = (
        input("Do you want to run the Sales Manager with handsoff? (yes/no): ")
        .strip()
        .lower()
    )
    sales_agent_system = SimpleSalesAgentSystem()
    sales_manager = SalesManager(with_handsoff=(handsoff_flag == "yes"))
    description = "Write a cold sales email"
    message = "Send a cold sales email addressed to 'Dear CEO'"
    if not sales_manager.with_handsoff:
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
        asyncio.run(
            sales_manager.run_manager(
                input=message,
                run_config=sales_agent_system._run_config,
            )
        )
    else:
        sales_manager.tools = sales_agent_system._sales_workflow.add_tools(
            run_config=sales_agent_system._run_config
        )
        sales_manager.handsoff = [sales_agent_system._sales_workflow._email_agent]
        # This message includes a name to trigger the guardrail
        message_with_name = (
            "Send out a cold sales email addressed to Dear CEO from Alice"
        )
        try:
            asyncio.run(
                sales_manager.run_handoff_manager(
                    input=message,
                    run_config=sales_agent_system._run_config,
                    tools=sales_manager.tools,
                    handoffs=sales_manager.handsoff,
                    guardrails=[sales_agent_system._sales_workflow.guardrail_against_names_in_message],
                )
            )
        except InputGuardrailTripwireTriggered as e:
            print(f"Guardrail triggered: {e.guardrail_result.output}")
        
