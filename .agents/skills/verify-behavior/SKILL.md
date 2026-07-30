---
name: verify-behavior
description: Launch Oz cloud agents to reproduce bugs or verify features/fixes, capturing video with Oz's native computer-use recording tools plus keyframe screenshots. Chooses Chrome/Puppeteer browser automation or desktop computer use, and for multi-story features fans out parallel story workers. Use whenever triage needs visual reproduction, implementation needs behavioral proof, review needs interactive confirmation, or any factory stage asks to verify UI/app behavior.
---

# Verify behavior

Prove or disprove visible product behavior for **bugs and greenfield features**. Other agents (triage, implementation, review) invoke this instead of driving the UI themselves.

Default evidence: **video** of the critical path, captured with Oz's **native computer-use recording tools**, plus keyframe screenshots. Screenshots alone are never sufficient unless a `start_recording` attempt actually failed — see [Video capture](#video-capture-native-oz-recording).

## Modes

- **`reproduce`** — show whether a reported bug still happens on baseline (usually default branch). Used mainly from triage.
- **`verify`** — show whether the implemented change matches expected behavior. Covers **features and fixes**. Used from implementation/review.

Infer mode if unnamed: issue-only → `reproduce`; implementation/PR branch → `verify`.

## Interaction channel

The verifying agent chooses. Parents may hint; do not hard-code unless the user requires it.

| Channel | Use when |
|---|---|
| **Browser use** (Chrome + Puppeteer MCP) | Web app/SPA; flow stays in-browser; need precise DOM interaction |
| **Computer use** (Oz desktop sandbox) | Desktop/mobile native; OS dialogs; native handoffs/login; windowing; Puppeteer unavailable; clearer full-desktop video; parallel isolated story sessions |

Prefer browser use for pure web flows. Prefer computer use for native surfaces and native boundaries. If browser use hits a native wall mid-flow, switch rather than false-blocking. Record `Channel: browser-use | computer-use | hybrid` plus a one-line why.

## Video capture (native Oz recording)

Oz computer use has **built-in video recording**. Use it. Do not build your own capture pipeline.

| Do | Don't |
|---|---|
| Call the `start_recording` tool before the critical path | Shell out to `ffmpeg`, `x11grab`, `avfoundation`, `wf-recorder`, `screencapture`, Playwright video, or any external recorder |
| Call `stop_recording` with the returned `recording_id` when the path is done | Hand-roll frame stitching, GIF conversion, or screen-scraping loops |
| Let the platform publish the recording as a run artifact | `upload_artifact` the video yourself — the platform already attaches it |
| Tune only what the tool exposes (e.g. `summary`, `description`) | Pick codecs, frame rates, or encoder flags manually |

Rules:

1. When the run has computer use enabled, **`start_recording` before** the first interaction of the critical path.
2. Keep the whole assigned story/repro path inside one recording when practical; short and focused beats long and idle.
3. **`stop_recording`** once the path completes, before writing the report, so the artifact finalizes and publishes.
4. Screenshots remain required as keyframes and are uploaded explicitly with `upload_artifact`.
5. The recording appears on the Oz run automatically. Reference it in the report; do not re-upload it.

If `start_recording` returns an error (feature unavailable, no display, recorder failed):

- Quote the **actual error text** in the report.
- Then, and only then, fall back to screenshots-only and label the status accordingly.
- Never claim video was unavailable without an attempted `start_recording` and its error.

A verification that never called `start_recording` on a computer-use-enabled run is **incomplete**, not verified.

## When to use / skip

**Use** for UI/browser/desktop/mobile/interactive behavior where visual proof helps.

**Skip** pure backend/CI/text-only work, or when required credentials/state are unavailable (report the blocker).

If this skill file is missing, parents continue without visual verification.

## PRODUCT.md coverage

When `PRODUCT.md` exists, it is the **primary source of user stories and acceptance criteria**:

1. Read it (parent path, `specs/<issue-slug>/PRODUCT.md`, or issue/PR links).
2. Build a checklist of exercisable user-facing stories/flows/criteria. Issue comments refine when newer.
3. Coverage:
   - `reproduce`: stories tied to the failure + baseline path to reach it
   - `verify` sole worker: all in-scope stories (not one ad-hoc happy path)
   - `verify` story worker: only the assigned story
4. Non-goals stay out of scope unless the issue expands them.
5. No PRODUCT.md → derive stories from the issue.

## Parent workflow

Parents orchestrate; they should not click through locally unless asked.

