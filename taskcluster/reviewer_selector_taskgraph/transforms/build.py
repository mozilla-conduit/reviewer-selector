from taskgraph.transforms.base import TransformSequence

import re

transforms = TransformSequence()


@transforms.add
def add_index_routes(config, tasks):
    for task in tasks:
        params = config.params
        head_rev = params["head_rev"]
        # Indices only allow dot-delimited groups of /[a-zA-Z0-9_!~*'()%-]+/.
        # Sanitise the branch name accordingly.
        head_ref = re.sub(r"[^F a-zA-Z0-9_!~*'()%-]", "_", params["head_ref"])

        index_prefix = "reviewer-selector"
        if params["tasks_for"] == "github-pull-request":
            index_prefix = f"{index_prefix}-pr"

        trust_domain = config.graph_config["trust-domain"]
        task.setdefault("routes", []).extend(
            [
                f"index.{trust_domain}.v2.{index_prefix}.{task['name']}.revision.{head_rev}",
                f"index.{trust_domain}.v2.{index_prefix}.{task['name']}.branch.{head_ref}",
            ]
        )

        yield task
