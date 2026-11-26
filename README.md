# Reviewer selector

Select reviewers based on a diff and a set of rules.

# Setup

Requirements: [uv](https://docs.astral.sh/uv/#installation).

    $ uv sync


# Running

In its simplest form, the script accepts a diff on stdin. It processes the diff
according to a rule file passed as an argument, and outputs a list of
individual and groups of reviewers.

    $ uv run reviewer-selector samples/herald_rules.sample.json < samples/sample.diff
    #example-group shtrom

The group prefix can be changed with `--group-prefix`. The reviewer separator
can be changed with `--reviewer-separator`. The `--repo` option allows the user
to specify a specific repository (to be used when evaluating conditions in some
rules.


# Development tasks

All the commands in this section rely on the development dependencies being installed.

    $ uv sync --group dev

## Tests

    $ make test

You can also run the tests within the built docker image.

    $ make build
    $ make test-docker

## Linting

Ruff has a [linter and a formatter](https://docs.astral.sh/ruff/faq/#do-i-have-to-use-ruffs-linter-and-formatter-together). We use both,

    $ uv run ruff format
    $ uv run ruff check --fix

or simply,

    $ make format

## Regenerating requirements.txt

    $ make requirements


## Bundling herald_rules

> [!WARNING]
> The rules format is a work in progress.
>
> The current rules files, as shown in [the
> sample](./samples/herald_rules.sample.json) is not final and not normative.
> It is used as a bootstrapping stop-gap, and should not be expected to remain
> stable at this stage.

The default behaviour is to search the target repository/branch for a `herald_rules.json` file.
If missing, a fallback from the container is used.

There is a [periodic action in the
`herald_crawler`](https://github.com/mozilla-conduit/herald_crawler/actions/workflows/refresh-herald-rules.yml)
which updates the rules via a pull request.

<details>

<summary>Manually updating the bundled rules</summary>

Herald rules can be extracted from Phabricator using the [Herald
Crawler](https://github.com/mozilla-conduit/herald_crawler).


    $ uv run herald-scraper --url https://phabricator.services.mozilla.com \
      --conduit-token $PHAB_TOKEN \
      --stmo-api-key $STMO_API_KEY \
      [--pmo-cookie $PMO_COOKIE] \
      --input herald_rules.json --output herald_rules.new.json
    $ mv herald_rules.new.json herald_rules.json

Get/create your `$PHAB_TOKEN` from
https://phabricator.services.mozilla.com/settings/user/<YOUR-USERNAME>/page/apitokens/.
Get your `$PMO_COOKIE` from the `pmo-access` cookie after logging in to
https://people.mozilla.org/
Get the `$STMO_API_KEY` from https://sql.telemetry.mozilla.org/users/me.

Those rules should be placed at the root of the source tree, and committed to
git so they are built as part of the image. `make build` takes care of using
configuring the image adequately.

New versions of the reviewer selector containing updated herald_rules.json,
should at least be minor updates.

</details>


# Containerised deployment

For use as part of a more complex pipeline, a docker image can be built. It is
setup to take most of its arguments from environment variables, and will update
a GitHub pull request directly if enough information is available.

## Building the container image

Requirements: [docker](https://docs.docker.com/get-started/get-docker/).

    $ make build

## Running in a container

For convenience, the sample rules are shipped with the container image. The
reviewers string is formatted for use with [GitHub's gh
CLI](https://cli.github.com/).

    $ docker run --rm -i reviewer-selector < samples/sample.diff
    No REPO_URL in environment, using built-in rules ...
    No DIFF_URL in environment, reading from stdin ...
    No ORG_NAME in environment, using # as group prefix ...
    No REPO_NAME or TARGET_BRANCH_NAME in environment, not matching repository-based rules ...
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
    No REPO_URL in environment, using built-in rules ...
    No DIFF_URL in environment, reading from stdin ...
    No ORG_NAME in environment, using # as group prefix ...
    No REPO_NAME or TARGET_BRANCH_NAME in environment, not matching repository-based rules ...
    No PR_URL or GITHUB_TOKEN in environment, outputing to stdout ...
    @android-reviewers

The container's behaviour can be entirely parametrised via environment variables.

    $ docker run --rm -i \
      -v ./herald_rules.real.json:/app/herald_rules.json \
      -e DIFF_URL=https://github.com/mozilla-firefox/infra-testing/pull/30.diff \
      -e PR_URL=https://github.com/mozilla-firefox/infra-testing/pull/30 \
      -e REPO_URL=https://github.com/mozilla-firefox/infra-testing \
      -e ORG_NAME=mozilla-firefox -e REPO_NAME=infra-testing \
      -e GITHUB_TOKEN=[REDACTED] \
      reviewer-selector
    Adding reviewers to https://github.com/mozilla-firefox/infra-testing/pull/30 ...

* If `DIFF_URL` is given, it will be fetched and passed into the selector's
stdin.
* If `GITHUB_TOKEN` and `PR_URL` are provided, the container will attempt 
  to set the reviewers on the target PR.

Some other optional behaviours can be triggered by providing additional context
in environment variables:
* If `ORG_NAME` is passed, it will be used to scope reviewers groups to that
  org.
* If `REPO_NAME` and `TARGET_BRANCH_NAME` are provided, rules that specifically
  match a given repository and/or branch will also be applied.
* If `REPO_URL` is given, the script will attempt to fetch a rules file from
  the `main` branch of the repository. If it fails, it will fallback to
  built-in rules.
* If `TC_SECRET_ID` is provided, it is expected to contain `GITHUB_APP_ID` and
  `GITHUB_APP_PRIVKEY` values. They will be used to generate a `GITHUB_TOKEN`
  (if unspecified) for `ORG_NAME`/`REPO_NAME`.

# Integration


## TaskCluster

The Reviewer Selector runs as a hook in TaskCluster. Docker images are built
for the main branches and releases, and used as configured in [the fxci-config
hook
definition](https://github.com/mozilla-releng/fxci-config/blob/6f0e34567d68106bf18f5089bab15f1420e000e4/hooks.yml#L324-L431).

> [!NOTE]
> * Releases are used for production
> * `main` ([and `staging` if desired](https://github.com/mozilla-releng/fxci-config/blob/6f0e34567d68106bf18f5089bab15f1420e000e4/hook-templates/project-engwf/reviewer-assignment-staging.yml#L36-L41)) is used for stage
> * `develop` is used for dev

The [hooks details can be seen in
TaskCluster](https://firefox-ci-tc.services.mozilla.com/hooks/project-engwf),
based on [their configuration
templates](https://github.com/mozilla-releng/fxci-config/tree/main/hook-templates/project-engwf).

### Local tooling

<details>

<summary>Building the Taskcluster Client for Shell</summary>

Requirements: [golang](https://go.dev/doc/install)

    $ git clone https://github.com/taskcluster/taskcluster
    $ cd taskcluster/clients/client-shell
    $ go build -o taskcluster .

</details>

## GitHub

The GitHub hook reacts to [pull-request
events](https://github.com/mozilla-releng/fxci-config/blob/6f0e34567d68106bf18f5089bab15f1420e000e4/hooks.yml#L371-L412)
published to Pulse by the [firefoxci-taskcluster GitHub
application](https://github.com/apps/firefoxci-taskcluster). The app needs to
be installed into any repository willing to use the reviewer selector, and
matching [Pulse bindings need to be added to the hook
definition](https://github.com/mozilla-releng/fxci-config/blob/6f0e34567d68106bf18f5089bab15f1420e000e4/hooks.yml#L338-L341).

Actions will be performed using as a GitHub application (e.g., Lando). The
TaskCluster secret should provide the following credentials.
* `GITHUB_APP_ID`
* `GITHUB_APP_PRIVKEY`


### GitHub authentication

To generate a GitHub application token based on a TaskCluster secret, use the
`gh-token-generator` script. The secret should contain two values, named
`GITHUB_APP_ID` and `GITHUB_APP_PRIVKEY`.

The generator relies on [Standard TaskCluster Environment
Variables](https://docs.taskcluster.net/docs/manual/design/env-vars) to obtain
the secret named with ID `TC_SECRET_ID`. Those variables can be set with the
[Taskcluster shell
client](https://github.com/taskcluster/taskcluster/tree/main/clients/client-shell),
`taskcluster signin`.

    $ eval $(/PATH/TO/taskcluster/clients/client-shell/taskcluster signin)  # follow the web prompts
    $ export ORG_NAME=mozilla-firefox
    $ export REPO_NAME=infra-testing
    $ uv run gh-token-generator

then

    $ GITHUB_TOKEN=$(uv run gh-token-generator)
    $ gh ...


### GitHub teams as review groups

The Herald Rules define review groups, which loosely map to GitHub teams.

GitHub teams are automatically updated to match review groups when the bundled
`herald_rules.json` file changes on `main`.

<details>

<summary>Manually managing review groups</summary>

The `team-creator` command is available to create teams, and sync membership to
the supplied herald_rules file. Teams are not automatically deleted.

    $ export ORG_NAME=mozilla-firefox
    $ export REPO_NAME=infra-testing
    $ export GITHUB_APP_ID=...
    $ export GITHUB_APP_PRIVKEY=...
    $ uv run team-creator --github-token $(uv run gh-token-generator) --debug \
      --organisation mozilla-firefox --base-team all-reviewers \
      /path/to/herald_rules.json


There is a dedicated GitHub app which has the correct permissions to maintain
team membership at
https://github.com/enterprises/mozilla-corporation/settings/apps/reviewer-selector-team-creator.

</details>


## Phabricator

For Phabricator, reviewer selection is triggered via a webhook to, e.g.,
`https://firefox-ci-tc.services.mozilla.com/api/hooks/v1/hooks/project-engwf/reviewer-assignment-production/trigger/<TOKEN>`.
Herald webhooks, however, have a set payload. Rather it should be triggered via
a [Harbourmaster Build
Plan](https://phabricator.services.mozilla.com/harbormaster/plan/11/), with a
[step to `Make HTTP
Request`](https://phabricator.services.mozilla.com/harbormaster/step/view/10/)
with the following `application/json`
[payload](https://github.com/mozilla-releng/fxci-config/blob/6f0e34567d68106bf18f5089bab15f1420e000e4/hooks.yml#L414-L431).

```
{
  "callsign": "${repository.callsign}",
  "diff_id": ${buildable.diff},
  "revision_id": ${buildable.revision},
  "revision_phid": "${buildable.container.phid}"
}
```

The `<TOKEN>` can be generated with

```
$ eval $(taskcluster signin)
$ taskcluster api hooks getTriggerToken project-engwf reviewer-assignment-production
```

> [!WARNING]
> As the token needs to be embedded in the webhook URI, the Build
> Plan needs to be set to be visible only to Administrators.

The build plan should:
* never hold drafts,
* never warn when landing,
* never affect buildable,
* always be restartable, and
* be runnable if viewable.

This build plan can then be set up to be started from Herald Rules, e.g., when
the [target repository is in a](https://phabricator.services.mozilla.com/H565)
[dedicated
project](https://phabricator.services.mozilla.com/tag/reviewer-selector/).

Actions will be performed as the [`reviewer-selector`
user](https://phabricator.services.mozilla.com/people/manage/8358/). The
TaskCluster secret should provide the following parameters.
* `PHABRICATOR_BASE_URL`
* `PHABRICATOR_API_TOKEN`
