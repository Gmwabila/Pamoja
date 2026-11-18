# PAMOJA AI — AI Chat Feature Release Report

**Release date:** November 18, 2026  
**Project:** PAMOJA AI  
**Repository:** https://github.com/Gmwabila/Pamoja  
**Deployment:** https://pamoja-19v9.onrender.com  
**Release stage:** Deployed to Render; Gemini Free-tier **private testing**, not an unrestricted public AI Chat launch.

## 1. Executive summary

PAMOJA AI now includes a mobile-friendly, account-based AI Chat experience integrated with Google's Gemini API. The implementation adds persistent conversations, multilingual interface support, conversation ownership controls, and database-backed request limits. The feature was developed in Django, tested locally and against an isolated Neon PostgreSQL testing database, committed to Git, and subsequently deployed to Render. A successful Render deployment was reported; a completed end-to-end live Gemini response and non-staff access check have not yet been documented in this report.

## 2. Features delivered

- **AI-powered conversations:** A Django backend sends user messages and recent conversation context to Gemini and returns generated responses.
- **Conversation history:** Signed-in users can list, open, and delete their saved conversations. User and model messages are stored in the application database.
- **Account isolation:** Conversation detail, deletion, and message submission enforce ownership checks; unauthenticated requests are protected.
- **Six-language interface:** English, French, Spanish, Lingala, Swahili, and Japanese, with translated UI and localized backend error messages.
- **Responsive chat interface:** Designed for PAMOJA's mobile-first web/PWA experience.
- **Personal-assistant instructions:** Supports planning, learning, careers, everyday questions, and general emotional support; explicitly avoids claiming access to the user's planner.
- **Private testing restriction:** A `PAMOJA_AI_TESTING_ONLY=true` environment setting was added to restrict sending AI messages to staff accounts while evaluating the Free tier. The restriction should be verified using a non-staff account on the deployed service.

## 3. Technology and architecture

| Layer | Implementation |
| --- | --- |
| Application | Python / Django |
| AI provider | Google Gemini API |
| Persistent data | Neon PostgreSQL in production; SQLite in local development |
| Hosting | Render |
| Version control | Git / GitHub |
| Internationalization | Django translation catalogs (`.po` / `.mo`) |
| Interface | Django template with mobile-responsive chat UI |

**Request flow:** Authenticated browser → Django AI Chat endpoint → authorization and rate-limit checks → Gemini API → persisted conversation/messages → response to browser.

**Main Django models:** `AIConversation`, `AIMessage`, `AIUsageLimit`, and `AIUsageGlobal`.

**AI Chat endpoints:**

| Route | Purpose |
| --- | --- |
| `/chat/` | Chat page |
| `/chat/message/` | Send message |
| `/chat/conversations/` | List conversations |
| `/chat/conversations/<conversation_id>/` | Retrieve one conversation |
| `/chat/conversations/<conversation_id>/delete/` | Delete one conversation |

## 4. Security and API quota protection

The implementation uses authenticated endpoints, user-specific conversation authorization, input validation, and server-side API credentials. The Gemini key is supplied through environment variables rather than embedded in frontend code.

| Scope | Application-enforced allowance |
| --- | ---: |
| Per user, fixed minute | 10 requests |
| Per user, UTC day | 40 requests |
| Global, rolling 60 seconds | 10 requests |
| Global, UTC day | 300 requests |

The global counters use database transactions and PostgreSQL row locking to coordinate concurrent requests. The rolling 60-second global limit reduces bursts that could cross calendar-minute boundaries. Requests denied by a global limit do not consume an individual's allowance.

**Known limits:** The global usage row is keyed by UTC day, so the rolling history does not span midnight; a short burst across midnight remains possible. The per-user minute limit is fixed-window rather than rolling. Google quotas are project/model-dependent and can also be affected by other consumers of the same Google project. Limits reduce the likelihood of upstream throttling but do not guarantee that Gemini will never return HTTP 429. Failed upstream attempts can still count against the application's limits.

## 5. Testing and verification

| Verification | Recorded outcome |
| --- | --- |
| Django system check | No issues reported |
| Local test suite | 75 discovered; **73 passed, 2 skipped**, 0 failures |
| PostgreSQL concurrency tests | **2 passed**, 0 failures, using isolated `pamoja-testing` Neon project |
| Migration consistency | `makemigrations --check --dry-run`: no changes detected |
| Deployment script | `build.sh` installs dependencies, collects static files, and runs Django migrations |
| Render deployment | User confirmed deployment succeeded and service is live |
| Live Gemini conversation | **Not yet documented as verified** |
| Non-staff private-test restriction | **Not yet documented as verified** |

The two locally skipped tests require PostgreSQL's `select_for_update` capability and were run separately against Neon.

## 6. Database migrations and release history

The AI Chat implementation introduced these Django migrations:

- `0005_aiconversation_aimessage.py` — conversations and messages
- `0006_aiusagelimit.py` — per-user usage tracking
- `0007_aiusageglobal.py` — global daily tracking
- `0008_aiusageglobal_minute_count_and_more.py` — global minute fields
- `0009_aiusageglobal_recent_request_times.py` — rolling-window timestamps

The main AI Chat feature was committed locally as `fb77f1a` (`feat: add multilingual AI chat with secure rate limiting`). A subsequent private-testing change was prepared and the resulting deployment was reported successful; its commit hash is not recorded here.

## 7. Free-tier privacy and release status

The current deployment uses the **Gemini API Free tier** for controlled testing. Under Google's Free-tier data-handling terms, prompts and responses may be used to improve Google products and may be subject to human review. For this reason, AI Chat should remain restricted to authorized testers, test prompts should avoid sensitive personal information, and the user-facing privacy notice should accurately explain processing and retention.

**Do not describe this as unrestricted public access to AI Chat.** The website is live, but the AI Chat feature is in private testing.

## 8. Remaining release checklist

- [ ] Confirm a staff account receives a successful Gemini response on the deployed site.
- [ ] Confirm conversation history persists after refresh and that deletion works.
- [ ] Confirm a non-staff account cannot send AI messages while `PAMOJA_AI_TESTING_ONLY=true`.
- [ ] Test the mobile chat layout and PWA navigation on iPhone.
- [ ] Check translated UI and backend errors on the deployed site.
- [ ] Review public privacy notice, retention/deletion behavior, and Google Free-tier processing disclosures.
- [ ] Consider fixing the global rolling-window UTC-midnight edge case before broader access.
- [ ] Review Google API quotas, project sharing, and billing/data-handling options before unrestricted public launch.

## 9. Developer commands

```bash
# From the PAMOJA project directory
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

For PostgreSQL-only concurrency tests, use the isolated testing database connection and run:

```bash
python manage.py test core.tests.test_ai_chat.AIConcurrentUsageTests
```

Never commit `GEMINI_API_KEY`, `DATABASE_URL`, or other secrets. Do not run test migrations against production data.

---

**Summary:** The AI Chat feature has been implemented, tested, committed, and deployed. The production website is live; AI Chat remains in controlled Free-tier testing until live functional, access-control, mobile, and privacy checks are complete.
