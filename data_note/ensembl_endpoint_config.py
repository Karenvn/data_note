from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Mapping

LEGACY_ORG_BASE = "https://ftp.ebi.ac.uk/pub/ensemblorganisms/"
LEGACY_ENS_MAIN_GFF3 = "https://ftp.ensembl.org/pub/current_gff3/"
LEGACY_ENS_MAIN_GTF = "https://ftp.ensembl.org/pub/current_gtf/"
DEFAULT_BETA_GRAPHQL_URL = "https://beta.ensembl.org/data/graphql"


def _configured_url(env: Mapping[str, str], env_name: str, default: str, *, trailing_slash: bool = True) -> str:
    value = env.get(env_name, default).strip()
    if trailing_slash:
        return value.rstrip("/") + "/"
    return value.rstrip("/")


@dataclass(slots=True)
class EnsemblEndpointConfig:
    organisms_base: str
    main_gff3_base: str
    main_gtf_base: str
    beta_graphql_url: str
    debug: bool = False
    headers: dict[str, str] = field(
        default_factory=lambda: {
            "Accept": "application/json",
            "User-Agent": "genome-notes/1.0",
        }
    )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "EnsemblEndpointConfig":
        env = environ or os.environ
        return cls(
            organisms_base=_configured_url(env, "GN_ENSEMBL_ORGANISMS_BASE", LEGACY_ORG_BASE),
            main_gff3_base=_configured_url(env, "GN_ENSEMBL_MAIN_GFF3_BASE", LEGACY_ENS_MAIN_GFF3),
            main_gtf_base=_configured_url(env, "GN_ENSEMBL_MAIN_GTF_BASE", LEGACY_ENS_MAIN_GTF),
            beta_graphql_url=_configured_url(
                env,
                "GN_ENSEMBL_GRAPHQL_URL",
                DEFAULT_BETA_GRAPHQL_URL,
                trailing_slash=False,
            ),
            debug=str(env.get("GN_DEBUG_ENSEMBL", "0")).strip().lower() in {"1", "true", "yes", "on"},
        )

    def debug_print(self, message: str) -> None:
        if self.debug:
            print(f"[ENSEMBL] {message}")


__all__ = [
    "DEFAULT_BETA_GRAPHQL_URL",
    "EnsemblEndpointConfig",
    "LEGACY_ENS_MAIN_GFF3",
    "LEGACY_ENS_MAIN_GTF",
    "LEGACY_ORG_BASE",
]