1. Collect issue/PR context, change type (feature/fix/both), mode, branch/ref, setup commands/URLs, surface hints, and PRODUCT.md path/excerpts.
2. Skip if not visually observable.
3. Launch verification (single worker or story fan-out below). Enable computer use on runs so native fallback/sessions exist; workers still pick browser use when better.
4. Wait and aggregate statuses: confirmed / partially confirmed / not reproduced / verified / partially verified / not verified / blocked.
5. Fold evidence into triage comments, PR bodies, or `review.json`. Do not claim behavioral verification without evidence or an explicit blocker.

### Parallel story fan-out (`verify`)

Default for multi-story features when stories are independent and isolation is possible:

1. Split PRODUCT.md/issue into key independent stories (merge tiny coupled criteria).
2. Launch one remote child per story in one batch, `remote.computer_use_enabled: true`.
3. Bound to ~**4–6** workers; second wave if needed. No unbounded fan-out.
4. Each worker gets shared setup + **one** assigned story and its own artifact dir.
5. Aggregate per-story pass/fail/blocked/not-run + evidence.

Stay single-worker for `reproduce`, one story, tightly sequential stories, or scarce credentials/env.

**Single path:**

```text
summary: Launching Oz cloud agent to <reproduce|verify> behavior.
remote.computer_use_enabled: true
agent_run_configs:
- name: "verify-behavior-primary"
  prompt: mode, issue/PR, branch, setup, single story or repro path
base_prompt: shared child prompt below
```

**Feature fan-out:**

```text
summary: Parallel Oz verification agents for key PRODUCT.md stories.
remote.computer_use_enabled: true
agent_run_configs:
- name: "verify-story-1-slug"
  prompt: verify + story 1 only + shared context
- name: "verify-story-2-slug"
  prompt: verify + story 2 only + shared context
base_prompt: shared child prompt below
```

Omit `model_id`/environment unless specified. Never put secrets in prompts. Prefer platform-equivalent cloud launch if `run_agents` is unavailable.

## Shared child prompt

```text
You are an Oz cloud verification agent.

Goal: exercise the assigned bug path or feature story; choose browser use vs computer use; capture video with Oz's native recording tools + keyframe screenshots; report evidence, not opinions.

Mode: <reproduce | verify>
Work shape: <single-path | assigned-story-worker>
Assigned story: <one story/criterion, or full checklist if sole worker>
Change type: <feature | bug-fix | both | unknown>
Issue/PR, PRODUCT.md/TECH.md paths+excerpts, expected/reported behavior, repro steps, branch/ref, app setup, surface hint, constraints: <fill in>

PRODUCT.md (if present): build the story checklist; cover only your assignment (or full in-scope list if sole verify worker). Prefer newer issue decisions on conflicts.

Channel: prefer Puppeteer/Chrome MCP for in-browser web; computer use for native/OS/multi-surface. Switch if blocked. Record channel + why.

Setup: confirm env/tools; checkout assigned ref (verify=implementation/PR head; reproduce=baseline); start app from docs; smallest path to UI; block with logs/screenshots if startup fails.

Video: call the native `start_recording` tool before the critical path and `stop_recording` after it. NEVER use ffmpeg/x11grab/avfoundation/Playwright video or any external recorder. Do not upload the recording yourself; the platform publishes it to the run. Only report "video unavailable" if `start_recording` actually failed, and quote its error.

Evidence dir: ~/verify-behavior-<issue>-<story-or-primary>
- Ordered keyframe screenshots covering each criterion
- manifest.md: file, time, channel, story, visible state, action, outcome support
- Upload screenshots/manifest via upload_artifact; report paths
- Never include secrets/tokens/credentialed URLs

Flow:
0. start_recording (computer-use runs) before touching the UI
1. Checklist before ad-hoc exploration
2. Baseline state + evidence
3. Exact reporter steps when relevant, then remaining assigned stories
4. reproduce: stop when bug appears; note unreached stories
5. verify: prove assigned feature story/checklist; greenfield is first-class; if also a fix, show failure is gone
6. ≤2 targeted extra variations if inconclusive and supported by spec/issue
7. stop_recording before writing the report
8. No product code changes; story workers do not re-fan-out

Report:
Verification summary: mode, work shape, channel, issue/PR, change type, PRODUCT.md, assigned story, status, branch/ref, setup, tools
User stories covered: <item>: pass|fail|blocked|not run — note
Steps / Evidence (video, screenshots, Oz run link) / Findings / Next step

Oz run links must use https://oz.warp.dev/runs/<run-id> (or https://oz.staging.warp.dev/runs/<run-id> on staging). Never post app.warp.dev or /run/ (singular) links.
```

