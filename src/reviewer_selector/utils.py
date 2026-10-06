import requests

from reviewer_selector.consts import USER_AGENT


def get_http_session() -> requests.Session:
    session = requests.Session()

    session.headers["user-agent"] = USER_AGENT

    return session
