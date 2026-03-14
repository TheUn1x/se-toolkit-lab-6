# Agent — Call an LLM from Code

## Overview

This is a simple Python CLI agent that takes a question as input, sends it to an LLM (Large Language Model), and returns a structured JSON response.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  CLI Input  │────▶│   agent.py   │────▶│  LLM API    │
│  (question) │     │  (orchestra  │     │  (OpenAI)   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  JSON Output │
                    │  {answer,    │
                    │   tool_calls}│
                    └──────────────┘
```

## LLM Provider

**Provider:** OpenAI API (or compatible API)

**Model:** `gpt-4o-mini` (configurable via `LLM_MODEL`)

**API Endpoint:** `https://api.openai.com/v1/chat/completions`

### Alternative Providers

You can use any OpenAI-compatible API by setting:
- `LLM_BASE_URL` — API base URL
- `LLM_MODEL` — Model name

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
uv run agent.py "What does REST stand for?"
```

### Output

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

### Output Format

- `answer` (string): The LLM's response to the question.
- `tool_calls` (array): Empty for this task (will be populated in Task 2).

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for the LLM provider | Required |
| `LLM_BASE_URL` | Base URL for the API | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model to use | `gpt-4o-mini` |

## Error Handling

- If no question is provided, the agent prints usage to stderr and exits with code 1.
- If `LLM_API_KEY` is not set, the agent prints an error to stderr and exits with code 1.
- If the API call fails, the agent prints the error to stderr and exits with code 1.
- All errors go to stderr; only valid JSON goes to stdout.

## Testing

Run tests:
```bash
uv run pytest tests/test_agent.py -v
```

## Files

- `agent.py` — Main CLI entry point.
- `.env.agent.secret` — API key (not committed to Git).
- `.env.agent.secret.example` — Example configuration.
- `AGENT.md` — This documentation.
- `plans/task-1.md` — Implementation plan.
- `tests/test_agent.py` — Regression tests.
