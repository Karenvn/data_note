import logging
import os
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)


def _identity_file() -> str:
    return os.getenv("YAML_SSH_IDENTITY_FILE", str(Path.home() / ".ssh" / "newkey"))


def fetch_or_copy_yaml(local_base: str,
                       tolid: str,
                       remote_path: str,
                       ssh_user: str,
                       ssh_host: str) -> Path | None:
    """
    Refresh the cached YAML from the authoritative remote path and return the
    local cache path under local_base/<tolid>.yaml.
    """
    local_yaml = Path(local_base) / f"{tolid}.yaml"
    local_yaml.parent.mkdir(parents=True, exist_ok=True)
    remote = f"{ssh_user}@{ssh_host}:{remote_path}"
    logger.info("Refreshing cached YAML via SCP: %s -> %s", remote, local_yaml)
    try:
        subprocess.run(["scp", "-i", _identity_file(), remote, str(local_yaml)], check=True)

        return local_yaml
    except subprocess.CalledProcessError as e:
        logger.error("SCP failed: %s", e)
        return None
