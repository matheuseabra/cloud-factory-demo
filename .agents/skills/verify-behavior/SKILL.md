---
name: verify-behavior
description: Launch Oz cloud agents to reproduce bugs or verify features/fixes with video or screenshot evidence. Chooses Chrome/Puppeteer browser automation or desktop computer use, and for multi-story features fans out parallel story workers. Use whenever triage needs visual reproduction, implementation needs behavioral proof, review needs interactive confirmation, or any factory stage asks to verify UI/app behavior.
---

# Verify behavior

Prove or disprove visible product behavior for **bugs and greenfield features**. Other agents (triage, implementation, review) invoke this instead of driving the UI themselves.

Default evidence: **video** of the critical path is required whenever capture is possible, plus keyframe screenshots. Screenshots alone are a fallback only when video tools are unavailable — say so explicitly.

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

Goal: exercise the assigned bug path or feature story; choose browser use vs computer use; capture video by default + keyframe screenshots; report evidence, not opinions.

Mode: <reproduce | verify>
Work shape: <single-path | assigned-story-worker>
Assigned story: <one story/criterion, or full checklist if sole worker>
Change type: <feature | bug-fix | both | unknown>
Issue/PR, PRODUCT.md/TECH.md paths+excerpts, expected/reported behavior, repro steps, branch/ref, app setup, surface hint, constraints: <fill in>

PRODUCT.md (if present): build the story checklist; cover only your assignment (or full in-scope list if sole verify worker). Prefer newer issue decisions on conflicts.

Channel: prefer Puppeteer/Chrome MCP for in-browser web; computer use for native/OS/multi-surface. Switch if blocked. Record channel + why.

Setup: confirm env/tools; checkout assigned ref (verify=implementation/PR head; reproduce=baseline); start app from docs; smallest path to UI; block with logs/screenshots if startup fails.

Evidence dir: ~/verify-behavior-<issue>-<story-or-primary>
- Prefer critical-path video/trace; else ordered screenshots
- manifest.md: file, time, channel, story, visible state, action, outcome support
- Upload via harness if available; else report paths
- Never include secrets/tokens/credentialed URLs

Flow:
1. Checklist before ad-hoc exploration
2. Baseline state + evidence
3. Exact reporter steps when relevant, then remaining assigned stories
4. reproduce: stop when bug appears; note unreached stories
5. verify: prove assigned feature story/checklist; greenfield is first-class; if also a fix, show failure is gone
6. ≤2 targeted extra variations if inconclusive and supported by spec/issue
7. No product code changes; story workers do not re-fan-out

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

Success means: clear mode status; channel choice; PRODUCT.md story checklist outcomes when present; fan-out or explicit serialize reason for multi-story features; **video artifact on the Oz run** (or explicit video-unavailable blocker); **evidence posted on the GitHub issue** when an issue is in scope; repeatable steps/setup; no secrets.

```text
Behavior verification:
- Mode / change type / channel(s) / fan-out
- Status / issue-PR
- PRODUCT.md stories: n passed / failed / blocked / not run
- Evidence / findings / next step
```


## Posting evidence back to GitHub

When this skill is invoked from a factory parent that has a GitHub issue/PR, evidence must land in **two** places:

1. **Oz run artifacts** — upload video/screenshots/manifest via the harness artifact mechanism so they appear on the Oz run.
2. **GitHub issue (and PR when one exists)** — parent or verify worker must post a comment that embeds or links the evidence.

### How to post to GitHub

Prefer attaching files with `gh` so they become issue assets, not just remote links:

```bash
# After evidence files exist locally in the run workspace:
gh issue comment <N> --repo <owner/repo> \
  --body "$(cat <<'EOF'
## Behavior verification evidence
- Mode: verify
- Status: verified | partially verified | not verified | blocked
- Oz verify run: https://oz.warp.dev/runs/<verify-run-id>
- Oz implement run: https://oz.warp.dev/runs/<parent-run-id>  # if applicable

### Video
Primary critical-path recording attached (or linked if upload fails).

### Keyframes
Screenshots attached for idle, action, success/failure states.
EOF
)" \
  --attach ~/verify-behavior-<issue>/01-critical-path.mp4 \
  --attach ~/verify-behavior-<issue>/01-idle.png \
  --attach ~/verify-behavior-<issue>/02-after-action.png
```

If `--attach` is unavailable or fails, upload via `gh api` to the issue comments/assets endpoint or include durable Oz artifact URLs **and** note the upload failure.

Rules:

- Video first. Filename like `01-critical-path.mp4` / harness recording name.
- Comment must include the Oz run URL using `https://oz.warp.dev/runs/<id>` (never `app.warp.dev/run/`).
- Do not claim verification complete until Oz artifacts exist **and** the GitHub issue comment with evidence has been posted (or an explicit blocker explains why posting failed).
- Parents (implementation/triage/review) are responsible for ensuring this handoff happens if the verify child cannot comment itself.

## Guardrails

- Cloud verification subagent over local clicking
- Features are first-class; not bug-fix-only
- PRODUCT.md defines stories when present
- Multi-story verify defaults to parallel workers
- Video required when capture is possible; screenshots are supplemental/fallback
- When a GitHub issue is in scope, post evidence to the issue (attach video/screenshots) and include Oz run links
- No claim of verification without Oz artifacts + GitHub evidence post (or explicit blocker)
- Bounded batches; no secret leakage; no irreversible actions without human confirmation

Optional `verify-behavior-local` may specialize setup/surface/fan-out limits only—not weaken evidence, privacy, or reporting.
