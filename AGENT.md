# Agent — System Agent with API Tool

## Overview

This is a Python CLI agent that takes a question as input, uses **tools** to navigate the project wiki, read source code, and query a deployed backend API. It returns a structured JSON response with the answer, optional source reference, and tool call history.

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
                    │  - query_api  │            │
                    └──────────────┘            │
                           │                    │
                           └────────────────────┘
                                   ▼
                          ┌──────────────┐
                          │  JSON Output │
                          │  {answer,    │
                          │   source?,   │
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

### `query_api`

Call the deployed backend API with authentication.

**Parameters:**
- `method` (string, required) — HTTP method (GET, POST, PUT, DELETE)
- `path` (string, required) — API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) — JSON request body for POST/PUT

**Returns:** JSON string with `status_code` and `body`, or error message

**Authentication:** Uses `LMS_API_KEY` from environment via `Authorization: Bearer <key>` header

**Example:**
```json
{"tool": "query_api", "args": {"method": "GET", "path": "/items/"}}
```

## Installation

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Create `.env.agent.secret` file with your LLM API key:
   ```bash
   cp .env.agent.secret.example .env.agent.secret
   ```

3. Ensure `.env.docker.secret` has `LMS_API_KEY` set for API authentication

## Usage

```bash
uv run agent.py "How many items are in the database?"
```

### Output

```json
{
  "answer": "There are 120 items in the database.",
  "source": "GET /items/",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's response to the question |
| `source` | string | Optional. Wiki section, source file, or API endpoint reference |
| `tool_calls` | array | All tool calls made. Each entry has `tool`, `args`, and `result` |

### Tool Call Format

Each entry in `tool_calls`:

| Field | Type | Description |
|-------|------|-------------|
| `tool` | string | Tool name (`read_file`, `list_files`, or `query_api`) |
| `args` | object | Tool arguments (e.g., `{"path": "wiki"}`) |
| `result` | string | Tool execution result |

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for the LLM provider | Required |
| `LLM_API_BASE` | Base URL for the LLM API | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model to use | `gpt-4o-mini` |
| `LMS_API_KEY` | Backend API key for `query_api` authentication | Required for API queries |
| `AGENT_API_BASE_URL` | Base URL for the backend API | `http://localhost:42002` |

**Important:** The autochecker injects different values at evaluation time. Do not hardcode any of these values.

## System Prompt Strategy

The system prompt instructs the LLM to:

1. **Use `list_files`** to discover wiki files or source code structure
2. **Use `read_file`** to read wiki documentation or source code
3. **Use `query_api`** for:
   - Data queries (how many items, scores, analytics)
   - System facts (status codes, API responses)
   - Bug diagnosis (query error first, then read source code to find the bug)

### Tool Selection Guide

| Question Type | Tool to Use |
|--------------|-------------|
| Wiki documentation | `list_files` → `read_file` |
| Source code analysis | `list_files` → `read_file` |
| Data queries (counts, scores) | `query_api` |
| Status codes | `query_api` |
| Bug diagnosis | `query_api` → `read_file` |
| Request lifecycle | `read_file` (docker-compose.yml, Dockerfile) |
| ETL idempotency | `read_file` (etl.py) |

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
- If `LMS_API_KEY` is not set, `query_api` returns an error.
- All errors go to stderr; only valid JSON goes to stdout.

## Security

### Path Traversal Prevention

Both `read_file` and `list_files` validate paths:
- Reject paths containing `..`
- Resolve path and verify it's within project root
- Return error message for invalid paths

### API Key Separation

Two distinct keys are used:
- `LLM_API_KEY` (in `.env.agent.secret`) — authenticates with LLM provider
- `LMS_API_KEY` (in `.env.docker.secret`) — authenticates with backend API

Never mix these keys or hardcode them in the code.

## Testing

Run tests:
```bash
uv run pytest tests/test_agent.py -v
```

### Test Coverage

- `test_agent_output_format` — Validates JSON output with answer, source, tool_calls
- `test_agent_json_schema` — Validates output JSON schema
- `test_agent_no_question` — Validates error handling for missing question
- `test_agent_merge_conflict_uses_read_file` — Tests read_file tool for wiki questions
- `test_agent_list_wiki_files_uses_list_files` — Tests list_files tool for wiki listing
- `test_agent_framework_uses_read_file` — Tests read_file for source code questions
- `test_agent_items_count_uses_query_api` — Tests query_api for data queries

## Benchmark Evaluation

