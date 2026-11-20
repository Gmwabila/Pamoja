# PAMOJA

**Together, every step of the way.**

Pamoja means *together* in Swahili. A mobile-first personal planning web app designed for multiple users, with Forest Green & Cream branding. This is milestone 1: a runnable local Django foundation, not a deployed public beta.

## Start on your Mac

**Already have PAMOJA running?** Use the update instructions in the outer `PAMOJA_Deploy` folder. Do not replace your entire project folder; the updater copies only the changed source files and keeps your database and environment.

For a fresh installation:

1. Download `PAMOJA_Deploy.zip` and unzip it. Open `PAMOJA_Deploy`; it contains the source folder named `pamoja`.
2. Move `pamoja` into `/Users/gloirembo/Projects/`.
3. Open Terminal and run:

```bash
cd /Users/gloirembo/Projects/pamoja
bash start.sh
```

4. Open **http://127.0.0.1:8000/**. Choose **Find your rhythm**, create an account, select your spaces, and add a task. There are no pre-made accounts or sample tasks.
5. Keep Terminal running while using the app. Press **Control+C** to stop. Run the same commands to start it again; your data stays saved.

The launcher looks for Python 3.10–3.14. If none is available, install Python 3.13 from https://www.python.org/downloads/ and run the launcher again. Django's Python compatibility reference: https://docs.djangoproject.com/en/5.2/releases/5.2/.

To open the code in VS Code: **File → Open Folder → `/Users/gloirembo/Projects/pamoja`**. If you have installed the `code` command, run `code /Users/gloirembo/Projects/pamoja`.

## What works now

- Welcome, sign up, email-based login, and POST-only logout.
- Separate accounts, password hashing, password validation, and CSRF-protected forms.
- Personalization: spaces, optional goal, time zone, and in-app reminder preference.
- Original Home structure: greeting, daily progress, Your Spaces, Today's Tasks, and a clearly labeled static planning tip.
- Saved dashboard space order, using up/down controls. Edit preferences to hide spaces without deleting associated tasks.
- Tasks: create, edit, complete, reopen, and delete. Planner supports space filters and a completed-task option.
- Each user's task queries and changes are restricted to their own account.
- Daily progress respects the user's time zone. An overdue-task banner appears when in-app reminders are enabled.
- Home shows up to five unfinished upcoming tasks in the next seven days, sorted by date and time, with a link to the full Planner. These do not affect today's progress.
- Due time uses Hour, Minute, and AM/PM select menus, including correct noon/midnight conversion. No native time input is used. Leave all three blank for a task without a time.
- Brand name is **PAMOJA**, including the header, default browser title, and install manifest.
- Profile page and a clearly labeled future AI Chat page.
- Web app manifest, home-screen icons, and a minimal service worker that does not cache private pages.

Education and Sports are available as task categories. Career and Fitness also group tasks at this stage. Dedicated job tracking, workouts, live sports research, and parlay results are not implemented.

## What comes next

See `PROJECT_PLAN.md` for the agreed product direction and milestone sequence. Live AI, AI action approval cards, chat history, full dashboard section customization, translated interfaces, email verification, password recovery, push notifications, and public hosting are not yet implemented.

This development build uses SQLite so you can run it without cloud accounts or billing. Production uses Neon PostgreSQL through environment variables. See `DEPLOYMENT.md` for the deployment and data-copy steps. Do not deploy Django's development server publicly.

## On your iPhone

The interface is responsive. Home-screen installation on your iPhone follows the HTTPS deployment milestone. A laptop's `127.0.0.1` address is not reachable from your phone. No live public URL is included in this package.

After HTTPS deployment: open PAMOJA in Safari → Share → Add to Home Screen. The manifest requests standalone display. There is no offline task editing or push notification delivery in this milestone.

## Development

```bash
cd /Users/gloirembo/Projects/pamoja
source .venv/bin/activate
python manage.py test
python manage.py check
python manage.py createsuperuser
```

The admin is at `/admin/`. Data is stored in `db.sqlite3`; keep it private, backed up, and outside Git. Do not delete it to restart the app. The zip excludes runtime data, environments, secrets, and caches.

The default settings support localhost development only. `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, and `DJANGO_ALLOWED_HOSTS` are environment settings for future deployment. This package now includes Neon database settings, WhiteNoise static delivery, Gunicorn startup, and Render build configuration. Account connections, data transfer, GitHub publication, live deployment validation, email delivery, rate limiting, and privacy/data controls still need completion. This package does not claim public-launch readiness.

## Structure

| Path | Purpose |
| --- | --- |
| `config/` | Django settings and top-level routes |
| `core/models.py` | Accounts, preferences, tasks |
| `core/forms.py` | Validated account, preference, and task forms |
| `core/views.py` | Owner-scoped account and task workflows |
| `core/templates/` | Responsive pages |
| `core/static/core/` | Styling, small interactions, PWA assets |
| `core/tests/` | Account flow, task lifecycle, isolation, time-zone and CSRF checks |

All styling and assets are local; no third-party font or CDN is required.

## Update verification

The workflow suite checks task saving with the time menus, editing existing times, clearing times, noon/midnight conversion, partial-input errors, account isolation, upcoming date boundaries, sorting, and today's progress. Run `python manage.py test` after applying an update. Native Safari behavior still needs a check on the user's Mac; no claim of a Safari browser test is made by these server tests.

## Neon and Render deployment

See `DEPLOYMENT.md`. Apply the deployment update with its updater, install requirements in the existing environment, copy the local account/tasks with `python manage.py move_to_neon`, and deploy the GitHub repository on Render. Database connection strings and the production secret stay out of source control.

## Development Milestones

### Notifications 3.0 — November 19, 2026

Successfully implemented and deployed PAMOJA's push notification system using Django, PostgreSQL, Web Push, and Render Cron Jobs.

- Customizable daily planning reminders
- Time-zone-aware scheduling
- Browser and iPhone PWA push notifications
- Duplicate delivery prevention
- 84 automated tests, with 82 passing and 2 skipped
- Successfully verified notification delivery on an iPhone lock screen

**[Read the Notifications 3.0 Launch Report](docs/PAMOJA_AI_Notifications_3_0_Launch_Report.pdf)**
