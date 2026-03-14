# Task 2: The Documentation Agent

## Implementation Plan

### Overview

Task 2 extends the CLI agent from Task 1 with **tools** and an **agentic loop**. The agent can now:
- Call `read_file` and `list_files` tools to navigate the project wiki
- Execute an agentic loop: send question → LLM returns tool_calls → execute tools → feed results back → repeat
- Return structured JSON with `answer`, `source`, and `tool_calls` fields

### Architecture

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

### Agentic Loop

1. Send user question + tool definitions to LLM
2. If LLM responds with `tool_calls`:
   - Execute each tool call
   - Append results as `tool` role messages
   - Go to step 1 (max 10 iterations)
3. If LLM responds with text (no tool calls):
   - Extract answer and source
   - Output JSON and exit

### Tool Schemas

#### `read_file`

Read a file from the project repository.

**Parameters:**
- `path` (string, required) — relative path from project root

**Returns:** File contents as string, or error message if file doesn't exist

**Security:** Must not read files outside project directory (no `../` traversal)

**Function schema:**
```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read a file from the project repository",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative path from project root"
        }
      },
      "required": ["path"]
    }
  }
}
```

#### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string, required) — relative directory path from project root

**Returns:** Newline-separated listing of entries

**Security:** Must not list directories outside project directory

**Function schema:**
```json
{
  "type": "function",
  "function": {
    "name": "list_files",
    "description": "List files and directories at a given path",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative directory path from project root"
        }
      },
      "required": ["path"]
    }
  }
}
```

### System Prompt

The system prompt instructs the LLM to:
1. Use `list_files` to discover wiki files
2. Use `read_file` to find the answer
3. Include source reference (file path + section anchor)
4. Call tools when needed, provide final answer when done

Example:
```
You are a helpful documentation assistant. You have access to tools to read files and list directories in a project wiki.

When answering questions:
1. Use list_files to discover relevant wiki files
2. Use read_file to read file contents and find answers
3. Always include a source reference in the format: wiki/filename.md#section-anchor
4. Call tools as needed, then provide a final answer when you have enough information

You have a maximum of 10 tool calls per question.
```

### Path Security

Both tools must validate paths to prevent directory traversal:
- Reject paths containing `..`
- Resolve path and verify it's within project root
- Return error message for invalid paths

### Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

**Fields:**
- `answer` (string, required) — The LLM's response
- `source` (string, required) — Wiki section reference (e.g., `wiki/git-workflow.md#section`)
- `tool_calls` (array, required) — All tool calls made. Each entry has `tool`, `args`, and `result`

### Dependencies

Same as Task 1:
- `httpx` — HTTP client for API calls
- `pydantic-settings` — Settings loading from `.env`
- `python-dotenv` — Environment variable loading

### Testing

Add 2 regression tests:

1. **"How do you resolve a merge conflict?"**
   - Expects `read_file` in `tool_calls`
   - Expects `wiki/git-workflow.md` in `source`

2. **"What files are in the wiki?"**
   - Expects `list_files` in `tool_calls`

### Timeline

1. Create `plans/task-2.md` (plan) — **commit first**
2. Update `agent.py` with tools and agentic loop
3. Update `AGENT.md` with documentation
4. Add 2 regression tests to `tests/test_agent.py`
5. Run tests, verify they pass
6. Git workflow: branch, commits, PR, review, merge
