import re

from taskgraph.transforms.base import TransformSequence

transforms = TransformSequence()


@transforms.add
def add_index_routes(config, tasks):
    for task in tasks:
        params = config.params
        head_rev = params["head_rev"]
        # Indices only allow dot-delimited groups of /[a-zA-Z0-9_!~*'()%-]+/.
        # Sanitise the branch name accordingly.
        head_ref = "does_this_thing_work"

        index_prefix = "reviewer-selector"
        if params["tasks_for"] == "github-pull-request":
            index_prefix = "reviewer-selector-pr"

        trust_domain = config.graph_config["trust-domain"]
        task.setdefault("routes", []).extend(
            [
                # XXX: We should be using `task['name']` as the last component,
                # but it's not defined in the task dict.
                f"index.{trust_domain}.v2.{index_prefix}.branch.{head_ref}.revision.{head_rev}.{config.kind}.reviewer-selector",
                f"index.{trust_domain}.v2.{index_prefix}.branch.{head_ref}.latest.{config.kind}.reviewer-selector",
            ]
        )

        yield task
