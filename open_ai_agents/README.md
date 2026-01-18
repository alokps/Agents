# OpenAI Agents - Sales Agent System

A sophisticated multi-agent system built with OpenAI's Agents SDK that demonstrates advanced agent orchestration, parallel execution, input guardrails, structured outputs, and tool integration for automated sales email generation and management.

## Overview

This project showcases a production-ready implementation of an AI-powered sales email system that leverages multiple specialized agents working in concert to generate, evaluate, and send compelling cold sales emails for ComplAI, a SOC2 compliance SaaS platform. The system features advanced capabilities including input validation through guardrails, structured output parsing, multi-model support, and comprehensive error handling.

## Architecture

### Core Components

#### 1. **SimpleSalesAgentSystem** (`simple_sales_agent_system.py`)
The main entry point that orchestrates the entire workflow, managing agent initialization, configuration, and execution. Includes interactive model selection supporting multiple LLM providers (GPT, Claude, Gemini).

#### 2. **SalesAgentWorkflow**
A comprehensive workflow system that manages multiple specialized sales agents, each with distinct writing styles:
- **Professional Sales Agent**: Generates formal, serious cold emails
- **Humorous Sales Agent**: Creates witty, engaging content with personality
- **Concise Sales Agent**: Produces brief, to-the-point messages
- **Guardrail Agent**: Validates user input for personal names using structured outputs

#### 3. **SalesManager**
An intelligent manager agent that coordinates the draft generation process, evaluates outputs, and handles email delivery through tools or handoffs. Supports input guardrails for content validation.

## Key Features

### 🚀 Parallel Execution with AsyncIO

The system leverages Python's `asyncio` library to achieve efficient parallel execution of multiple agents:

```python
async def run_all_agents(self, input: str, run_config: RunConfig):
    results = await asyncio.gather(
        Runner.run(self._sales_agent_1, input, run_config=run_config),
        Runner.run(self._sales_agent_2, input, run_config=run_config),
        Runner.run(self._sales_agent_3, input, run_config=run_config),
    )
```

**Benefits:**
- **Concurrent Processing**: All three sales agents generate emails simultaneously rather than sequentially
- **Reduced Latency**: Overall execution time is determined by the slowest agent, not the sum of all agents
- **Efficient Resource Utilization**: Maximizes throughput when making multiple LLM API calls
- **Asynchronous I/O**: Non-blocking file operations using `aiofiles` for writing outputs

### 🛡️ Input Guardrails

The system implements intelligent input validation using the `@input_guardrail` decorator to prevent unauthorized content:

```python
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
    is_name_in_message = result.final_output.is_name_in_message
    return GuardrailFunctionOutput(
        output_info={"found_name": str(result.final_output)},
        tripwire_triggered=is_name_in_message
    )
```

**Key Features:**
- **Agent-Based Validation**: Uses a dedicated guardrail agent with structured outputs to detect personal names
- **Tripwire Mechanism**: Automatically halts execution when policy violations are detected
- **Exception Handling**: Gracefully catches `InputGuardrailTripwireTriggered` exceptions
- **Context-Aware**: Validates input before agent execution begins
- **Structured Output Parsing**: Uses Pydantic models for type-safe validation results

### 📊 Structured Outputs

The system uses Pydantic models for type-safe, structured agent responses:

```python
class NameCheckOutput(BaseModel):
    is_name_in_message: bool
    name: str

guardrail_agent = Agent(
    name="Agent which checks for name presence in message",
    instructions="Check if the user is including someone's personal name...",
    output_type=NameCheckOutput,
)
```

**Advantages:**
- **Type Safety**: Automatic validation and parsing of LLM responses
- **Schema Enforcement**: Ensures agents return data in expected formats
- **Easy Integration**: Direct access to structured fields (e.g., `result.final_output.is_name_in_message`)
- **Error Prevention**: Catches malformed outputs before they cause runtime errors

### 🛠️ Tool Integration

The system demonstrates sophisticated tool usage patterns that enable agents to perform external actions:

#### Function Tools
Custom tools wrapped with the `@function_tool` decorator:
- **send_email()**: Sends plain text emails via SendGrid API
- **send_html_email()**: Sends HTML-formatted emails with rich styling

#### Agent-as-Tool Pattern
Agents can be converted into tools that other agents can invoke:

```python
sales_agent_1.as_tool(
    tool_name="professional_sales_agent",
    tool_description="Write a cold sales email",
    run_config=run_config
)
```

**Use Cases:**
1. **Sales Manager Workflow**: Manager agent uses sales agents as tools to generate multiple draft options
2. **Nested Agent Execution**: Agents can orchestrate other agents programmatically
3. **Specialized Task Delegation**: Complex workflows broken into tool-callable sub-tasks

