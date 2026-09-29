# Pocket Job Desk

A phone-first version of the [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) workflow that runs inside Claude.

**Open it:** https://claude.ai/artifact/YNyKKZNHnoiYWrFYFCYYfw (private to its owner)

## What it does

| Tab | Matches ai-job-search | What happens |
|---|---|---|
| Find | `/scrape` + `/rank` | **Find jobs for me**: one tap searches every target role from your profile, in your location and/or remote, across Indeed, Dice and ZipRecruiter. It dedupes the results, marks jobs you haven't seen before, and has Claude rank them against your profile. A custom search is also available |
| Apply | `/apply` | Eligibility, language and location gates, then the 5-dimension fit score (30/25/15/30 weights, same thresholds). After that: a drafter pass, a hiring-manager reviewer pass, and a final CV + cover letter. Download as Word or copy the text. Flags stretch claims so you can keep, soften or drop each one. Answers application-form questions within a character limit |
| Tracker | `/outcome` | Same status vocabulary (`drafted`, `applied`, `interview`, `offer`, `hired`, `rejected`, `no_response`, `offer_declined`, `withdrawn`, plus `saved`). Shows deadline warnings and days quiet, logs follow-ups, and drafts follow-up emails |
| Interview | `/interview` | Prep pack (STAR answers built only from your real experience, tough questions, questions to ask) and a practice interview |
| Profile | `/setup` | Upload a resume (PDF or Word) and/or import from Indeed; the sources merge. Then a conversational interview (the original Path C, one question at a time, skipping anything already known) fills in the rest. Your profile is the only source of facts |

## How it works

- It's a single HTML file published as a claude.ai Artifact. There's no server and no API key.
- AI calls use the viewer's own Claude plan (`sample` capability).
- Job boards are called through the viewer's connectors (`mcp` capability).
- Profile and applications are stored privately per user (`db` capability, `data/users/<id>/`). If that isn't available, they fall back to `localStorage`.
- Word files are built in the browser with `docx@9.5.1` from jsDelivr and saved through the `downloads` capability.

## Differences from the original

- It can't browse the web, so company facts come only from the posting text. The prompts forbid unverified company claims rather than verifying them.
- Output is Word/plain text instead of LaTeX PDFs, because a phone can't run a LaTeX compiler.
- The job boards are US ones (Indeed, Dice, ZipRecruiter) instead of the Danish portals.

## Updating

Edit `index.html`, then republish it to the same artifact URL from a Claude Code session.

## Sharing with someone else

Each person needs their own Claude account (a paid plan is recommended, because drafting uses a lot of usage). They also need their own Indeed / Dice / ZipRecruiter connectors added in claude.ai Settings → Connectors.

Share the artifact from its **Share** menu and invite them by email as an **Editor**. Each viewer's data lives in their own private `data/users/<id>/` subtree; nobody else can read it, the owner included. If they're invited at a level that can't write (Viewer or Commenter), the app saves on their device instead and tells them to ask for Editor access.