Run the local benchmark:
```bash
uv run run_eval.py
```

The benchmark tests 10 questions across all classes:
- Wiki lookup (protect branch, SSH)
- System facts (framework, status codes)
- Data queries (item count)
- Bug diagnosis (ZeroDivisionError, TypeError)
- Reasoning (request lifecycle, ETL idempotency)

## Files

- `agent.py` — Main CLI entry point with agentic loop and all tools.
- `.env.agent.secret` — LLM API key (not committed to Git).
- `.env.agent.secret.example` — Example LLM configuration.
- `.env.docker.secret` — Backend API key (not committed to Git).
- `AGENT.md` — This documentation.
- `plans/task-3.md` — Implementation plan.
- `tests/test_agent.py` — Regression tests.
- `run_eval.py` — Local benchmark runner.

## Lessons Learned

Building the System Agent taught several important lessons about designing agentic systems that interact with real-world APIs.

**1. Tool descriptions matter.** Initially, the LLM would call the wrong tool for data queries. Making the `query_api` description explicit about "use for data queries, counts, scores, analytics" significantly improved tool selection. The key was distinguishing when to use each tool: wiki questions → read_file, data questions → query_api, bugs → query_api first then read_file.

**2. Environment variable separation is critical.** Mixing up `LLM_API_KEY` and `LMS_API_KEY` caused confusing authentication failures. Keeping them in separate files (`.env.agent.secret` vs `.env.docker.secret`) and documenting their purposes clearly prevented this.

**3. Error handling in tools.** The `query_api` tool initially crashed on connection errors. Wrapping HTTP calls in try/except and returning descriptive error messages allowed the LLM to understand what went wrong and potentially retry or report the issue.

**4. Source field flexibility.** In Task 2, `source` was always a wiki file. With API queries, the source became the API endpoint (e.g., `GET /items/`). Making `source` optional and context-dependent was necessary for the agent to handle diverse question types.

**5. Iterative debugging with run_eval.py.** The benchmark runner was invaluable for rapid iteration. Each failure revealed a specific issue: wrong tool, missing keyword, or incorrect argument. Fixing one issue at a time and re-running led to a working agent.

**6. Maximum iterations protection.** The 10-call limit prevents infinite loops but can truncate legitimate multi-step reasoning. We increased it to 15 to allow for complex bug diagnosis workflows.

**7. Python vs JSON booleans.** A subtle bug: using `true` (JSON) instead of `True` (Python) in the tool schema caused a NameError. Always use Python syntax in Python code, even when defining JSON schemas.

**8. Auth parameter for testing.** To test unauthenticated access (e.g., "what status code without auth?"), we added an optional `auth` parameter to `query_api`. This allows the LLM to explicitly request unauthenticated requests.

**9. Explicit answer instructions.** The LLM would sometimes say "I'll continue reading" instead of providing answers. Adding explicit instructions like "MUST provide a direct, complete answer" and "Do not say 'I'll continue'" significantly improved response quality.

**10. Bug diagnosis workflow.** For bug questions, the agent needs to: (1) query with realistic parameters to trigger the error, (2) read the source code, (3) provide answer with error type, location, and cause. Making this workflow explicit in the system prompt was essential.

## Final Benchmark Score

**10/10 PASSED** on local evaluation.

The agent successfully handles:
- Wiki documentation lookup (branch protection, SSH)
- Source code analysis (framework, router modules)
- Data queries (item count)
- System facts (status codes without auth)
- Bug diagnosis (ZeroDivisionError, TypeError with None values)
- Reasoning questions (request lifecycle, ETL idempotency)

Note: The autochecker bot tests 10 additional hidden questions and uses LLM-based judging for open-ended answers.

## Example Sessions

### Wiki Question
```
$ uv run agent.py "How do you resolve a merge conflict?"
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [...]
}
```

### API Question
```
$ uv run agent.py "How many items are in the database?"
{
  "answer": "There are 120 items in the database.",
  "source": "GET /items/",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "..."}
  ]
}
```

### Bug Diagnosis
```
$ uv run agent.py "Query /analytics/completion-rate for lab-99. What error do you get?"
{
  "answer": "The API returns a ZeroDivisionError because there are no learners in lab-99, causing division by zero when calculating the completion rate.",
  "source": "backend/app/routers/analytics.py#get_completion-rate",
  "tool_calls": [
    {"tool": "query_api", ...},
    {"tool": "read_file", "args": {"path": "backend/app/routers/analytics.py"}, "result": "..."}
  ]
}
```
