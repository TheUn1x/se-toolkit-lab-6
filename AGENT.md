# Agent — Documentation Agent with Tools

## Overview

This is a Python CLI agent that takes a question as input, uses **tools** to navigate the project wiki, and returns a structured JSON response with the answer, source reference, and tool call history.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  CLI Input  │────▶│   agent.py   │────▶│  LLM API    │
│  (question) │     │  (orchestra  │     │  (OpenAI)   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                     │
                           │  ◀─────┐            │
                           ▼        │            ▼
                    ┌──────────────┐     ┌─────────────┐
                    │  Tool Executor│    │  Tool Calls │
                    │  - read_file  │     │  (JSON)     │
                    │  - list_files │     └─────────────┘
                    └──────────────┘            │
                           │                    │
                           └────────────────────┘
                                   ▼
                          ┌──────────────┐
                          │  JSON Output │
                          │  {answer,    │
                          │   source,    │
                          │   tool_calls}│
                          └──────────────┘
```

## Agentic Loop

The agent follows this loop:

1. **Send** user question + tool definitions to LLM
2. **If LLM returns tool_calls:**
   - Execute each tool
   - Append results as `tool` role messages
   - Go to step 1 (max 10 iterations)
3. **If LLM returns text (no tool calls):**
   - Extract answer and source
   - Output JSON and exit

## LLM Provider

**Provider:** OpenAI API (or compatible API)

**Model:** `gpt-4o-mini` (configurable via `LLM_MODEL`)

**API Endpoint:** `https://api.openai.com/v1/chat/completions`

### Alternative Providers

You can use any OpenAI-compatible API by setting:
- `LLM_BASE_URL` — API base URL
- `LLM_MODEL` — Model name

## Tools

### `read_file`

Read a file from the project repository.

**Parameters:**
- `path` (string, required) — Relative path from project root

**Returns:** File contents as string, or error message

**Security:** Rejects paths containing `..` (directory traversal prevention)

**Example:**
```json
{"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}}
```

### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string, required) — Relative directory path from project root

**Returns:** Newline-separated listing of entries

**Security:** Rejects paths containing `..` (directory traversal prevention)

**Example:**
```json
{"tool": "list_files", "args": {"path": "wiki"}}
```

## Installation

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Create `.env.agent.secret` file with your API key:
   ```bash
   cp .env.agent.secret.example .env.agent.secret
   # Edit .env.agent.secret and add your API key
   ```

## Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "# Git workflow...\n..."
    }
  ]
}
```

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's response to the question |
| `source` | string | Wiki section reference (e.g., `wiki/git-workflow.md#section`) |
| `tool_calls` | array | All tool calls made. Each entry has `tool`, `args`, and `result` |

### Tool Call Format

Each entry in `tool_calls`:

| Field | Type | Description |
|-------|------|-------------|
| `tool` | string | Tool name (`read_file` or `list_files`) |
| `args` | object | Tool arguments (e.g., `{"path": "wiki"}`) |
| `result` | string | Tool execution result |

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for the LLM provider | Required |
| `LLM_BASE_URL` | Base URL for the API | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model to use | `gpt-4o-mini` |

## System Prompt Strategy

The system prompt instructs the LLM to:

1. Use `list_files` to discover relevant wiki files
2. Use `read_file` to read file contents and find answers
3. Always include a source reference in format: `wiki/filename.md#section-anchor`
4. Call tools as needed, then provide final answer when enough information is gathered
5. Maximum 10 tool calls per question

### Section Anchor Format

To create section anchors:
- Look for headers like `# Section Name` or `## Section Name`
- Convert to lowercase, replace spaces with hyphens: `#section-name`
- Example: `## Resolving Merge Conflicts` → `#resolving-merge-conflicts`

## Error Handling

- If no question is provided, the agent prints usage to stderr and exits with code 1.
- If `LLM_API_KEY` is not set, the agent prints an error to stderr and exits with code 1.
- If the API call fails, the agent prints the error to stderr and exits with code 1.
- If path traversal is detected, tools return an error message.
- All errors go to stderr; only valid JSON goes to stdout.

## Security

### Path Traversal Prevention

Both tools validate paths:
- Reject paths containing `..`
- Resolve path and verify it's within project root
- Return error message for invalid paths

## Testing

Run tests:
```bash
uv run pytest tests/test_agent.py -v
```

### Test Coverage

- `test_agent_output_format` — Validates JSON output with answer, source, tool_calls
- `test_agent_json_schema` — Validates output JSON schema
- `test_agent_no_question` — Validates error handling for missing question
- `test_agent_merge_conflict` — Tests read_file tool usage for merge conflict question
- `test_agent_list_wiki_files` — Tests list_files tool usage for wiki listing question

## Files

- `agent.py` — Main CLI entry point with agentic loop.
- `.env.agent.secret` — API key (not committed to Git).
- `.env.agent.secret.example` — Example configuration.
- `AGENT.md` — This documentation.
- `plans/task-2.md` — Implementation plan.
- `tests/test_agent.py` — Regression tests.

## Example Session

```
$ uv run agent.py "How do you resolve a merge conflict?"
{
  "answer": "To resolve a merge conflict: 1) Edit the conflicting file to choose which changes to keep, 2) Stage the resolved file with `git add`, 3) Commit the changes.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\ngit.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "# Git workflow\n\n## Resolving Merge Conflicts\n..."
    }
  ]
}
```
