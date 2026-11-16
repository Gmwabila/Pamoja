# PAMOJA on your iPhone — Neon + Render

This package prepares PAMOJA for a development deployment. It does not itself create a GitHub repository or a Render service, publish a live URL, or copy your Mac's data. Your existing Neon project is named **pamoja**; reuse it, separate from AFCON USA.

## 1. Apply the deployment update

Stop Django with **Control+C**. Download and unzip `PAMOJA_Deploy.zip` in Downloads. Do not replace your existing project folder.

```bash
python3 ~/Downloads/PAMOJA_Deploy/apply_update.py /Users/gloirembo/Projects/pamoja
cd /Users/gloirembo/Projects/pamoja
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py check
```

The updater backs up changed files. It adds deployment settings and dependencies while preserving `db.sqlite3`, your environment, and any `.env` file. Without a DATABASE_URL environment variable, your Mac continues using SQLite.

## 2. Make a separate GitHub repository

In GitHub, choose **New repository**. Name it **pamoja**, choose **Private**, and leave the README, gitignore, and license initialization options off because the source already exists.

In your existing Mac project:

```bash
cd /Users/gloirembo/Projects/pamoja
git init -b main
git add .gitignore .python-version requirements.txt manage.py config core build.sh render.yaml start.sh README.md PROJECT_PLAN.md DEPLOYMENT.md
git status
git commit -m "Prepare PAMOJA for Neon and Render"
```

Use the actual remote URL and push commands GitHub shows under **Push an existing repository**. Do not guess the owner name or reuse AFCON's remote. If `git remote -v` already lists a remote, check it before changing it.

The ignore rules exclude `.venv`, `.env`, SQLite files, source/database backups, generated static files, and logs. Never commit `pamoja_data.json`, database backups, or connection strings.

## 3. Keep your saved account and tasks

Use the existing **pamoja** Neon project. It must have its own database, separate from AFCON. Before anyone signs up on the online site, copy your local data:

1. In Neon **Connect**, select the production branch and `neondb` database.
2. Turn **connection pooling off** and copy the direct connection string. Keep it private.
3. Stop the local Django server and run:

```bash
cd /Users/gloirembo/Projects/pamoja
source .venv/bin/activate
python manage.py move_to_neon
```

Paste the direct connection string at the hidden Terminal prompt, then press Enter. The paste will not appear on screen. This command backs up SQLite, creates the Django schema in Neon, and copies groups, accounts, profiles, and tasks. It preserves password hashes so your current password still works. It checks counts and refuses to overwrite a target that already has saved data or unrelated application tables.

The transfer leaves local data unchanged and writes no connection-string file. Keep the existing JSON/SQLite backups outside the Git repository. If the command reports a failure, share only the non-secret error text. Do not reset or delete the Neon project to retry.

The transfer routines were tested locally; a live Neon connection and the account/task counts must still be verified during deployment. Test schema changes on a Neon development branch before applying future migrations to production.

## 4. Deploy on Render

Create a **Web Service** using the **pamoja** GitHub repository. Do not create another Postgres database on Render; Neon is the database.

| Setting | Value |
| --- | --- |
| Language/runtime | Python |
| Branch | main |
| Root directory | blank, if manage.py is at repository root |
| Build command | `bash build.sh` |
| Start command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120` |
| Health check | `/healthz/` |
| Instance type | Free for development |
| Auto deploy | On Commit |

You can instead create a Blueprint from `render.yaml`; it supplies the same configuration. Never set up both routes as separate services.

Set these environment variables **in Render**:

| Name | Private value |
| --- | --- |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | Generate a random secret in Render; keep it stable across deployments |
| `DATABASE_URL` | Neon's **pooled** connection string, with SSL required |
| `DATABASE_URL_UNPOOLED` | Neon's **direct** connection string for the same branch/database, with SSL required |

Render supplies `RENDER_EXTERNAL_HOSTNAME`; settings use it for allowed hosts and CSRF origins. On Render, Django trusts the platform's forwarded HTTPS header. For a custom domain later, explicitly add its hostname and HTTPS origin using `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.

The build collects static files and runs migrations against the direct connection. WhiteNoise serves the styling, icons, JavaScript, and manifest. Gunicorn serves Django. Production refuses to start with the local development key or without a PostgreSQL URL; it never silently uses ephemeral SQLite.

Free Render services sleep after inactivity, so the first load can take roughly a minute. This deployment is for building and testing; broader public launch features such as verified email and password recovery remain future work.

## 5. Verify and install on iPhone

Wait for Render's **Live** status and copy its actual HTTPS URL. On your Mac, verify `/healthz/`, login with the migrated account, and check the saved tasks and preferences. Confirm styling/icons load and that another account cannot view yours.

On iPhone, open that HTTPS URL in Safari → **Share → Add to Home Screen → Add**. Launch **PAMOJA** from its icon, log in, create a task, and refresh to verify persistence. Your Mac can be off. The app requires internet; push notifications and offline task editing are not implemented.

## Updates tomorrow

Change code in `/Users/gloirembo/Projects/pamoja`, run checks, commit, and push to the linked main branch. Render redeploys the code while Neon retains the online data. Your Home Screen icon uses the same URL and does not need reinstalling.

Your local SQLite and online Neon databases are separate after the one-time copy. Do not rerun the initial import into a live database. Plan and test later schema migrations on a development branch, and treat the online site as the source for ongoing phone data.

## References

- https://neon.com/docs/guides/django
- https://neon.com/docs/connect/connection-pooling
- https://render.com/docs/deploy-django
- https://render.com/docs/free
- https://render.com/docs/python-version
