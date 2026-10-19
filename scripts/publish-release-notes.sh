#!/usr/bin/env bash
# Rebuild a GitHub Release body as: the tracked narrative (docs/release-notes/<version>.md),
# a marker line, then the section semantic-release generated.
#
# Usage: bash scripts/publish-release-notes.sh <version>
#        (semantic-release runs it as the @semantic-release/exec successCmd)
#
# Idempotent: on a re-run everything above the marker is replaced from the file and the generated
# section below it is kept, so the body never accumulates copies. Fails if the narrative file is
# missing or the published body comes back without it.
set -euo pipefail

version="${1:?usage: publish-release-notes.sh <version>}"
tag="v${version}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
narrative="${repo_root}/docs/release-notes/${version}.md"
marker="<!-- generated-release-notes -->"

if [[ ! -s "${narrative}" ]]; then
    echo "ERROR: ${narrative} is missing or empty" >&2
    exit 1
fi

current=""
current="$(gh release view "${tag}" --json body --jq .body)"
if [[ "${current}" == *"${marker}"* ]]; then
    generated="${current#*"${marker}"}"
else
    generated="${current}"
fi
generated="${generated#$'\n'}"

body_file="$(mktemp)"
trap 'rm -f -- "${body_file}"' EXIT
{
    cat "${narrative}"
    printf '\n%s\n\n%s\n' "${marker}" "${generated}"
} > "${body_file}"

gh release edit "${tag}" --notes-file "${body_file}" >/dev/null

published=""
published="$(gh release view "${tag}" --json body --jq .body)"
first_line="$(head -n 1 "${narrative}")"
if [[ "${published}" != *"${first_line}"* || "${published}" != *"${marker}"* ]]; then
    echo "ERROR: ${tag} body does not contain the narrative after edit" >&2
    exit 1
fi
echo "✅ ${tag} release body: ${#published} chars (narrative + generated)"
