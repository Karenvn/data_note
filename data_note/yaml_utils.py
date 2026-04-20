import logging
import os
import subprocess
from pathlib import Path



IDENTITY_FILE = os.getenv("YAML_SSH_IDENTITY_FILE", str(Path.home() / ".ssh" / "newkey"))
logger = logging.getLogger(__name__)


def fetch_or_copy_yaml(local_base: str,
                       tolid: str,
                       remote_path: str,
                       ssh_user: str,
                       ssh_host: str) -> Path:
    """
    Given a remote_path on the server, return a Path to the YAML file:
    - if it's already in local_base/<tolid>.yaml, use that
    - otherwise scp remote_path → local_base/<tolid>.yaml
    """
    local_yaml = Path(local_base) / f"{tolid}.yaml"
    if local_yaml.exists():
        logger.info("Reusing local YAML: %s", local_yaml)
        return local_yaml

    local_yaml.parent.mkdir(parents=True, exist_ok=True)
    remote = f"{ssh_user}@{ssh_host}:{remote_path}"
    logger.info("SCP'ing %s -> %s", remote, local_yaml)
    try:
        subprocess.run(["scp", "-i", IDENTITY_FILE, remote, str(local_yaml)], check=True)

        return local_yaml
    except subprocess.CalledProcessError as e:
        logger.error("SCP failed: %s", e)
        return None
