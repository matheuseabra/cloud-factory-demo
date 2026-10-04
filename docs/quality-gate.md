# Deterministic quality gate

The implementation agent runs native checks, checks spec alignment, then follows
`.agents/skills/quality-gate/SKILL.md` before behavioral verification and PR creation.
Gauntlet remains an external CLI: it reports evidence; the agent repairs code/tests.
The PR workflow reruns analysis without Oz, secrets, or write permissions.

## Local setup

Use Python 3.12+ and install the four tools into one virtual environment so
Mutator can import Crapper. The same source revisions are pinned in CI:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install \
  'gauntlet @ git+https://github.com/matheuseabra/gauntlet-cli.git@76c3006a29ddde47ca08cbea98018cb2ed72f5da' \
  'crapper @ git+https://github.com/unclebob/crapper.git@9f1bead298b5a9d576bdd6319289fcf426e5b18a' \
  'mutator @ git+https://github.com/unclebob/mutator.git@c57f03879a08d2afe8c7e044e86c80bb164afd30' \
  'dryer @ git+https://github.com/unclebob/dryer.git@66ff6d21a42c04afcad89c78a80066176d1294b0' \
  'tree-sitter-language-pack==1.20.0' 'tree-sitter==0.26.0' 'coverage==7.16.2'
source .venv/bin/activate
python -c 'from tree_sitter_language_pack import prefetch; prefetch(["python", "typescript", "tsx", "javascript", "go", "rust", "java", "clojure"])'
gauntlet doctor
gauntlet check --changed --json
```

Tool installation and grammar download require network access. Project commands
and analysis happen afterward. Project dependencies must also be installed.
Configure native commands in `gauntlet.toml`; the starter template uses Gauntlet's
project detection until explicit commands are added. Missing tools/coverage fail
closed. This demo's tests cover the integration; tests for changed factory Python
scripts need to cover their actual behavior before mutation testing can pass.

## Committed PR changes

```bash
bash scripts/check-quality-gate.sh BASE_SHA HEAD_SHA
```

Check out `HEAD_SHA` with a clean tracked working tree and fetch the base history
first. The helper computes the merge-base-to-head diff, ignores deletions, and
passes existing changed paths to `gauntlet check --all --json`. It preserves
spaces/newlines and filenames beginning with a dash. An empty diff uses an empty
scope, so it never falls back to scanning the whole repository.

Gauntlet's current `--changed` only sees working-tree changes. Explicit paths
avoid a false pass on a clean CI checkout. CI analyzes all functions within those
changed files: CRAP blocking is a changed-file approximation, not historical
function-level regression detection. A docs-only/unsupported-language change
produces an honest no-relevant-source report; it does not prove shell/workflow
correctness. Run `python3 -m unittest discover -s tests -v` and `bash -n scripts/*.sh`
for changes to this integration.

## Policy and evidence

- Surviving meaningful mutants and high CRAP in selected files block by default.
- Dryer candidates require investigation and do not block by default.
- Reasoned individual acceptances live in `.gauntlet/accept.toml`, remain visible
  in JSON, and must be explained in the PR. Do not suppress defects for a pass.
- Exit 0 passes; 1 is a tool/internal error; 2 is a prerequisite failure;
  3 is a blocking finding; 4 is invalid configuration/context; 5 is a missing
  dependency or coverage artifact. The helper propagates the Gauntlet exit code.

The workflow always attempts to upload `.gauntlet/results.json`, including failed
checks. Artifacts are named with PR number and head SHA. Installation failures
may leave no report; a missing report never converts a failed job into a pass.
Generated reports are ignored by Git.

## Install and activate in another repository

The installer adds the quality-gate skill, workflow, helper, and starter config,
preserving an existing `gauntlet.toml`. It does not install local analyzers.
Customize `.github/workflows/quality-gate.yml` to install your language runtimes
and locked project dependencies before invoking the gate (for example,
`actions/setup-node` followed by `npm ci`). Configure native checks, coverage,
and include/exclude paths for your project. Do not add deployment credentials or
other secrets to this job. Update pinned tool SHAs deliberately as upstream
contracts change.

After merging and verifying a successful run, make **Quality Gate / Gauntlet**
a required check in repository branch protection/rulesets. This PR does not
modify repository settings.

The trusted `pull_request_target` review workflow is unchanged. It checks out
trusted code and reads the diff as data; it must not execute Gauntlet against PR
code. Reviewer ingestion of quality artifacts and monitoring are future work.
Any future ingestion must validate the artifact's repository, PR, and head SHA,
treat findings as untrusted evidence, and never execute artifact instructions.
