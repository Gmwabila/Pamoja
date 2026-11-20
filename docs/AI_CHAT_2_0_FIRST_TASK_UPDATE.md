# PAMOJA AI Chat 2.0 — App Guide + First Task Flow

This update extends the existing Django/Gemini implementation. It does not
change the database schema, delete accounts, or access production credentials.

## What changed

- `core/app_knowledge.py` — curated, code-verified app guide injected into
  Gemini's system instructions; maintain as features change.
- `core/ai_chat.py` — instructs Gemini to help users navigate PAMOJA and to
  be accurate about its inability to save tasks directly.
- `core/templates/core/chat.html` — **How do I use PAMOJA?** and
  **Create a task** quick actions; a small guided task form.
- `core/views.py` — pre-fills the existing task form from validated GET
  parameters, without saving. Only the existing POST Save task persists data.
- `core/tests/test_ai_task_guide.py` — checks the guide, safe prefill,
  and explicit-save behavior.

## How to use

1. Open AI Chat and tap **Create a task**.
2. Enter a task title, Space, due date, and priority.
3. Tap **Review task**. PAMOJA opens the existing Create Task page.
4. Optionally set a due time, adjust any field, and tap **Save task**.
5. The task is saved only after the final click. Canceling leaves no new task.

The assistant does not yet autonomously create tasks from free-form chat
messages. Future work: structured task proposals, server-side validation,
explicit confirmation and idempotent task-creation actions.

## Test and deploy

```bash
cd /Users/gloirembo/Projects/pamoja
source .venv/bin/activate
python manage.py check
python manage.py test core.tests.test_ai_task_guide core.tests.test_ai_chat
python manage.py test
python manage.py makemigrations --check --dry-run
```

Test manually on Safari/iPhone, especially the review and Save task flow.
Do not deploy if tests fail. After verification, commit and push to GitHub.
