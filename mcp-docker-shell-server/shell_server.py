import asyncio
import json
import time
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool


server = Server("shell-server")


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="terminal",
            description="Run a shell command on the host and return stdout, stderr, and exit code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute as a single string.",
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "description": "Optional timeout in seconds before the process is killed (default 60).",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        )
    ]


async def _run_shell_command(command: str, timeout_seconds: float) -> Dict[str, Any]:
    start_time = time.perf_counter()
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )
        return_code = process.returncode
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "stdout": stdout_bytes.decode(errors="replace"),
            "stderr": stderr_bytes.decode(errors="replace"),
            "return_code": return_code,
            "duration_ms": duration_ms,
        }
    except asyncio.TimeoutError:
        try:
            process.kill()
        finally:
            await process.wait()
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "stdout": "",
            "stderr": f"Process timed out after {timeout_seconds} seconds",
            "return_code": -1,
            "duration_ms": duration_ms,
        }


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any] | None) -> Any:
    if name != "terminal":
        return {
            "type": "text",
            "text": json.dumps({"error": f"Unknown tool: {name}"}),
        }

    if arguments is None or not isinstance(arguments, dict):
        return {
            "type": "text",
            "text": json.dumps({"error": "Missing arguments object"}),
        }

    command = arguments.get("command")
    if not isinstance(command, str) or not command.strip():
        return {
            "type": "text",
            "text": json.dumps({"error": "Argument 'command' must be a non-empty string"}),
        }

    timeout_seconds_value = arguments.get("timeout_seconds", 60)
    try:
        timeout_seconds = float(timeout_seconds_value)
        if timeout_seconds <= 0:
            return {
                "type": "text",
                "text": json.dumps({"error": "'timeout_seconds' must be > 0"}),
            }
    except (TypeError, ValueError):
        return {
            "type": "text",
            "text": json.dumps({"error": "'timeout_seconds' must be a number"}),
        }

    result = await _run_shell_command(command=command, timeout_seconds=timeout_seconds)
    return {"type": "text", "text": json.dumps(result)}


async def main() -> None:
    async with stdio_server() as (read, write):
        # Pass a proper InitializationOptions object instead of a bare dict.
        # Use the Server helper which fills in capabilities/version automatically.
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())


