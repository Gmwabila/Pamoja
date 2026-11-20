# PAMOJA AI Chat 2.0 — Conversational Task Proposals

**Status:** Local-testing candidate. Do not deploy before tests and review.

## What changed

- Gemini receives the user's current local date/time zone and PAMOJA's real Space keys.
- A `propose_task` Gemini function declaration lets the assistant prepare a structured task proposal from natural language.
- A new `AITaskProposal` model stores a proposal linked to the assistant's chat message. **This is not a Planner task.**
- The chat displays an editable review card (title, Space, date, optional time, Normal/High priority).
- Only an authenticated, CSRF-protected `POST` to the confirmation endpoint creates a real `Task` using the existing Django `TaskForm` validation.
- The endpoint enforces ownership and makes repeat confirmation requests idempotent. Saved proposals remain visible in conversation history.
- General chat, chat history, usage limits, existing quick actions and Planner remain intact.

## Workflow

1. User: “Create a task to study Python tomorrow.”
2. Gemini calls `propose_task` with structured details; Django validates the model output.
3. PAMOJA stores an unsaved proposal and shows an editable preview.
4. User reviews the fields and selects **Save to Planner**.
5. Django validates again and saves a Task under the authenticated user. The card then displays **Open Planner**.

If the user has not given a date, the assistant is instructed to ask a follow-up question. Model behavior should be tested with real Gemini requests; a function call is not guaranteed for every phrasing.

## Security and data model

- No task is saved during the Gemini API call.
- A proposal belongs to the conversation's user; another account cannot read or save it.
- The confirmation endpoint requires login, CSRF protection, and POST.
- Task fields are validated server-side; model-generated fields are untrusted.
- `select_for_update` and `saved_at` prevent sequential or concurrent duplicate saves on PostgreSQL.
- Deleting a chat deletes its proposals, **not** Planner tasks already saved.
- Database migration: `core/migrations/0017_aitaskproposal.py` (adds one table).

## Local test commands

```bash
cd /Users/gloirembo/Projects/pamoja
source .venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.tests.test_ai_conversational_tasks core.tests.test_ai_chat core.tests.test_ai_task_guide
python manage.py test
```

Before `migrate`, check the database configured in `.env`. If `DATABASE_URL` points to production Neon, **do not run local migrations against production**. Use a local SQLite or separate Neon development database, and deploy the migration through your established Render build process after tests pass.

```bash
python manage.py shell -c "from django.conf import settings; d=settings.DATABASES['default']; print('Engine:',d['ENGINE']); print('Host:',d.get('HOST','local')); print('Database:',d.get('NAME'))"
python manage.py migrate
python manage.py runserver
```

Test in `/chat/` with the following: “Help me create a task to study Python tomorrow”; verify that **no** Planner task exists before pressing Save, then save and check Planner. Try changing the Space or priority before saving. Refresh the conversation and verify that the proposal remains visible.

## Limitations

- Gemini may ask a clarifying question or return text instead of calling the function; the user can use the existing manual Create a task action as a fallback.
- Only **creation** is implemented. Editing or deleting existing Planner tasks via AI is not supported.
- This patch has been statically checked for Python and JavaScript syntax; Django tests and actual Gemini tool-calling must run in the user's configured local environment before deployment.
