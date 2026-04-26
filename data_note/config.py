from __future__ import annotations

from dataclasses import dataclass
import getpass
import os
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from .models import AssemblySelectionInput


def _env_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _expand_path(value: str) -> Path:
    return Path(value).expanduser()


def _assets_root_from_env(env: Mapping[str, str], home: Path) -> Path:
    value = env.get("DATA_NOTE_GN_ASSETS") or env.get("DATA_NOTE_SERVER_DATA") or str(home / "gn_assets")
    return _expand_path(value)


@dataclass(slots=True)
class AppConfig:
    entrez_email: str
    entrez_api_key: str
    debug_ensembl: bool
    profile_name: str
    server_data_root: Path
    corrections_file: Path
    cyto_info_tsv: Path
    lr_sample_prep_tsv: Path
    author_db_path: Path
    portal_url: str | None
    portal_api_path: str
    tola_tsv_url: str | None
    jira_base_url: str | None
    jira_domain: str | None
    yaml_cache_dir: Path
    yaml_ssh_user: str | None
    yaml_ssh_host: str | None
    yaml_ssh_identity_file: Path
    include_gbif_distribution: bool = False
    assembly_accession: str | None = None
    alternate_assembly_accession: str | None = None
    hap1_assembly_accession: str | None = None
    hap2_assembly_accession: str | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AppConfig":
        env = environ or os.environ
        home = Path.home()
        server_data_root = _assets_root_from_env(env, home)

        jira_base_url = env.get("JIRA_BASE_URL")
        jira_domain = env.get("JIRA_DOMAIN")
        if not jira_domain and jira_base_url:
            parsed = urlparse(jira_base_url if "://" in jira_base_url else f"https://{jira_base_url}")
            jira_domain = parsed.netloc or parsed.path or None

        return cls(
            entrez_email=env.get("ENTREZ_EMAIL", "default_email"),
            entrez_api_key=env.get("ENTREZ_API_KEY", "default_api_key"),
            debug_ensembl=_env_bool(env.get("GN_DEBUG_ENSEMBL"), default=False),
            profile_name=env.get("DATA_NOTE_PROFILE", "darwin").strip().lower() or "darwin",
            server_data_root=server_data_root,
            corrections_file=_expand_path(
                env.get(
                    "DATA_NOTE_CORRECTIONS_FILE",
                    str(home / "genome_note_templates" / "text_corrections.json"),
                )
            ),
            cyto_info_tsv=_expand_path(
                env.get(
                    "DATA_NOTE_CYTO_INFO_TSV",
                    str(server_data_root / "cyto_info.tsv"),
                )
            ),
            lr_sample_prep_tsv=_expand_path(
                env.get(
                    "DATA_NOTE_LR_SAMPLE_PREP_TSV",
                    str(server_data_root / "LR_sample_prep.tsv"),
                )
            ),
            author_db_path=_expand_path(
                env.get("DATA_NOTE_AUTHOR_DB", str(server_data_root / "author_db.sqlite3"))
            ),
            portal_url=env.get("PORTAL_URL"),
            portal_api_path=env.get("PORTAL_API_PATH", "/api/v1"),
            tola_tsv_url=env.get("DATA_NOTE_TOLA_TSV_URL"),
            jira_base_url=jira_base_url.rstrip("/") if jira_base_url else None,
            jira_domain=jira_domain,
            yaml_cache_dir=_expand_path(env.get("YAML_CACHE_DIR", "yaml_cache")),
            yaml_ssh_user=env.get("YAML_SSH_USER") or getpass.getuser(),
            yaml_ssh_host=env.get("YAML_SSH_HOST") or "tol22",
            yaml_ssh_identity_file=_expand_path(
                env.get("YAML_SSH_IDENTITY_FILE", str(home / ".ssh" / "newkey"))
            ),
            include_gbif_distribution=_env_bool(
                env.get("DATA_NOTE_INCLUDE_GBIF_DISTRIBUTION"),
                default=False,
            ),
            assembly_accession=env.get("DATA_NOTE_ASSEMBLY"),
            alternate_assembly_accession=env.get("DATA_NOTE_ALT_ASSEMBLY"),
            hap1_assembly_accession=env.get("DATA_NOTE_HAP1_ASSEMBLY"),
            hap2_assembly_accession=env.get("DATA_NOTE_HAP2_ASSEMBLY"),
        )

    def apply_environment(self) -> None:
        self._set("ENTREZ_EMAIL", self.entrez_email)
        self._set("ENTREZ_API_KEY", self.entrez_api_key)
        self._set("GN_DEBUG_ENSEMBL", "1" if self.debug_ensembl else "0")
        self._set("DATA_NOTE_PROFILE", self.profile_name)
        self._set("DATA_NOTE_GN_ASSETS", self.server_data_root)
        self._set("DATA_NOTE_SERVER_DATA", self.server_data_root)
        self._set("DATA_NOTE_CORRECTIONS_FILE", self.corrections_file)
        self._set("DATA_NOTE_CYTO_INFO_TSV", self.cyto_info_tsv)
        self._set("DATA_NOTE_LR_SAMPLE_PREP_TSV", self.lr_sample_prep_tsv)
        self._set("DATA_NOTE_AUTHOR_DB", self.author_db_path)
        self._set("PORTAL_API_PATH", self.portal_api_path)
        self._set("YAML_CACHE_DIR", self.yaml_cache_dir)
        self._set("YAML_SSH_IDENTITY_FILE", self.yaml_ssh_identity_file)
        self._set(
            "DATA_NOTE_INCLUDE_GBIF_DISTRIBUTION",
            "1" if self.include_gbif_distribution else "0",
        )
        self._set_optional("PORTAL_URL", self.portal_url)
        self._set_optional("DATA_NOTE_TOLA_TSV_URL", self.tola_tsv_url)
        self._set_optional("JIRA_BASE_URL", self.jira_base_url)
        self._set_optional("JIRA_DOMAIN", self.jira_domain)
        self._set_optional("YAML_SSH_USER", self.yaml_ssh_user)
        self._set_optional("YAML_SSH_HOST", self.yaml_ssh_host)
        self._set_optional("DATA_NOTE_ASSEMBLY", self.assembly_accession)
        self._set_optional("DATA_NOTE_ALT_ASSEMBLY", self.alternate_assembly_accession)
        self._set_optional("DATA_NOTE_HAP1_ASSEMBLY", self.hap1_assembly_accession)
        self._set_optional("DATA_NOTE_HAP2_ASSEMBLY", self.hap2_assembly_accession)

    def assembly_selection_input(self) -> AssemblySelectionInput | None:
        selection_input = AssemblySelectionInput(
            assembly_accession=self.assembly_accession,
            alternate_accession=self.alternate_assembly_accession,
            hap1_accession=self.hap1_assembly_accession,
            hap2_accession=self.hap2_assembly_accession,
        )
        if not selection_input.has_any():
            return None
        selection_input.validate()
        return selection_input

    @staticmethod
    def _set(name: str, value: str | Path) -> None:
        os.environ[name] = str(value)

    @staticmethod
    def _set_optional(name: str, value: str | None) -> None:
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)


def load_config(environ: Mapping[str, str] | None = None) -> AppConfig:
    return AppConfig.from_env(environ)
