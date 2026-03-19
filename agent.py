#!/usr/bin/env python3
"""
Agent CLI — System Agent with Tools.

Usage:
    uv run agent.py "How many items are in the database?"

Output:
    {
      "answer": "There are 120 items in the database.",
      "source": "",
      "tool_calls": [
        {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "..."}
      ]
    }
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 15


def load_env() -> None:
    """Load environment variables from .env files."""
    # Load LLM config from .env.agent.secret
    agent_env_file = Path(__file__).parent / ".env.agent.secret"
    if agent_env_file.exists():
        load_dotenv(agent_env_file)

    # Load LMS API key from .env.docker.secret
    docker_env_file = Path(__file__).parent / ".env.docker.secret"
    if docker_env_file.exists():
        # Load only variables not already set
        for line in docker_env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_llm_config() -> dict[str, str]:
    """Get LLM configuration from environment variables."""
    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", os.getenv("LLM_API_BASE", "https://api.openai.com/v1")),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }


def get_api_config() -> dict[str, str]:
    """Get backend API configuration from environment variables."""
    return {
        "api_key": os.getenv("LMS_API_KEY", ""),
        "base_url": os.getenv("AGENT_API_BASE_URL", "http://localhost:42002"),
    }


def get_project_root() -> Path:
    """Get the project root directory (parent of agent.py)."""
    return Path(__file__).parent.resolve()


def validate_path(path: str) -> tuple[bool, str]:
    """
    Validate that a path is within the project directory.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is empty.
    """
    # Check for directory traversal
    if ".." in path:
        return False, "Path traversal not allowed: cannot contain '..'"

    # Resolve the full path
    project_root = get_project_root()
    try:
        full_path = (project_root / path).resolve()
    except Exception as e:
        return False, f"Invalid path: {e}"

    # Verify the path is within project root
    try:
        full_path.relative_to(project_root)
    except ValueError:
        return False, f"Path must be within project directory: {path}"

    return True, ""


def read_file_tool(path: str) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root.

    Returns:
        File contents as string, or error message.
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"

    project_root = get_project_root()
    file_path = project_root / path

    if not file_path.exists():
        return f"Error: File not found: {path}"

    if not file_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def list_files_tool(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root.

    Returns:
        Newline-separated listing of entries, or error message.
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"

    project_root = get_project_root()
    dir_path = project_root / path

    if not dir_path.exists():
        return f"Error: Directory not found: {path}"

    if not dir_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted(dir_path.iterdir())
        lines = [entry.name for entry in entries]
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing directory: {e}"


def query_api_tool(method: str, path: str, body: str | None = None, auth: bool = True) -> str:
    """
    Call the deployed backend API.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE).
        path: API path (e.g., '/items/', '/analytics/completion-rate').
        body: Optional JSON request body for POST/PUT.
        auth: Whether to include authentication header (default True). Set to False to test unauthenticated access.

    Returns:
        JSON string with status_code and body, or error message.
    """
    config = get_api_config()

    # Normalize path to start with /
    if not path.startswith("/"):
        path = "/" + path

    url = f"{config['base_url'].rstrip('/')}{path}"

    headers = {
        "Content-Type": "application/json",
    }

    # Only add auth header if requested
    if auth:
        if not config["api_key"]:
            return "Error: LMS_API_KEY not set in environment"
        headers["Authorization"] = f"Bearer {config['api_key']}"

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, content=body or "{}")
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, content=body or "{}")
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return f"Error: Unsupported method: {method}"

            result = {
                "status_code": response.status_code,
                "body": response.text,
            }
            return json.dumps(result, ensure_ascii=False)

    except httpx.ConnectError as e:
        return f"Error: Cannot connect to API at {url}: {e}"
    except httpx.HTTPError as e:
        return f"Error: HTTP request failed: {e}"
    except Exception as e:
        return f"Error: {e}"


def get_tool_definitions() -> list[dict[str, Any]]:
    """Get tool definitions for LLM function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the project repository. Use this to read wiki documentation or source code files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md', 'backend/app/main.py')",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path. Use this to discover what files exist in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki', 'backend/app/routers')",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Call the deployed backend API. Use for data queries (item counts, scores, analytics), system facts (status codes), and bug diagnosis. For bug diagnosis: first query to see the error, then use read_file to find the bug in source code.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE)",
                            "enum": ["GET", "POST", "PUT", "DELETE"],
                        },
                        "path": {
                            "type": "string",
                            "description": "API path (e.g., '/items/', '/analytics/completion-rate', '/analytics/scores')",
                        },
                        "body": {
                            "type": "string",
                            "description": "JSON request body for POST/PUT requests (optional)",
                        },
                        "auth": {
                            "type": "boolean",
                            "description": "Whether to include authentication header (default: true). Set to false to test unauthenticated access.",
                            "default": True,
                        },
                    },
                    "required": ["method", "path"],
                },
            },
        },
    ]


