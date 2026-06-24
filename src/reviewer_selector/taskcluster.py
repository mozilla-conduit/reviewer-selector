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
