# PAMOJA — product decisions and build plan

## Agreed direction

- Name: **PAMOJA**. Meaning: *together* in Swahili. **AKILI** is reserved for another project.
- Purpose: a personal life assistant anyone can sign up for and adapt to their preferences.
- Platform: responsive Django web app first; installable on the iPhone Home Screen after HTTPS deployment. A native Flutter app is optional later.
- Visual identity: **Forest Green & Cream**. Use the original Home Dashboard v1.0 structure as the reference across pages.
- Home: greeting, daily progress, Your Spaces, Today's Tasks, Upcoming Tasks (next seven days), and assistant suggestions. Sensible defaults with user customization.
- Example onboarding preferences: Daily Planning, Career & Jobs, Fitness; English; reminders enabled. These are editable preferences, not a fixed user persona.
- Other users can select other combinations, including Education and Sports.
- AI: permitted personal context; proposed changes reviewed before saving; no external account access without an authorized connection.

## Page map

| Page | Route | Current state |
| --- | --- | --- |
| Welcome | `/` | Implemented |
| Sign Up | `/signup/` | Local signup implemented; email verification later |
| Login | `/login/` | Implemented; recovery later |
| Personalization | `/onboarding/` | Saved spaces, goal, time zone, in-app reminders |
| Home | `/dashboard/` | Saved tasks, progress, space ordering, next-seven-day upcoming list, static tip |
| AI Chat | `/chat/` | Honest placeholder; no live AI |
| Planner | `/planner/` | Task management and filters; calendar/recurrence later |
| Profile | `/profile/` | Account summary, preference access, logout |

## Milestones

1. **Local foundation — this package.** Test accounts, onboarding, dashboard, task saving, empty states, mobile layout, and account isolation. Review the look on the user's Mac.
2. **AI connection.** Select a provider and budget; keep credentials on the server; add chat history, context controls, validated task proposals, explicit confirmation, usage limits, and failure recovery. No fake model replies.
3. **Public-beta foundation.** Configure PostgreSQL, production hosting, HTTPS/static assets, verified email, password recovery, abuse controls, backups, data deletion/privacy controls, and deployment checks. Test home-screen installation on iPhone.
4. **Reminders and deeper personalization.** Configurable notification delivery and quiet hours; broader dashboard arrangement; translations validated with native speakers.
5. **Useful modules.** Application tracking and career assistance; workout logging and plans; assignment tracking; verified sports data and optional result tracking. Build each around real user feedback.

## Review before the next milestone

Local user checks confirmed registration, personalization, task creation, date editing, completion, and today's progress. A native Safari time-input issue prevented task submission; a plain text field allowed saving. This update replaces it with hour/minute/AM-PM menus and retains server validation. The brand is now PAMOJA, always uppercase, with no AI suffix. The Upcoming Tasks list addresses the user's difficulty finding tomorrow's tasks from Home.

Next, check the new controls in Safari on the Mac, confirm completion after refreshing, and review upcoming tasks. The assistant tested the backend and rendered forms; Safari testing is still a user-device check. Then move to live AI integration after the user reviews the update.

## Current deployment work

The user wants PAMOJA available on their iPhone while development continues. Their existing Neon project is `pamoja` in Ohio. Local data was verified as one account and five tasks before subsequent task testing; actual transfer counts must be read at transfer time. Production configuration, Render build/start settings, and a one-time guarded data-copy command are included. They have not yet been verified on the live service. A separate GitHub repository and Render service still need to be connected and deployed. Keep the current app and local database; do not replace the project directory.
