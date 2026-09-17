import os

from taskcluster.helper import TaskclusterConfig, load_secrets


class Taskcluster:
    _tc: TaskclusterConfig

    def __init__(self):
        self._tc = TaskclusterConfig()
        self._tc.auth()

    def fetch_secret(self, secret_id: str) -> dict[str, str]:
        """Fetch a TaskCluster secret by it ID."""
        secrets = self._tc.get_service("secrets")
        return load_secrets(secrets, secret_id)


def tc_task_url() -> str | None:
    if (tc_root := os.getenv("TASKCLUSTER_ROOT_URL")) and (
        tc_task_id := os.getenv("TASK_ID")
    ):
        return f"{tc_root}/tasks/{tc_task_id}"
