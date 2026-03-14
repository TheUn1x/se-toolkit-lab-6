#!/usr/bin/env python3
"""
Regression tests for agent.py.

Tests that agent.py outputs valid JSON with required fields.
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_output_format() -> None:
    """Test that agent.py outputs valid JSON with answer and tool_calls fields."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with a simple question
    result = subprocess.run(
        [sys.executable, str(agent_path), "What is 2+2?"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Parse stdout as JSON
    stdout = result.stdout.strip()
    assert stdout, "stdout is empty"

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

    # Validate required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"


def test_agent_json_schema() -> None:
    """Test that the output JSON schema is correct."""
    # Expected schema:
    # {
    #   "answer": string,
    #   "tool_calls": array
    # }

    sample_outputs = [
        {"answer": "Representational State Transfer.", "tool_calls": []},
        {"answer": "A short answer.", "tool_calls": []},
        {"answer": "", "tool_calls": []},
    ]

    for output in sample_outputs:
        # Validate it's serializable
        json_str = json.dumps(output)
        parsed = json.loads(json_str)

        # Validate fields
        assert "answer" in parsed
        assert "tool_calls" in parsed
        assert isinstance(parsed["answer"], str)
        assert isinstance(parsed["tool_calls"], list)


def test_agent_no_question() -> None:
    """Test that agent.py returns error when no question is provided."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [sys.executable, str(agent_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Should exit with non-zero code
    assert result.returncode != 0, "Should exit with error when no question provided"
    # Error message should go to stderr
    assert "Usage" in result.stderr or "question" in result.stderr.lower()


def test_agent_merge_conflict_uses_read_file() -> None:
    """Test that agent.py uses read_file tool for merge conflict question."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with merge conflict question
    result = subprocess.run(
        [sys.executable, str(agent_path), "How do you resolve a merge conflict?"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Parse stdout as JSON
    stdout = result.stdout.strip()
    assert stdout, "stdout is empty"

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

    # Validate required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Validate that read_file was used
    tool_calls = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be a list"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names = [tc.get("tool") for tc in tool_calls]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Validate source contains wiki/git-workflow.md
    source = output["source"]
    assert isinstance(source, str), "'source' must be a string"
    assert "wiki/git-workflow.md" in source, f"Expected wiki/git-workflow.md in source, got: {source}"


def test_agent_list_wiki_files_uses_list_files() -> None:
    """Test that agent.py uses list_files tool for wiki listing question."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with wiki listing question
    result = subprocess.run(
        [sys.executable, str(agent_path), "What files are in the wiki?"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Parse stdout as JSON
    stdout = result.stdout.strip()
    assert stdout, "stdout is empty"

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

    # Validate required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Validate that list_files was used
    tool_calls = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be a list"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names = [tc.get("tool") for tc in tool_calls]
    assert "list_files" in tool_names, "Expected list_files to be called"

    # Validate that the result contains expected wiki files
    for tc in tool_calls:
        if tc.get("tool") == "list_files":
            result_content = tc.get("result", "")
            assert "git-workflow.md" in result_content or "git.md" in result_content, \
                "Expected list_files result to contain wiki files"


def test_agent_framework_uses_read_file() -> None:
    """Test that agent.py uses read_file tool for framework question."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with framework question
    result = subprocess.run(
        [sys.executable, str(agent_path), "What Python web framework does the backend use?"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Parse stdout as JSON
    stdout = result.stdout.strip()
    assert stdout, "stdout is empty"

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

    # Validate required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Validate that read_file was used
    tool_calls = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be a list"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names = [tc.get("tool") for tc in tool_calls]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Validate that answer mentions FastAPI
    answer = output.get("answer", "").lower()
    assert "fastapi" in answer, f"Expected answer to mention FastAPI, got: {output.get('answer')}"


def test_agent_items_count_uses_query_api() -> None:
    """Test that agent.py uses query_api tool for items count question."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with items count question
    result = subprocess.run(
        [sys.executable, str(agent_path), "How many items are in the database?"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Parse stdout as JSON
    stdout = result.stdout.strip()
    assert stdout, "stdout is empty"

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

    # Validate required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Validate that query_api was used
    tool_calls = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be a list"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names = [tc.get("tool") for tc in tool_calls]
    assert "query_api" in tool_names, "Expected query_api to be called"

    # Validate that the answer contains a number
    answer = output.get("answer", "")
    import re
    numbers = re.findall(r"\d+", answer)
    assert len(numbers) > 0, f"Expected answer to contain a number, got: {answer}"