#### Composite Tool Chains
The Email Formatter agent demonstrates tool chaining:
```python
tools = [
    subject_writer.as_tool(...),      # Generates email subject
    html_converter.as_tool(...),       # Converts to HTML format
    send_html_email                    # Delivers the email
]
```

### 🔄 Agent Handoffs

The system supports two coordination patterns:

1. **Tool-Based Coordination**: Manager directly invokes tools to complete tasks
2. **Handoff-Based Coordination**: Manager delegates to specialized agents with guardrails:
   ```python
   async def run_handoff_manager(
       self, input: str, run_config: RunConfig, 
       tools: List, handoffs: List, guardrails: List
   ):
       self._sales_manager_handoff_agent.input_guardrails = guardrails
       result = await Runner.run(
           starting_agent=self._sales_manager_handoff_agent,
           input=input,
           run_config=run_config,
       )
   ```

### 🎯 Multi-Model Support

The system supports multiple LLM providers through interactive model selection:

```python
current_model_name = input(
    "Enter the model name to use from the following options (default: gpt-5-mini):"
    "gpt-5-mini, claude-sonnet-4-5, gemini-2.5-pro: "
)
```

**Supported Models:**
- **GPT Models**: `gpt-5-mini` (default)
- **Claude Models**: `claude-sonnet-4-5`
- **Gemini Models**: `gemini-2.5-pro`

The `CustomModelProvider` dynamically configures the appropriate model client based on user selection.

## Workflow Execution Modes

### Mode 1: Direct Tool Management
```python
with_handsoff=False
```
- Sales Manager uses sales agents as tools
- Directly invokes `send_email` tool
- Single-agent control flow

### Mode 2: Handoff Management (with Guardrails)
```python
with_handsoff=True
```
- Sales Manager evaluates drafts, then hands off to Email Manager
- **Input guardrails validate user requests** before processing
- Email Manager uses subject_writer, html_converter, and send_html_email tools
- Multi-agent collaborative workflow with security controls
- Exception handling for guardrail violations

**Guardrail Integration:**
```python
try:
    asyncio.run(
        sales_manager.run_handoff_manager(
            input=message,
            run_config=run_config,
            tools=tools,
            handoffs=handoffs,
            guardrails=[guardrail_against_names_in_message],
        )
    )
except InputGuardrailTripwireTriggered as e:
    print(f"Guardrail triggered: {e.guardrail_result.output}")
```

## Technical Implementation Details

### Custom Model Provider
Integrates with custom OpenAI-compatible endpoints and supports multiple model providers:
```python
class CustomModelProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(
            model=current_model_name,  # Dynamically set based on user selection
            openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key)
        )
```

**Features:**
- Dynamic model selection at runtime
- Support for custom API endpoints
- Token-based authentication with automatic refresh
- Compatible with OpenAI ChatCompletions API format

### Guardrail Implementation Pattern

The system uses a **closure-based approach** for guardrails to avoid `self` parameter issues:

```python
# Defined inside __init__ to capture self via closure
@input_guardrail
async def guardrail_against_names_in_message(ctx, agent, input):
    # Access instance variables through closure
    result = await Runner.run(
        starting_agent=self._guardrail_agent,
        input=input,
        run_config=RunConfig(model_provider=CustomModelProvider()),
        context=ctx.context,
    )
    return GuardrailFunctionOutput(...)

# Store as instance attribute
self.guardrail_against_names_in_message = guardrail_against_names_in_message
```

This pattern ensures proper function signature while maintaining access to instance variables.

### Structured Output Parsing

The system leverages Pydantic models with `output_type` for automatic JSON parsing:

```python
# Agent automatically returns structured output
guardrail_agent = Agent(
    name="guardrail_checker",
    output_type=NameCheckOutput,  # Pydantic model
)

result = await Runner.run(starting_agent=guardrail_agent, ...)
# result.final_output is already a NameCheckOutput object
is_valid = result.final_output.is_name_in_message
```

### Exception Handling

Comprehensive error handling for guardrail violations and operational errors:

```python
try:
    asyncio.run(sales_manager.run_handoff_manager(...))
except InputGuardrailTripwireTriggered as e:
    print(f"Guardrail triggered: {e.guardrail_result.output}")
```

### Streaming Support
Real-time output streaming for enhanced user experience:
```python
async for event in result.stream_events():
    if event.type == "raw_response_event":
        print(event.data.delta, end="", flush=True)
```

### File Output Management
Asynchronous file writing ensures non-blocking I/O:
```python
async with aiofiles.open("outputs/sales_agent_outputs.txt", "w") as f:
    await f.write(output + "\n\n")
```

## Configuration

### Environment Variables
```bash
SENDGRID_API_KEY=<your-sendgrid-key>
FROM_EMAIL=<sender-email>
TO_EMAIL=<recipient-email>
```

### Dependencies
- `agents`: OpenAI Agents SDK (with guardrails support)
- `asyncio`: Asynchronous programming
- `aiofiles`: Async file operations
- `sendgrid`: Email delivery
- `python-dotenv`: Environment management
- `pydantic`: Data validation and structured outputs
- `openai`: OpenAI Python client library

