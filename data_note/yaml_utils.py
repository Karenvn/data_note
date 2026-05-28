import logging
import os
import shutil
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)


def _identity_file() -> str:
    return os.getenv("YAML_SSH_IDENTITY_FILE", str(Path.home() / ".ssh" / "newkey"))


def _candidate_cache_files(local_yaml: Path) -> list[Path]:
    filename = local_yaml.name
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add_cache_dir(cache_dir: Path) -> None:
        candidate = cache_dir.expanduser() / filename
        key = candidate.resolve(strict=False)
        if key not in seen:
            seen.add(key)
            candidates.append(candidate)

    search_dirs = os.getenv("YAML_CACHE_SEARCH_DIRS")
    if search_dirs is not None:
        for raw_dir in search_dirs.split(os.pathsep):
            if raw_dir.strip():
                add_cache_dir(Path(raw_dir.strip()))
        return candidates

    cwd = Path.cwd()
    home = Path.home()
    for parent in (cwd, *cwd.parents):
        add_cache_dir(parent / "yaml_cache")
        if parent == home or parent == parent.parent:
            break

    documents = home / "Documents"
    if documents.is_dir():
        for project_dir in documents.iterdir():
            if project_dir.is_dir():
                add_cache_dir(project_dir / "yaml_cache")

    add_cache_dir(home / "BTK_requests" / "yaml_cache")
    add_cache_dir(home / "code" / "data_note" / "yaml_cache")
    return candidates


def _reuse_existing_yaml_cache(local_yaml: Path) -> Path | None:
    local_key = local_yaml.resolve(strict=False)
    for candidate in _candidate_cache_files(local_yaml):
        candidate_key = candidate.resolve(strict=False)
        if candidate_key == local_key:
            continue
        if not candidate.is_file():
            continue

        local_yaml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, local_yaml)
        logger.info("Reusing cached YAML from %s -> %s", candidate, local_yaml)
        return local_yaml

    return None


def fetch_or_copy_yaml(local_base: str,
                       tolid: str,
                       remote_path: str,
                       ssh_user: str,
                       ssh_host: str) -> Path | None:
    """
    Return the cached YAML under local_base/<tolid>.yaml, fetching it from the
    authoritative remote path only when the local cache is missing.
    """
    local_yaml = Path(local_base) / f"{tolid}.yaml"
    if local_yaml.is_file():
        logger.info("Using cached YAML: %s", local_yaml)
        return local_yaml

    reused_yaml = _reuse_existing_yaml_cache(local_yaml)
    if reused_yaml:
        return reused_yaml

    local_yaml.parent.mkdir(parents=True, exist_ok=True)
    remote = f"{ssh_user}@{ssh_host}:{remote_path}"
    logger.info("Refreshing cached YAML via SCP: %s -> %s", remote, local_yaml)
    try:
        subprocess.run(["scp", "-i", _identity_file(), remote, str(local_yaml)], check=True)

        return local_yaml
    except subprocess.CalledProcessError as e:
        logger.error("SCP failed: %s", e)
        return None