### Mode add-ons

**reproduce:** match reporter steps/environment; do not implement or verify a change. Statuses: confirmed | partially confirmed | not reproduced | blocked.

**verify:** features and fixes; PRODUCT.md stories drive coverage; story workers own one story; sole worker covers all in-scope stories; include original repro path when fixing a bug. Statuses: verified | partially verified | not verified | blocked.

**orchestrator:** list key independent stories → default parallel computer-use-capable workers → aggregate; do not claim full feature verify if material stories did not run.

## Success / parent summary

Success means: clear mode status; channel choice; PRODUCT.md story checklist outcomes when present; fan-out or explicit serialize reason for multi-story features; **native recording artifact on the Oz run** (or a quoted `start_recording` error); **evidence posted on the GitHub issue and PR** when they are in scope; repeatable steps/setup; no secrets.

```text
Behavior verification:
- Mode / change type / channel(s) / fan-out
- Status / issue-PR
- PRODUCT.md stories: n passed / failed / blocked / not run
- Evidence / findings / next step
```


## Posting evidence back to GitHub

When this skill is invoked from a factory parent that has a GitHub issue/PR, evidence must land in **three** places:

1. **Oz run artifacts** — the native recording publishes automatically; upload screenshots/manifest with `upload_artifact`.
2. **GitHub issue** — comment with the evidence files **attached** as binary assets.
3. **GitHub PR** — when a PR exists, attach the same video (at minimum) to the PR body or a PR comment, not just a pointer to the issue.

### How to post to GitHub

Attach files with `gh` so they become real GitHub assets (`user-attachments` URLs), not just remote links. A comment that only names filenames does not count as attached evidence.

The native recording is finalized on the Oz run. To attach it to GitHub, download it to the workspace first (Oz artifact download or the local recording path reported by `stop_recording`), then attach that file.

```bash
# RECORDING=<local path to the native recording reported by stop_recording
#            or downloaded from the Oz run artifacts>
gh issue comment <N> --repo <owner/repo> \
  --body "$(cat <<'EOF'
## Behavior verification evidence
- Mode: verify
- Status: verified | partially verified | not verified | blocked
- Channel: computer-use | browser-use | hybrid
- Oz verify run: https://oz.warp.dev/runs/<verify-run-id>
- Oz implement run: https://oz.warp.dev/runs/<parent-run-id>  # if applicable

### Video
Native Oz computer-use recording of the critical path, attached below.

### Keyframes
Screenshots attached for idle, action, success/failure states.
EOF
)" \
  --attach "$RECORDING" \
  --attach ~/verify-behavior-<issue>/01-idle.png \
  --attach ~/verify-behavior-<issue>/02-after-action.png
```

Mirror the same attachment onto the PR when one exists:

```bash
gh pr comment <PR> --repo <owner/repo> \
  --body "Behavior verification video for #<N> — Oz verify run: https://oz.warp.dev/runs/<verify-run-id>" \
  --attach "$RECORDING"
```

If `--attach` is unavailable or fails, upload via `gh api` to the issue comments/assets endpoint or include durable Oz artifact URLs **and** note the upload failure.

Rules:

- Video first, from the native recorder. Never a self-produced ffmpeg file.
- Comment must include the Oz run URL using `https://oz.warp.dev/runs/<id>` (never `app.warp.dev/run/`).
- Do not claim verification complete until the Oz recording exists **and** evidence has been posted to the issue **and** the PR (or an explicit blocker explains why posting failed).
- Parents (implementation/triage/review) are responsible for ensuring this handoff happens if the verify child cannot comment itself.

## Guardrails

- Cloud verification subagent over local clicking
- Features are first-class; not bug-fix-only
- PRODUCT.md defines stories when present
- Multi-story verify defaults to parallel workers
- Video via native `start_recording`/`stop_recording`; screenshots are keyframes, not a substitute
- Never shell out to ffmpeg or any external screen recorder
- When a GitHub issue/PR is in scope, attach evidence to both and include Oz run links
- No claim of verification without the Oz recording + GitHub evidence posts (or a quoted `start_recording` failure)
- Bounded batches; no secret leakage; no irreversible actions without human confirmation

Optional `verify-behavior-local` may specialize setup/surface/fan-out limits only—not weaken evidence, privacy, or reporting.
