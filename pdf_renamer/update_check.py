import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

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
    package_url: str = ""


def versioned_pkg_path(version: str) -> Path:
    return (
        Path.home()
        / "Downloads"
        / f"OSA PDF Renamer Installer {version}.pkg"
    )


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
    package_url = ""
    for asset in payload.get("assets", []):
        name = str(asset.get("name", "")).lower()
        download_url = str(
            asset.get("browser_download_url", "")
        ).strip()
        if name.endswith(".pkg") and download_url:
            package_url = download_url
            break

    return UpdateInfo(
        latest_version=latest,
        release_url=release_url,
        package_url=package_url,
    )


def open_url(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(
            ["/usr/bin/open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def open_file(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(
            ["/usr/bin/open", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def download_update(update: UpdateInfo) -> tuple[Path | None, str]:
    if not update.package_url:
        return None, "The release does not include a pkg installer asset."

    target = versioned_pkg_path(update.latest_version)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(
            update.package_url,
            stream=True,
            timeout=20,
        ) as response:
            response.raise_for_status()
            with target.open("wb") as destination:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        destination.write(chunk)
    except Exception as error:
        return None, str(error)

    return target, ""


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
            "Download the installer now?"
        ),
        buttons=("Later", "Download"),
        default_button="Download",
    )
    if button != "Download":
        return

    path, error = download_update(update)
    if path:
        show_dialog(
            "OSA PDF Renamer update downloaded",
            (
                "The updated installer has been downloaded and will open now.\n\n"
                f"{path}"
            ),
        )
        open_file(path)
        return

    fallback = show_dialog(
        "OSA PDF Renamer update failed",
        (
            "The installer could not be downloaded automatically.\n\n"
            f"Details: {error}\n\n"
            "Open the GitHub release page instead?"
        ),
        buttons=("Later", "Open"),
        default_button="Open",
    )
    if fallback == "Open":
        open_url(update.release_url)
