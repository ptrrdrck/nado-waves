#!/usr/bin/env bash
#
# Push the built bundle to the public Pages repository.
#
# Called by both workflows that produce it: "Build forecast" after each
# GFS-Wave cycle, and "Collect beach inputs" hourly once the observed reading
# is rebuilt. It lives here rather than inline in each because it is thirty
# lines of git plumbing that must behave identically in both, and two copies
# of that drift.
#
# Environment (nothing is passed as an argument — argv is visible to any
# process on the runner, and one of these is a credential):
#
#   PAGES_REPO   owner/name of the public repository
#   PAGES_TOKEN  fine-grained PAT, Contents: write on PAGES_REPO only
#   BUNDLE       directory holding the built files (default build/site)
#   REASON       short text for the commit message
#
# Exits 0 without pushing when PAGES_TOKEN is unset, so a repository that has
# not been wired up yet still runs the rest of its workflow.

set -euo pipefail

BUNDLE="${BUNDLE:-build/site}"
REASON="${REASON:-Publish}"

if [ -z "${PAGES_TOKEN:-}" ]; then
  echo "::notice title=Page not published::PAGES_TOKEN is not set, so the bundle was built but not pushed."
  exit 0
fi

if [ ! -d "${BUNDLE}" ]; then
  echo "::error title=Nothing to publish::${BUNDLE} does not exist."
  exit 1
fi

work="$(mktemp -d)"
if ! git clone --depth 1 "https://github.com/${PAGES_REPO}.git" "$work" 2>/dev/null; then
  echo "::error title=Pages repo unreachable::Could not clone ${PAGES_REPO}. Check it exists and the token's repository access."
  exit 1
fi

# Replace the published files; anything else in the repository is left alone.
cp "${BUNDLE}"/* "$work/"
[ -f "${BUNDLE}/.nojekyll" ] && cp "${BUNDLE}/.nojekyll" "$work/"

cd "$work"
git config user.name "nado-waves forecast"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A

if git diff --cached --quiet; then
  echo "Published page already current."
  exit 0
fi

changed="$(git diff --cached --name-only | tr '\n' ' ')"
git commit -m "${REASON}" \
  -m "Changed: ${changed}. Built from nado-waves; do not edit here."

# The token reaches git through the credential helper's stdin, never through a
# remote URL that `git remote -v` would print.
git config credential.helper '!f() { echo "username=x-access-token"; echo "password=${PAGES_TOKEN}"; }; f'
for attempt in 1 2 3 4; do
  if git push origin HEAD; then
    echo "::notice title=Page published::${PAGES_REPO}: ${changed}"
    exit 0
  fi
  echo "Push failed (attempt ${attempt}); rebasing and retrying."
  git pull --rebase --autostash origin HEAD || true
  sleep $((2 ** attempt))
done

echo "::error title=Publish failed::Could not push to ${PAGES_REPO}"
exit 1
