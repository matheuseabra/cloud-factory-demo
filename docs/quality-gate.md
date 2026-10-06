# Deterministic quality gate

The implementation agent runs native checks, checks spec alignment, then follows
`.agents/skills/quality-gate/SKILL.md` before behavioral verification and PR creation.
Gauntlet remains an external CLI: it reports evidence; the agent repairs code/tests.
The PR workflow reruns committed changes without Oz, secrets, or write permissions.

## Agent runtime setup

Before modifying code, bootstrap inside the environment executing implementation:

```bash
bash scripts/setup-quality-tools.sh
source .gauntlet/tools/bin/activate
gauntlet doctor
gauntlet check --changed --json
```

The bootstrap reads a reviewed immutable SHA from `gauntlet-version.txt`, fetches
that Gauntlet revision into temporary storage, and runs its shared
`scripts/setup-tools.sh` installer. Gauntlet owns the analyzer pins and grammar
setup; the factory does not duplicate them. Installed tools remain in
`.gauntlet/tools` after temporary source cleanup. Reuse successful setup from the
current run; setup must not happen during checks.

Python 3.12+, Git, and network access are required for setup. Set `GAUNTLET_PYTHON`
when a compatible interpreter has a different name. Project dependencies must
also be installed. Configure native commands in `gauntlet.toml`; the starter
uses Gauntlet project detection until explicit commands are added. Missing tools,
coverage, or setup prerequisites are blockers, not passes.

The implementation workflow explicitly tells Oz to bootstrap inside its cloud
runtime. Installing tools on the GitHub dispatcher cannot provision that runtime.
Optional `WARP_AGENT_ENVIRONMENT` selects a provisioned Oz environment with Python,
Git, and project dependencies. The pinned Oz action supports `environment` for
cloud runs; `profile` applies only to local runs. The cloud path still needs the
repository's `WARP_API_KEY`; the separate quality workflow needs no secret.

## Committed PR changes

```bash
gauntlet check --base BASE_SHA --json
```

Check out the intended head with a clean tracked working tree and fetch base/head
history first. Gauntlet resolves the unique merge base, selects existing committed
changes, and carries their changed line ranges into CRAP policy. Untracked files
and deletions are excluded; an empty selection never expands into a full scan.
JSON includes resolved `base_sha`, `head_sha`, and `merge_base_sha`.

The factory has no custom diff-selection helper. Working-tree `--changed` is for
uncommitted agent work; native `--base` is for clean committed PR comparisons.
CRAP policy uses changed function spans when available and otherwise changed
files. Historical CRAP score comparison is not implemented. Mutation still
examines functions in selected files; it is not limited to changed lines.

A no-relevant-source pass does not prove shell, workflow, or product correctness.
The factory workflow runs its native integration tests separately. Report selected
scope and native validation alongside the Gauntlet result. This demo's tests cover
the integration; tests for factory Python scripts must cover their actual behavior.

## Policy and evidence

- Meaningful surviving mutants and severe CRAP in changed code block by default.
- Dryer candidates require investigation and do not block by default.
- Individual acceptances in `.gauntlet/accept.toml` require concrete reasons,
  remain visible in JSON, and must be explained in the PR.
- Exit 0 passes; 1 is a tool/internal error; 2 is a prerequisite failure;
  3 is a blocking finding; 4 is invalid configuration/context; 5 is a missing
  dependency or coverage artifact.

The workflow clears stale reports before analysis and always attempts to upload
`.gauntlet/results.json`, including failed runs. Artifacts are named with PR number
and head SHA. Setup failures may leave no report; missing evidence cannot turn a
failed job into a pass. Generated results and tool environments stay out of Git.

## Install and activate in another repository

The factory installer adds the skill, workflow, runtime bootstrap, revision pin,
and starter config, preserving an existing `gauntlet.toml`. CI calls the shared
Gauntlet setup action at the same immutable revision as the runtime bootstrap.
Tests keep that pin and the live/installable workflows aligned.

Customize `quality-gate.yml` to install project runtimes and locked dependencies
before invoking the gate (for example, `actions/setup-node` and `npm ci`). Configure
native checks, coverage, and analysis scope for your project. Update the Gauntlet
SHA in both `gauntlet-version.txt` and the workflow/template after reviewing and
verifying its setup/CLI contract. No deployment credentials belong in this job.

After merging and verifying a successful run, require **Quality Gate / Gauntlet**
in branch protection/rulesets. This PR does not modify repository settings.

The trusted `pull_request_target` review workflow is unchanged: contributor code
remains data, and the reviewer never executes Gauntlet against it. Review-artifact
ingestion and monitoring are future work. Future ingestion must bind evidence to
the repository, PR, and head SHA, and treat artifact content as untrusted data.