def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    """
    Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute.
        args: Tool arguments.

    Returns:
        Tool result as string.
    """
    if tool_name == "read_file":
        return read_file_tool(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files_tool(args.get("path", ""))
    elif tool_name == "query_api":
        return query_api_tool(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("body"),
            args.get("auth", True),
        )
    else:
        return f"Error: Unknown tool: {tool_name}"


def get_system_prompt() -> str:
    """Get the system prompt for the LLM."""
    return """You are a helpful documentation and system assistant. You have access to tools to:
1. Read files and list directories in a project wiki and source code
2. Query a deployed backend API for data and system information

When answering questions:
- For wiki documentation questions: use list_files to discover files, then read_file to find answers
- For source code questions: use list_files to explore structure, then read_file to read code
- For data queries (counts, scores, analytics): use query_api with GET method
- For system facts (status codes, API responses): use query_api
- For bug diagnosis:
  1. First query the API with appropriate parameters to see the actual error
  2. Then read the source code to find the bug
  3. Provide a complete answer with error type, location, and cause
- For testing unauthenticated access: use query_api with auth=false to see what status code is returned without authentication
- For request lifecycle questions (e.g., "journey of HTTP request"): Read docker-compose.yml, Caddyfile, Dockerfile, and main.py — then provide a complete answer tracing all hops from browser → Caddy → FastAPI → auth → router → ORM → PostgreSQL and back.

EFFICIENCY: When you need to read multiple files (e.g., all router modules), make ALL read_file calls in a SINGLE turn. Do not read files one at a time. After listing files, immediately request to read all relevant files at once by making multiple tool calls.

CRITICAL RULES:
1. After gathering information with tools, you MUST provide a direct, complete answer in your NEXT response.
2. NEVER say "Let me check", "I'll continue", "Now I need to", or similar phrases — these indicate you haven't finished.
3. If you have read the relevant files, IMMEDIATELY provide the final answer with all details.
4. Your response after tool calls should be the FINAL ANSWER, not another planning step.

CRITICAL: For bug diagnosis questions:
1. Query the API with realistic parameters to trigger the actual error (e.g., /analytics/top-learners?lab=lab-01)
2. Read the source code to find the buggy line
3. Provide a complete answer that includes:
   - The error type (e.g., TypeError, ZeroDivisionError)
   - The specific bug location (file and function/line)
   - What causes the bug (e.g., "sorting None values", "division by zero")
   - Include keywords from the question (e.g., TypeError, None, sorted)

Example for "list all API routers":
1. First turn: list_files("backend/app/routers")
2. Second turn: read_file("backend/app/routers/items.py"), read_file("backend/app/routers/analytics.py"), read_file("backend/app/routers/interactions.py"), read_file("backend/app/routers/pipeline.py") — ALL AT ONCE
3. Third turn: Provide a direct answer like "The backend has these router modules: items.py handles item CRUD operations, analytics.py handles analytics endpoints, interactions.py handles user interactions, pipeline.py handles ETL pipeline operations."

Example for "HTTP request journey":
1. First turn: read_file("docker-compose.yml"), read_file("caddy/Caddyfile"), read_file("Dockerfile"), read_file("backend/app/main.py") — ALL AT ONCE
2. Second turn: Provide a complete answer like "The HTTP request journey is: 1) Browser sends request to Caddy reverse proxy on port X, 2) Caddy forwards to FastAPI app, 3) FastAPI authenticates using LMS_API_KEY, 4) Request routed to appropriate handler, 5) ORM queries PostgreSQL, 6) Response flows back through the same path."

Always include a source reference in the format: wiki/filename.md#section-anchor or backend/path/file.py for code.
For API queries, the source can be the API endpoint (e.g., GET /items/).

You have a maximum of 15 tool calls per question. Use them efficiently.

To find section anchors in markdown files:
- Look for headers like `# Section Name` or `## Section Name`
- Convert to lowercase, replace spaces with hyphens: `#section-name`
- Include the anchor in your source field"""


def call_llm(
    messages: list[dict[str, Any]], config: dict[str, str], tools: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """
    Call LLM API and return the response.

    Args:
        messages: List of message dicts with 'role' and 'content'.
        config: LLM configuration.
        tools: Optional list of tool definitions.

    Returns:
        Dict with 'content' and 'tool_calls' keys.
    """
    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "max_tokens": 1500,
        "temperature": 0.7,
    }

    if tools:
        payload["tools"] = tools

    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]

        result = {
            "content": message.get("content") or "",
            "tool_calls": [],
        }

        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                if tc.get("type") == "function":
                    result["tool_calls"].append({
                        "id": tc.get("id", ""),
                        "name": tc["function"]["name"],
                        "arguments": json.loads(tc["function"]["arguments"]),
                    })

        return result


