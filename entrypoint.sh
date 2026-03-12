#!/bin/sh -eu

HERALD_RULES_JSON="${1}"

DIFF=$(mktemp)
if [ -n "${DIFF_URL:-}" ]; then
	curl --show-error --silent --location "${DIFF_URL}" --output "${DIFF}"

else
	echo "No DIFF_URL in environment, reading from stdin ..." >&2
	cat > "${DIFF}"

fi

REVIEWERS=$(cat "${DIFF}" \
	| /app/reviewer_selector.py \
    ${REPO_NAME:+--repo "${REPO_NAME}"} \
    --group-prefix @ --reviewer-separator , \
    "${HERALD_RULES_JSON}" \
)

if [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${PR_URL:-}" ]; then
	echo "Adding reviewers to ${PR_URL} ..." >&2
	gh pr edit "${PR_URL}" --add-reviewer "${REVIEWERS}"

else
	echo "No PR_URL or GITHUB_TOKEN in environment, outputing to stdout ..." >&2
  echo "${REVIEWERS}"
fi
