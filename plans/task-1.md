# Task 1: Call an LLM from Code

## Implementation Plan

### LLM Provider and Model

**Provider:** OpenAI API (или совместимый API, например, GigaChat/Sber)

**Model:** `gpt-4o-mini` или `gpt-3.5-turbo` — баланс между скоростью и качеством ответов.

Альтернатива для РФ: GigaChat (`gigachat`) через их API.

### Architecture

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

### Component Structure

1. **agent.py** — точка входа CLI:
   - Парсинг аргументов командной строки (вопрос как первый аргумент).
   - Загрузка API-ключа из `.env.agent.secret`.
   - Вызов LLM через HTTP-клиент (httpx).
   - Форматирование ответа в JSON.
   - Вывод JSON в stdout, логи — в stderr.

2. **System Prompt** (минимальный):
   ```
   You are a helpful assistant. Answer questions concisely and accurately.
   ```

3. **Output Format**:
   ```json
   {"answer": "<текст ответа>", "tool_calls": []}
   ```

### Dependencies

- `httpx` — HTTP-клиент для вызова API.
- `pydantic-settings` — загрузка настроек из `.env`.
- `python-dotenv` — загрузка переменных окружения.

### API Key Storage

API-ключ хранится в `.env.agent.secret` (добавлен в `.gitignore`):
```
LLM_API_KEY=<ключ>
```

### Testing

Регрессионный тест (`tests/test_agent.py`):
- Запускает `agent.py` как subprocess с тестовым вопросом.
- Парсит stdout как JSON.
- Проверяет наличие полей `answer` (строка) и `tool_calls` (пустой список).

### Timeline

1. Создать `plans/task-1.md` (план).
2. Создать `.env.agent.secret` с API-ключом.
3. Создать `agent.py`.
4. Создать `AGENT.md` с документацией.
5. Создать тест `tests/test_agent.py`.
6. Запустить тест, убедиться в прохождении.