def run_agentic_loop(question: str, config: dict[str, str]) -> dict[str, Any]:
    """
    Run the agentic loop to answer a question.

    Args:
        question: User's question.
        config: LLM configuration.

    Returns:
        Dict with 'answer', 'source', and 'tool_calls' keys.
    """
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": question},
    ]

    tools = get_tool_definitions()
    all_tool_calls: list[dict[str, Any]] = []

    for iteration in range(MAX_TOOL_CALLS):
        response = call_llm(messages, config, tools)

        # If no tool calls, check if we have a final answer
        if not response["tool_calls"]:
            answer = response["content"]
            
            # Check if this looks like an intermediate thought (not a final answer)
            intermediate_phrases = [
                "let me", "i'll", "i will", "now i need", "let's check",
                "let's see", "i should", "i need to", "checking", "looking at"
            ]
            answer_lower = answer.lower().strip()
            is_intermediate = any(phrase in answer_lower for phrase in intermediate_phrases)
            
            # Also check if answer is too short to be complete (less than 50 chars and no punctuation)
            is_too_short = len(answer_lower) < 50 and not answer.endswith('.')
            
            if is_intermediate or is_too_short:
                # Add a user message to prompt for final answer
                messages.append({
                    "role": "user",
                    "content": "Please provide your final answer now. Do not say 'let me check' or similar - just give the complete answer based on the information you've gathered."
                })
                continue
            
            # Extract source from the answer if possible
            source = extract_source_from_answer(answer)

            return {
                "answer": answer,
                "source": source,
                "tool_calls": all_tool_calls,
            }

        # Add assistant message with tool calls FIRST (required by Qwen API)
        assistant_content = response["content"] if response["content"] else ""
        messages.append({
            "role": "assistant",
            "content": assistant_content,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"]),
                    },
                }
                for tc in response["tool_calls"]
            ],
        })

        # Execute tool calls and add tool responses AFTER assistant message
        for tool_call in response["tool_calls"]:
            tool_name = tool_call["name"]
            tool_args = tool_call["arguments"]

            # Execute the tool
            result = execute_tool(tool_name, tool_args)

            # Record the tool call with result
            all_tool_calls.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            })

            # Add tool response to messages (must come after assistant with tool_calls)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result,
            })

    # Max iterations reached
    answer = "Maximum tool call limit reached. Partial answer based on available information."
    source = extract_source_from_tool_calls(all_tool_calls)

    return {
        "answer": answer,
        "source": source,
        "tool_calls": all_tool_calls,
    }


def extract_source_from_answer(answer: str) -> str:
    """
    Try to extract a source reference from the answer.

    Looks for patterns like wiki/filename.md#section or wiki/filename.md or backend/...
    """
    # Look for wiki file reference with anchor
    match = re.search(r"(wiki/[\w\-/.]+\.md#[\w\-]+)", answer)
    if match:
        return match.group(1)

    # Look for wiki file reference without anchor
    match = re.search(r"(wiki/[\w\-/.]+\.md)", answer)
    if match:
        return match.group(1)

    # Look for backend source file reference
    match = re.search(r"(backend/[\w\-/.]+\.py)", answer)
    if match:
        return match.group(1)

    # Look for API endpoint reference
    match = re.search(r"(GET|POST|PUT|DELETE)\s+(/[\w\-/.]+)", answer)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    return ""


def extract_source_from_tool_calls(tool_calls: list[dict[str, Any]]) -> str:
    """
    Extract source from the last tool call.

    For read_file: returns the file path
    For query_api: returns the API endpoint
    """
    for tc in reversed(tool_calls):
        if tc["tool"] == "read_file":
            path = tc["args"].get("path", "")
            if path:
                # Try to extract section from result
                result = tc.get("result", "")
                section = extract_section_from_content(result)
                if section:
                    return f"{path}#{section}"
                return path
        elif tc["tool"] == "query_api":
            method = tc["args"].get("method", "GET")
            path = tc["args"].get("path", "")
            return f"{method} {path}"
        elif tc["tool"] == "list_files":
            path = tc["args"].get("path", "")
            return path
    return ""


def extract_section_from_content(content: str) -> str:
    """
    Try to extract a section anchor from file content.

    Looks for markdown headers that might be relevant.
    """
    lines = content.split("\n")
    for line in lines[:50]:  # Check first 50 lines
        # Match markdown headers
        match = re.match(r"^#+\s+(.+)$", line)
        if match:
            header = match.group(1).strip().lower()
            # Convert to anchor format
            anchor = header.replace(" ", "-").replace("'", "").replace('"', "")
            anchor = re.sub(r"[^a-z0-9\-]", "", anchor)
            if anchor:
                return anchor
    return ""


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py <question>", file=sys.stderr)
        return 1

    question = sys.argv[1]

    load_env()
    llm_config = get_llm_config()

    if not llm_config["api_key"]:
        print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
        return 1

    try:
        result = run_agentic_loop(question, llm_config)
    except httpx.HTTPError as e:
        print(f"Error calling LLM API: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        import traceback
        print(f"Unexpected error: {e}", file=sys.stderr)
        print(f"Traceback: {traceback.format_exc()}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
