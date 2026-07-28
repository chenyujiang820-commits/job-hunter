# Domestic Job Search

Use this Codex-native skill for manual domestic job-search work. It is a readable workflow contract and does not depend on Claude Code slash-command execution.

## Workflow

```text
scrape -> inspect/cache new jobs -> rank -> user selects job -> apply -> local archive
```

### `scrape`

Manually inspect public, read-only Zhilian search/detail pages for junior product-manager roles in Zhejiang. Cache only newly inspected job data locally. Stop on login, CAPTCHA, SMS verification, or anti-bot pages. Do not submit, upload, chat, reply, or perform any platform write.

### `rank`

Read the confirmed local candidate profile and cached jobs. Apply hard exclusions first, then rank by location tier, product direction and career fit, qualifications, and other reference dimensions. Show salary as a ranking reference only and make risk flags visible.

### `apply`

Accept exactly one user-selected job. Confirm the profile and user approval before drafting. Produce both a tailored resume and cover letter for that selected job only. Validate facts, obtain reviewer assessment and user approval, then generate DOCX and PDF locally. Do not upload or submit.

### `outcome`

Record a manually reported application outcome in local tracker state. Never call a platform write operation or send external messages.

## Operating Rules

- Prioritize Lishui, then Hangzhou/Jinhua, then other Zhejiang cities.
- Hard-exclude labor dispatch and outsourcing; there is no salary floor.
- Candidate sources are PDF, DOCX, Markdown, and plain text under `documents/`.
- Keep candidate data, generated materials, tracker state, scraper state, and email contents local.

Read the references before changing profile or evaluation behavior.

