# Task 3: The System Agent

## Implementation Plan

### Overview

Task 3 extends the Documentation Agent from Task 2 with a new `query_api` tool that can call the deployed backend API. The agent can now answer:
- **Static system facts** — framework, ports, status codes (from source code)
- **Data-dependent queries** — item count, scores, completion rates (from live API)
- **Bug diagnosis** — query API errors, then read source code to find bugs

### Architecture

Same agentic loop as Task 2, with one additional tool:

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

### New Tool: `query_api`

Call the deployed backend API with authentication.

**Parameters:**
- `method` (string, required) — HTTP method (GET, POST, etc.)
- `path` (string, required) — API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) — JSON request body for POST/PUT

**Returns:** JSON string with `status_code` and `body`

**Authentication:** Use `LMS_API_KEY` from `.env.docker.secret` via `Authorization: Bearer <key>` header

**Function schema:**
```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the deployed backend API. Use for data queries like item counts, scores, analytics.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, PUT, DELETE)",
          "enum": ["GET", "POST", "PUT", "DELETE"]
        },
        "path": {
          "type": "string",
          "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
        },
        "body": {
          "type": "string",
          "description": "JSON request body for POST/PUT (optional)"
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

### Environment Variables

The agent must read all configuration from environment variables (not hardcoded):

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` | Optional, defaults to `http://localhost:42002` |

**Important:** The autochecker injects different values at evaluation time. Hardcoded values will fail.

### System Prompt Update

Update the system prompt to guide the LLM on tool selection:

1. **Use `list_files`** to discover wiki files or source code structure
2. **Use `read_file`** to read wiki documentation or source code
3. **Use `query_api`** for:
   - Data queries (how many items, scores, analytics)
   - System facts (status codes, API responses)
   - Bug diagnosis (query error, then read source)

Example prompt addition:
```
For data-dependent questions (counts, scores, analytics), use query_api.
For static system facts (framework, file structure), use read_file or list_files.
For bug diagnosis: first query_api to see the error, then read_file to find the bug in source code.
```

### Output Format Change

In Task 2, `source` was required. In Task 3, `source` is **optional** — system questions may not have a wiki source.

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",  // optional, can be empty for API queries
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "..."}
  ]
}
```

### Implementation Steps

1. **Add `query_api` tool function:**
   - Read `LMS_API_KEY` from `.env.docker.secret`
   - Read `AGENT_API_BASE_URL` from env (default: `http://localhost:42002`)
   - Make HTTP request with `Authorization: Bearer <LMS_API_KEY>`
   - Return JSON with `status_code` and `body`

2. **Register tool schema:**
   - Add to `get_tool_definitions()`

3. **Update system prompt:**
   - Add guidance on when to use each tool

4. **Update output validation:**
   - Make `source` field optional

5. **Add 2 regression tests:**
   - `test_agent_framework_uses_read_file` — "What framework does the backend use?"
   - `test_agent_items_count_uses_query_api` — "How many items are in the database?"

6. **Run benchmark:**
   - `uv run run_eval.py`
   - Iterate until all 10 questions pass

### Benchmark Questions

| # | Question | Expected Tools | Grading |
|---|----------|----------------|---------|
| 0 | Wiki: protect a branch | `read_file` | keyword: branch, protect |
| 1 | Wiki: SSH connection | `read_file` | keyword: ssh/key/connect |
| 2 | Framework from source | `read_file` | keyword: FastAPI |
| 3 | API router modules | `list_files` | keyword: items, interactions, analytics, pipeline |
| 4 | Items in database | `query_api` | numeric > 0 |
| 5 | Status code without auth | `query_api` | keyword: 401/403 |
| 6 | `/analytics/completion-rate` bug | `query_api`, `read_file` | keyword: ZeroDivisionError |
| 7 | `/analytics/top-learners` bug | `query_api`, `read_file` | keyword: TypeError/None |
| 8 | Request lifecycle (docker-compose + Dockerfile) | `read_file` | LLM judge |
| 9 | ETL idempotency | `read_file` | LLM judge |

### Debugging Strategy

1. Run `uv run run_eval.py`
2. On failure, read the feedback hint
3. Fix the issue:
   - Tool not called → improve tool description in schema
   - Wrong arguments → clarify parameter descriptions
   - API error → fix tool implementation
   - Timeout → reduce max iterations
4. Re-run until all pass

### Timeline

1. Create `plans/task-3.md` (plan) — **commit first**
2. Update `agent.py` with `query_api` tool
3. Add 2 regression tests
4. Run `run_eval.py`, iterate until all 10 pass
5. Update `AGENT.md` with lessons learned (200+ words)
6. Git workflow: branch, commits, PR, review, merge

### Initial Benchmark Score

**First run:** 3/10 passed

Failures:
- Question 4 (router modules): Agent was reading files but not providing a summary answer
- Question 6 (status code): Agent was sending auth header by default, needed `auth=false` parameter
- Questions 7-10: Various issues with incomplete answers and tool selection

### Iteration Log

**Iteration 1:** Fixed router modules question
- Problem: Agent said "I'll continue reading" instead of providing answer
- Fix: Updated system prompt to require direct answers after reading files
- Result: 5/10 passed

**Iteration 2:** Fixed status code question
- Problem: Agent always sent auth header, got 200 instead of 401
- Fix: Added `auth` parameter to query_api tool (default true, can be set to false)
- Result: 7/10 passed

**Iteration 3:** Fixed bug diagnosis questions
- Problem: Agent answers were being cut off, missing keywords
- Fix: 
  - Increased MAX_TOOL_CALLS from 10 to 15
  - Updated system prompt with explicit bug diagnosis workflow
  - Added instruction to query with realistic parameters (e.g., `?lab=lab-01`)
- Result: 10/10 passed

**Final Score: 10/10 PASSED**

### Key Learnings

1. **Python boolean vs JSON boolean:** Used `true` instead of `True` in tool schema, causing NameError
2. **Auth parameter needed:** For testing unauthenticated access, agent needs `auth=false` option
3. **Explicit instructions matter:** LLM needs clear guidance on when to provide final answers
4. **Bug diagnosis workflow:** Must query with realistic parameters to trigger actual errors
