#!/bin/sh -eu
# Variables expected in environment:
# * PHABRICATOR_REVISION_PHID
# * PHABRICATOR_REVISION_URL
# * PR_URL
# * HERALD_RULES_JSON (optional, use a different set of herald rules from within the image)

if [ -z "${HERALD_RULES_JSON:-}" ]; then
  HERALD_RULES_JSON="${DEFAULT_HERALD_RULES_JSON}"
fi

reviewer-selector \
    --verbose \
    ${PHABRICATOR_REVISION_PHID:+--phabricator-revision-phid "${PHABRICATOR_REVISION_PHID}"} \
    ${PHABRICATOR_REVISION_URL:+--phabricator-revision-url "${PHABRICATOR_REVISION_URL}"} \
    ${PR_URL:+--pr-url "${PR_URL}"} \
    ${*} \
    "${HERALD_RULES_JSON}"
