#!/bin/sh -eu
# Variables expected in environment:
# * DIFF_URL (optional, will read stdin otherwise)
# * GITHUB_TOKEN (optional, will output reviewers to stdout otherwise)
# * PR_URL (optional, will output reviewers to stdout otherwise)
# * ORG_NAME (optional, will use # as a group prefix otherwise)
# * REPO_NAME (optional, for more rule matching with TARGET_BRANCH_NAME)
# * TARGET_BRANCH_NAME (optional, for more rule matching with REPO_NAME)
# * REPO_URL (optional, to fetch specific rules)

CURL="curl --fail --show-error --silent --location"

if [ -n "${REPO_URL:-}" ]; then
  HERALD_RULES_JSON=$(mktemp)
  # We always fetch the rules from the main branch.
  RULES_URL="${REPO_URL}/refs/heads/main/herald_rules.json"

	if ! ${CURL} "${RULES_URL}" --output "${HERALD_RULES_JSON}"; then
    echo "Failed to fetch rules from ${RULES_URL}, using built-in rules ..." >&2
    HERALD_RULES_JSON=""

  fi

else
	echo "No REPO_URL in environment, using built-in rules ..." >&2

fi

if [ -z "${HERALD_RULES_JSON:-}" ]; then
  HERALD_RULES_JSON="${1}"
fi

DIFF=$(mktemp)
if [ -n "${DIFF_URL:-}" ]; then
  ${CURL} "${DIFF_URL}" --output "${DIFF}"

else
	echo "No DIFF_URL in environment, reading from stdin ..." >&2
	cat > "${DIFF}"

fi

if [ -n "${ORG_NAME:-}" ]; then
  GROUP_PREFIX="${ORG_NAME}/"

else
  GROUP_PREFIX="#"
	echo "No ORG_NAME in environment, using ${GROUP_PREFIX} as group prefix ..." >&2

fi

if [ -n "${REPO_NAME:-}" ] && [ -n "${TARGET_BRANCH_NAME:-}" ]; then
  REPO_BRANCH=${REPO_NAME}-${TARGET_BRANCH_NAME}

else
	echo "No REPO_NAME or TARGET_BRANCH_NAME in environment, not matching repository-based rules ..." >&2
fi

REVIEWERS=$(cat "${DIFF}" \
	| reviewer-selector \
    ${REPO_BRANCH:+--repo "${REPO_BRANCH}"} \
    --group-prefix "${GROUP_PREFIX}" --reviewer-separator , \
    "${HERALD_RULES_JSON}" \
)

if [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${PR_URL:-}" ]; then
	echo "Adding reviewers to ${PR_URL} ..." >&2
	gh pr edit "${PR_URL}" --add-reviewer "${REVIEWERS}"

else
	echo "No PR_URL or GITHUB_TOKEN in environment, outputing to stdout ..." >&2
  echo "${REVIEWERS}"
fi
