import os
import subprocess
from pathlib import Path



IDENTITY_FILE = os.getenv("YAML_SSH_IDENTITY_FILE", str(Path.home() / ".ssh" / "newkey"))


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
        print(f"[info] Reusing local YAML: {local_yaml}")
        return local_yaml

    local_yaml.parent.mkdir(parents=True, exist_ok=True)
    remote = f"{ssh_user}@{ssh_host}:{remote_path}"
    print(f"[info] SCP’ing {remote} → {local_yaml}")
    try:
        subprocess.run(["scp", "-i", IDENTITY_FILE, remote, str(local_yaml)], check=True)

        return local_yaml
    except subprocess.CalledProcessError as e:
        print(f"[error] SCP failed: {e}")
        return None