## Usage

### Interactive Execution

The system provides an interactive CLI for model selection and workflow mode:

```bash
uv run .\simple_sales_agent_system.py
```

**Prompts:**
1. **Model Selection**: Choose from gpt-5-mini, claude-sonnet-4-5, or gemini-2.5-pro
2. **Workflow Mode**: Select tool-based or handoff-based execution

### Programmatic Usage

```python
# Initialize the system with selected model
sales_agent_system = SimpleSalesAgentSystem()
sales_manager = SalesManager(with_handsoff=True)

# Configure tools and handoffs
sales_manager.tools = sales_agent_system._sales_workflow.add_tools(
    run_config=sales_agent_system._run_config
)
sales_manager.handsoff = [sales_agent_system._sales_workflow._email_agent]

# Execute with guardrails
message = "Send out a cold sales email addressed to Dear CEO"
try:
    asyncio.run(
        sales_manager.run_handoff_manager(
            input=message,
            run_config=sales_agent_system._run_config,
            tools=sales_manager.tools,
            handoffs=sales_manager.handsoff,
            guardrails=[
                sales_agent_system._sales_workflow.guardrail_against_names_in_message
            ],
        )
    )
except InputGuardrailTripwireTriggered as e:
    print(f"Input validation failed: {e.guardrail_result.output}")
```

## Output

Generated emails and execution logs are saved to:
- `outputs/sales_agent_outputs.txt`: All draft emails from parallel execution
- `outputs/sales_manager_tools_outputs.txt`: Final output from tool-based workflow
- `outputs/sales_manager_handoff_outputs.txt`: Final output from handoff-based workflow (with guardrails)

## Advanced Features

### Input Validation Pipeline
The guardrail system provides a multi-layered validation approach:

1. **Pre-Execution Validation**: Input checked before agent processing begins
2. **Agent-Based Analysis**: Dedicated guardrail agent performs intelligent content analysis
3. **Structured Decision**: Type-safe boolean result determines whether to proceed
4. **Graceful Failure**: Exceptions provide detailed information about policy violations

### Closure-Based Guardrails
A novel pattern that combines decorator syntax with instance methods:

```python
# Inside __init__ method
@input_guardrail
async def guardrail_fn(ctx, agent, input):
    # Access self through closure, avoiding self parameter issues
    result = await Runner.run(starting_agent=self._guardrail_agent, ...)
    
self.guardrail_fn = guardrail_fn  # Store as instance attribute
```

**Benefits:**
- No `self` parameter conflicts with SDK expectations
- Access to instance variables through closure
- Clean decorator syntax
- Proper async/await support

### Multi-Provider Architecture
The system's model provider abstraction enables:
- **Runtime Model Switching**: Change models without code modifications
- **Provider Agnostic**: Works with any OpenAI-compatible API
- **Centralized Configuration**: Single point of control for model selection
- **Easy Testing**: Switch to different models for evaluation

## Best Practices Demonstrated

✅ **Concurrent Agent Execution**: Parallel processing for improved performance  
✅ **Input Guardrails**: Security and policy enforcement at the agent level  
✅ **Structured Outputs**: Type-safe response parsing with Pydantic  
✅ **Tool Composition**: Modular, reusable tool design  
✅ **Agent Orchestration**: Hierarchical agent coordination patterns  
✅ **Async I/O**: Non-blocking file and network operations  
✅ **Exception Handling**: Graceful handling of guardrail violations and errors  
✅ **Multi-Model Support**: Provider-agnostic architecture  
✅ **Separation of Concerns**: Clear boundaries between workflow, manager, and system layers  
✅ **Configuration Management**: Environment-based configuration for deployment flexibility  
✅ **Interactive CLI**: User-friendly command-line interface for model selection

## Error Handling Patterns

### Guardrail Violations
```python
try:
    result = await Runner.run(...)
except InputGuardrailTripwireTriggered as e:
    # e.guardrail_result contains detailed violation information
    print(f"Policy violation: {e.guardrail_result.output}")
```

### SendGrid Integration
```python
def check_sendgrid_client(self) -> bool:
    status_code = send_test_email("Test", "Test content")
    return 202 == status_code
```

## Security Features

🔒 **Input Validation**: Guardrails prevent unauthorized content injection  
🔒 **Structured Outputs**: Type validation prevents malformed responses  
🔒 **Exception Handling**: Safe failure modes for policy violations  
🔒 **Environment-Based Secrets**: API keys stored in environment variables  
🔒 **Pre-Execution Checks**: SendGrid client validation before workflow starts

## License

This project is provided as-is for educational and development purposes.

---

**Built with OpenAI Agents SDK** | **Powered by AsyncIO** | **Production-Ready Architecture** | **Enterprise Security**
