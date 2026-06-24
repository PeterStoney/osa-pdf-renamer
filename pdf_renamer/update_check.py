import re
import subprocess
import sys
from dataclasses import dataclass

import requests

from .config import APP_VERSION, GITHUB_REPO
from .health import show_dialog


GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/{repo}/releases/latest"
)


@dataclass
class UpdateInfo:
    latest_version: str
    release_url: str


def version_tuple(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(part) for part in parts) if parts else (0,)


def newer_version_available(current: str, latest: str) -> bool:
    current_parts = version_tuple(current)
    latest_parts = version_tuple(latest)
    length = max(len(current_parts), len(latest_parts))
    current_parts += (0,) * (length - len(current_parts))
    latest_parts += (0,) * (length - len(latest_parts))
    return latest_parts > current_parts


def latest_release() -> UpdateInfo | None:
    try:
        response = requests.get(
            GITHUB_LATEST_RELEASE_URL.format(repo=GITHUB_REPO),
            headers={"Accept": "application/vnd.github+json"},
            timeout=4,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None

    tag = str(payload.get("tag_name", "")).strip()
    release_url = str(payload.get("html_url", "")).strip()
    if not tag or not release_url:
        return None

    latest = tag[1:] if tag.lower().startswith("v") else tag
    return UpdateInfo(latest_version=latest, release_url=release_url)


def open_url(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(
            ["/usr/bin/open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def check_for_updates() -> None:
    update = latest_release()
    if update is None:
        return
    if not newer_version_available(APP_VERSION, update.latest_version):
        return

    button = show_dialog(
        "OSA PDF Renamer update available",
        (
            "A newer OSA PDF Renamer installer is available.\n\n"
            f"Installed version: {APP_VERSION}\n"
            f"Latest version: {update.latest_version}\n\n"
            "Open the GitHub release page to download the latest pkg?"
        ),
        buttons=("Later", "Open"),
        default_button="Open",
    )
    if button == "Open":
        open_url(update.release_url)
