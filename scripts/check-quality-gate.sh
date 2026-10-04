#!/usr/bin/env bash
# Analyze committed PR changes without relying on a dirty working tree.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  printf 'Usage: bash scripts/check-quality-gate.sh BASE_SHA HEAD_SHA\n' >&2
  exit 4
fi

root="$(git rev-parse --show-toplevel)"
cd "$root"
base="$(git rev-parse --verify --end-of-options "${1}^{commit}")"
head="$(git rev-parse --verify --end-of-options "${2}^{commit}")"
if [ "$(git rev-parse HEAD)" != "$head" ]; then
  printf 'Check out HEAD_SHA before running the PR quality gate.\n' >&2
  exit 4
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  printf 'Committed PR analysis requires a clean tracked working tree.\n' >&2
  exit 4
fi

# Capture Git failure before reading the NUL-delimited list. No shell evaluation
# of filenames; prefix paths so a filename starting with '-' is not an option.
diff_file="$(mktemp)"
trap 'rm -f "$diff_file"' EXIT
git diff --no-ext-diff --no-textconv --no-renames --name-only \
  --diff-filter=ACMRT -z "$base...$head" -- > "$diff_file"
files=()
while IFS= read -r -d '' file; do
  if [ -f "$file" ]; then
    files+=("./$file")
  fi
done < "$diff_file"

mkdir -p .gauntlet
rm -f .gauntlet/results.json
if [ "${#files[@]}" -eq 0 ]; then
  # Explicit empty directory prevents --all from scanning the entire repository.
  empty_scope="$(mktemp -d "$root/.gauntlet/empty-scope.XXXXXX")"
  trap 'rm -f "$diff_file"; rmdir "$empty_scope"' EXIT
  files=("$empty_scope")
fi

# --all means every function in these explicit PR paths, not the whole repo.
# Gauntlet filters unsupported languages, excluded paths, and test files.
gauntlet check --all --json --output .gauntlet/results.json "${files[@]}"
