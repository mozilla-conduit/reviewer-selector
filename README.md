# Reviewer selector

Select reviewers based on a diff and a set of rules.

# Setup

Requirements: [uv](https://docs.astral.sh/uv/#installation).

    $ uv venv
    $ uv pip install -r requirements.txt

# Running

In its simplest form, the script accepts a diff on stdin. It processes the diff
according to a rule file passed as an argument, and outputs a list of
individual and groups of reviewers.

    $ uv run ./reviewer_selector.py herald_rules.sample.json < sample.diff
    #example-group shtrom

The group prefix can be changed with `--group-prefix`. The reviewer separator
can be changed with `--reviewer-separator`. The `--repo` option allows the user
to specify a specific repository (to be used when evaluating conditions in some
rules.

# WARNING: The rules format is a work in progress

The current rules files, as shown in [the sample](./herald_rules.sample.json)
is not final and not normative. It is used as a bootstrapping stop-gap, and
should not be expected to remain stable at this stage.

# Tests

    $ uv run pytest

# Linting

    $ uv run ruff format

# Containerised deployment

For use as part of a more complex pipeline, a docker image can be built. It is
setup to take most of its arguments from environment variables, and will update
a GitHub pull request directly if enough information is available.

## Building the container image

Requirements: [docker](https://docs.docker.com/get-started/get-docker/).

    $ docker build -t reviewer-selector .


## Running in a container

For convenience, the sample rules are shipped with the container image. The
reviewers string is formatted for use with [GitHub's gh
CLI](https://cli.github.com/).

    $ docker run --rm -i reviewer-selector < sample.diff
    No DIFF_URL in environment, reading from stdin ...
    No PR_URL or GITHUB_TOKEN in environment, outputing to stdout ...
    @example-group,shtrom

The warnings are output to stderr.

A more advanced example would mount a real ruleset into the container at
`/app/herald_rules.json`. The diff data can be fetched from a pull request and
piped into the container.

    $ curl --silent --location https://github.com/mozilla-firefox/infra-testing/pull/30.diff \
       | docker run --rm -i \
         -v ./herald_rules.real.json:/app/herald_rules.json \
         reviewer-selector
    No DIFF_URL in environment, reading from stdin ...
    No PR_URL or GITHUB_TOKEN in environment, outputing to stdout ...
    @android-reviewers

The container's behaviour can be entirely parametrised via environment variables.

    $ docker run --rm -i \
      -v ./herald_rules.real.json:/app/herald_rules.json \
      -e DIFF_URL=https://github.com/mozilla-firefox/infra-testing/pull/30.diff \
      -e PR_URL=https://github.com/mozilla-firefox/infra-testing/pull/30 \
      -e GITHUB_TOKEN=[REDACTED] reviewer-selector
    Adding reviewers to https://github.com/mozilla-firefox/infra-testing/pull/30 ...

If `DIFF_URL` is given, it will be fetched and passed into the selector's
stdin. If `GITHUB_TOKEN` and `PR_URL` are provided, the container will attempt
to set the reviewers on the target PR.
