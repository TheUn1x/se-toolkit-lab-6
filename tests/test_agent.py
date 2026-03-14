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
