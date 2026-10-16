"""Inventory and release metadata checks shared by sidecar transport tools."""
import hashlib
import json
from pathlib import Path


RELEASE_FILE = "sidecar-release.json"


def inventory_digest(manifest):
    data = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def read_inventory(path):
    manifest = json.loads(Path(path).read_text())
    if manifest["schema"] != "grampy-sidecar-inventory.v1":
        raise ValueError("Unsupported inventory schema")
    return manifest


def read_release(root, manifest):
    release = json.loads((Path(root) / RELEASE_FILE).read_text())
    if (not isinstance(release, dict)
            or set(release) != {"schema", "version", "inventory_sha256", "include_history"}
            or release["schema"] != "grampy-sidecar-release.v1"
            or not isinstance(release["version"], str) or not release["version"].strip()
            or not isinstance(release["include_history"], bool)):
        raise ValueError("Invalid whole-sidecar release metadata")
    if release["inventory_sha256"] != inventory_digest(manifest):
        raise ValueError("Sidecar release does not match the supplied inventory")
    return release


def verify(root, manifest, *, include_history=False):
    root = Path(root).resolve()
    failures = []
    checked = 0
    if (root / RELEASE_FILE).exists():
        try:
            read_release(root, manifest)
        except (OSError, ValueError, KeyError, TypeError) as error:
            failures.append(f"invalid release metadata: {error}")
    records = manifest["files"]
    known = {RELEASE_FILE}
    for record in records:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"Unsafe inventory path: {relative}")
        if relative.as_posix() in known:
            raise ValueError(f"Duplicate inventory path: {relative}")
        known.add(relative.as_posix())
        if record["group"] == "archive" and not include_history:
            continue
        path = root / relative
        if any(p.is_symlink() for p in (path, *path.parents) if p != root and p.is_relative_to(root)):
            failures.append(f"unsupported symlink: {relative}")
            continue
        try:
            size = path.stat().st_size
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
        except OSError:
            failures.append(f"missing or unreadable: {relative}")
            continue
        checked += 1
        if size != record["bytes"] or actual != record["sha256"]:
            failures.append(f"changed: {relative}")
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file() and path.name != ".DS_Store":
                relative = path.relative_to(root).as_posix()
                if relative not in known:
                    failures.append(f"unclassified installed file: {relative}")
    return checked, failures

