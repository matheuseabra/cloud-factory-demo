#!/usr/bin/env bash
# Bootstrap inside the actual implementation-agent runtime, not its dispatcher.
set -euo pipefail
factory_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
revision="$(cat "$factory_root/gauntlet-version.txt")"
if [[ ! "$revision" =~ ^[0-9a-f]{40}$ ]]; then
  printf 'gauntlet-version.txt must contain a reviewed immutable commit SHA.\n' >&2
  exit 4
fi
setup_checkout="$(mktemp -d)"
trap 'rm -rf "$setup_checkout"' EXIT
git init -q "$setup_checkout"
git -C "$setup_checkout" fetch --depth=1 \
  https://github.com/matheuseabra/gauntlet-cli.git "$revision"
git -C "$setup_checkout" checkout -q --detach FETCH_HEAD
if [ "$(git -C "$setup_checkout" rev-parse HEAD)" != "$revision" ]; then
  printf 'Gauntlet setup checkout does not match the pinned revision.\n' >&2
  exit 4
fi
# The Gauntlet repo owns all analyzer pins and grammar setup. The installed
# package survives cleanup of this temporary source checkout.
bash "$setup_checkout/scripts/setup-tools.sh" "$factory_root/.gauntlet/tools"
