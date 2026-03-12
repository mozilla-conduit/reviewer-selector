#!/bin/sh -eu

HERALD_RULES_JSON="${1}"

DIFF=$(mktemp)
if [ -n "${DIFF_URL:-}" ]; then
	curl --show-error --silent --location "${DIFF_URL}" --output "${DIFF}"

else
	echo "No DIFF_URL in environment, reading from stdin ..." >&2
	cat > "${DIFF}"

fi

REVIEWERS=$( cat "${DIFF}" \
	| /app/reviewer_selector.py --group-prefix @ --reviewer-separator , "${HERALD_RULES_JSON}" \
)

if [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${PR:-}" ]; then
	echo "Adding reviewers to ${PR} ..." >&2
	gh pr edit "${PR}" --add-reviewer "${REVIEWERS}"

else
	echo "No PR or GITHUB_TOKEN in environment, outputing to stdout ..." >&2
  echo "${REVIEWERS}"
fi
