# OpenAI Agents - Sales Agent System

A sophisticated multi-agent system built with OpenAI's Agents SDK that demonstrates advanced agent orchestration, parallel execution, and tool integration for automated sales email generation and management.

## Overview

This project showcases a production-ready implementation of an AI-powered sales email system that leverages multiple specialized agents working in concert to generate, evaluate, and send compelling cold sales emails for ComplAI, a SOC2 compliance SaaS platform.

## Architecture

### Core Components

#### 1. **SimpleSalesAgentSystem** (`simple_sales_agent_system.py`)
The main entry point that orchestrates the entire workflow, managing agent initialization, configuration, and execution.

#### 2. **SalesAgentWorkflow**
A comprehensive workflow system that manages multiple specialized sales agents, each with distinct writing styles:
- **Professional Sales Agent**: Generates formal, serious cold emails
- **Humorous Sales Agent**: Creates witty, engaging content with personality
- **Concise Sales Agent**: Produces brief, to-the-point messages

#### 3. **SalesManager**
An intelligent manager agent that coordinates the draft generation process, evaluates outputs, and handles email delivery through tools or handoffs.

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
2. **Handoff-Based Coordination**: Manager delegates to specialized agents:
   ```python
   handoffs=[email_formatter_sender]  # Delegates formatting and sending
   ```

## Workflow Execution Modes

### Mode 1: Direct Tool Management
```python
with_handsoff=False
```
- Sales Manager uses sales agents as tools
- Directly invokes `send_email` tool
- Single-agent control flow

### Mode 2: Handoff Management
```python
with_handsoff=True
```
- Sales Manager evaluates drafts, then hands off to Email Manager
- Email Manager uses subject_writer, html_converter, and send_html_email tools
- Multi-agent collaborative workflow

## Technical Implementation Details

### Custom Model Provider
Integrates with custom OpenAI-compatible endpoints:
```python
class CustomModelProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(
            model="gpt-5-mini",
            openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key)
        )
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
- `agents`: OpenAI Agents SDK
- `asyncio`: Asynchronous programming
- `aiofiles`: Async file operations
- `sendgrid`: Email delivery
- `python-dotenv`: Environment management

## Usage

```python
# Initialize the system
sales_agent_system = SimpleSalesAgentSystem()
sales_manager = SalesManager(with_handsoff=True)

# Execute the workflow
message = "Send out a cold sales email addressed to Dear CEO from Alice"
asyncio.run(
    sales_manager.run_handoff_manager(
        input=message,
        run_config=sales_agent_system._run_config,
        tools=sales_manager.tools,
        handoffs=sales_manager.handsoff,
    )
)
```

## Output

Generated emails are saved to:
- `outputs/sales_agent_outputs.txt`: All draft emails from parallel execution
- `outputs/sales_manager_outputs.txt`: Final output from tool-based workflow
- `outputs/sales_manager_handoff_outputs.txt`: Final output from handoff-based workflow

## Best Practices Demonstrated

✅ **Concurrent Agent Execution**: Parallel processing for improved performance  
✅ **Tool Composition**: Modular, reusable tool design  
✅ **Agent Orchestration**: Hierarchical agent coordination patterns  
✅ **Async I/O**: Non-blocking file and network operations  
✅ **Error Handling**: Validation checks (SendGrid client verification)  
✅ **Separation of Concerns**: Clear boundaries between workflow, manager, and system layers  
✅ **Configuration Management**: Environment-based configuration for deployment flexibility

## License

This project is provided as-is for educational and development purposes.

---

**Built with OpenAI Agents SDK** | **Powered by AsyncIO** | **Production-Ready Architecture**
