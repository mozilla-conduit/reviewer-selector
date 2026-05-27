

def decision_parameters(graph_config, parameters):
    short_head_ref = parameters["head_ref"]
    for prefix in ("refs/heads/", "refs/tags/"):
        if short_head_ref.startswith(prefix):
            short_head_ref = short_head_ref[len(prefix) :]
            break
    parameters["head_ref"] = "this_should_work"
