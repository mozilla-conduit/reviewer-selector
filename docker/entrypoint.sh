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
  RULES_URL="${REPO_URL}/raw/refs/heads/${TARGET_BRANCH_NAME:-main}/herald_rules.json"

  echo "Attempting to fetch rules from ${RULES_URL} ..." >&2
	if ! ${CURL} -L "${RULES_URL}" --output "${HERALD_RULES_JSON}"; then
    echo "Failed, using built-in rules ..." >&2
    HERALD_RULES_JSON=""

  fi

else
	echo "No REPO_URL in environment, using built-in rules ..." >&2

fi

if [ -z "${HERALD_RULES_JSON:-}" ]; then
  HERALD_RULES_JSON="${1:-${DEFAULT_HERALD_RULES_JSON}}"
fi

DIFF=$(mktemp)
if [ -n "${DIFF_URL:-}" ]; then
	echo "Fetching diff from DIFF_URL from environment ..." >&2
  ${CURL} "${DIFF_URL}" --output "${DIFF}"

elif [ -z "${PR_URL:-}" ]; then
	echo "No DIFF_URL or PR_URL in environment, reading from stdin ..." >&2
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
	echo "REPO_NAME or TARGET_BRANCH_NAME missing from environment, not matching repository-based rules ..." >&2
fi

REVIEWERS=$(cat "${DIFF}" \
	| reviewer-selector \
    --verbose \
    ${REPO_BRANCH:+--repo "${REPO_BRANCH}"} \
    ${PR_URL:+--pr-url "${PR_URL}"} \
    --group-prefix "${GROUP_PREFIX}" --reviewer-separator , \
    "${HERALD_RULES_JSON}" \
)

if [ -z "${GITHUB_TOKEN:-}" ] && [ -n "${TC_SECRET_ID:-}" ]; then
  echo "TC_SECRET_ID provided, using it to generate GITHUB_TOKEN ..." >&2
  GITHUB_TOKEN="$(gh-token-generator)"
  export GITHUB_TOKEN
fi

if [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${PR_URL:-}" ]; then
  if [ -z "${REVIEWERS}" ]; then
    echo "No reviewers to add ..." >&2

  else
    echo "Adding reviewers ${REVIEWERS} to ${PR_URL} ..." >&2
    gh pr edit "${PR_URL}" --add-reviewer "${REVIEWERS}" >/dev/null
  fi

else
	echo "PR_URL or GITHUB_TOKEN missing from environment, outputing to stdout ..." >&2
  echo "${REVIEWERS}"
fi
