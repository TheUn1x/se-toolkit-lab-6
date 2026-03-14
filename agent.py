#!/usr/bin/env python3
"""
Agent CLI — Documentation Agent with Tools.

Usage:
    uv run agent.py "How do you resolve a merge conflict?"

Output:
    {
      "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
      "source": "wiki/git-workflow.md#resolving-merge-conflicts",
      "tool_calls": [
        {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
        {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
      ]
    }
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10


def load_env() -> None:
    """Load environment variables from .env.agent.secret."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    if env_file.exists():
        load_dotenv(env_file)


def get_llm_config() -> dict[str, str]:
    """Get LLM configuration from environment variables."""
    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
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


def get_tool_definitions() -> list[dict[str, Any]]:
    """Get tool definitions for LLM function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the project repository. Use this to read file contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
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
                "description": "List files and directories at a given path. Use this to discover what files exist.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki')",
                        }
                    },
                    "required": ["path"],
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
    else:
        return f"Error: Unknown tool: {tool_name}"


def get_system_prompt() -> str:
    """Get the system prompt for the LLM."""
    return """You are a helpful documentation assistant. You have access to tools to read files and list directories in a project wiki.

When answering questions:
1. Use list_files to discover relevant wiki files
2. Use read_file to read file contents and find answers
3. Always include a source reference in the format: wiki/filename.md#section-anchor
4. Call tools as needed, then provide a final answer when you have enough information

You have a maximum of 10 tool calls per question.

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
            "content": message.get("content", ""),
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

        # If no tool calls, we have the final answer
        if not response["tool_calls"]:
            # Extract source from the answer if possible
            answer = response["content"]
            source = extract_source_from_answer(answer)

            return {
                "answer": answer,
                "source": source,
                "tool_calls": all_tool_calls,
            }

        # Execute tool calls
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

            # Add tool response to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result,
            })

        # Add assistant message with tool calls
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

    Looks for patterns like wiki/filename.md#section or wiki/filename.md
    """
    import re

    # Look for wiki file reference with anchor
    match = re.search(r"(wiki/[\w\-/.]+\.md#[\w\-]+)", answer)
    if match:
        return match.group(1)

    # Look for wiki file reference without anchor
    match = re.search(r"(wiki/[\w\-/.]+\.md)", answer)
    if match:
        return match.group(1)

    return ""


def extract_source_from_tool_calls(tool_calls: list[dict[str, Any]]) -> str:
    """
    Extract source from the last read_file tool call.

    Tries to find a relevant section from the answer context.
    """
    for tc in reversed(tool_calls):
        if tc["tool"] == "read_file":
            path = tc["args"].get("path", "")
            if path.startswith("wiki/"):
                # Try to extract section from result
                result = tc.get("result", "")
                section = extract_section_from_content(result)
                if section:
                    return f"{path}#{section}"
                return path
    return ""


def extract_section_from_content(content: str) -> str:
    """
    Try to extract a section anchor from file content.

    Looks for markdown headers that might be relevant.
    """
    import re

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
    config = get_llm_config()

    if not config["api_key"]:
        print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
        return 1

    try:
        result = run_agentic_loop(question, config)
    except httpx.HTTPError as e:
        print(f"Error calling LLM API: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
