"""Keep the manifest version, README version and release tag in sync."""

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "custom_components" / "xiaomi_miio_fan" / "manifest.json"


def _manifest_version() -> str:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


def test_readme_version_matches_manifest():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"Version \*\*([\d.]+)\*\*", readme)
    assert match, "README must state 'Version **x.y.z**'"
    assert match.group(1) == _manifest_version()


def test_release_tag_matches_manifest():
    """On a tag build (GITHUB_REF_TYPE=tag) the tag must equal the manifest version."""
    if os.environ.get("GITHUB_REF_TYPE") != "tag":
        return
    assert os.environ["GITHUB_REF_NAME"] == f"v{_manifest_version()}"
