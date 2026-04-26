from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
from typing import Any, Callable, Mapping

from num2words import num2words

from .gbif_taxonomy_client import GbifTaxonomyClient
from .gbif_occurrence_client import GbifOccurrenceClient
from .models import AssemblySelection
from .ncbi_datasets_client import NcbiDatasetsClient
from .ncbi_taxonomy_client import NcbiTaxonomyClient
from .species_summary_models import GenomeAssemblyReport, SpeciesSummary

logger = logging.getLogger(__name__)
_DEFAULT_GBIF_TAXONOMY_CLIENT = GbifTaxonomyClient()


def text_num(n: int) -> str:
    return num2words(n) if n <= 10 else str(n)


def plural(n: int, singular: str) -> str:
    return singular if n == 1 else singular + "s"


def core_acc(acc: str) -> str:
    match = re.search(r"GC[AF]_(\d+)", acc)
    return match.group(1) if match else acc


def _normalise_assembly_input(
    assembly_input: AssemblySelection | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(assembly_input, AssemblySelection):
        return assembly_input.to_context_dict()
    return dict(assembly_input)


@dataclass(slots=True)
class SpeciesSummaryService:
    taxonomy_client: NcbiTaxonomyClient = field(default_factory=NcbiTaxonomyClient)
    datasets_client: NcbiDatasetsClient = field(default_factory=NcbiDatasetsClient)
    gbif_fetcher: Callable[[str, str], dict[str, Any]] = field(
        default_factory=lambda: _DEFAULT_GBIF_TAXONOMY_CLIENT.fetch_species_metadata
    )
    gbif_occurrence_client: GbifOccurrenceClient = field(default_factory=GbifOccurrenceClient)

    def build_summary(
        self,
        species_taxid: int | str,
        assembly_input: AssemblySelection | Mapping[str, Any],
        *,
        tolid: str | None = None,
        include_distribution: bool = False,
    ) -> SpeciesSummary:
        assembly_dict = _normalise_assembly_input(assembly_input)
        lineage = self.taxonomy_client.fetch_lineage_and_ranks(str(species_taxid))
        selected_accessions = self._selected_accessions(assembly_dict)
        selected_cores = {core_acc(accession) for accession in selected_accessions}

        genus_reports = self.datasets_client.fetch_taxon_reports(lineage["genus_taxid"])
        family_reports = self.datasets_client.fetch_taxon_reports(lineage["family_taxid"])

        genus_grouped = self.group_reports(genus_reports, set(selected_accessions), tolid)
        family_grouped = self.group_reports(family_reports, set(selected_accessions), tolid)

        species_records = genus_grouped.get(lineage["species"], [])
        other_species_assemblies = [
            report
            for report in species_records
            if core_acc(report.accession) not in selected_cores
        ]

        refseq_category = self.find_refseq_category(genus_reports, selected_cores)
        summary = SpeciesSummary(
            species_taxid=str(species_taxid),
            species=lineage["species"],
            genus=lineage["genus"],
            family=lineage["family"],
            genus_taxid=lineage.get("genus_taxid"),
            family_taxid=lineage.get("family_taxid"),
            genus_genome_count=len(genus_grouped),
            family_genome_count=len(family_grouped),
            refseq_category=refseq_category,
            other_species_assemblies=other_species_assemblies,
        )
        summary.intro_text = self.render_intro(summary)

        if include_distribution:
            try:
                gbif_data = self.gbif_fetcher(summary.species, summary.species_taxid)
                usage_key = gbif_data.get("gbif_usage_key")
                if usage_key:
                    summary.gbif_usage_key = str(usage_key)
                    summary.gbif_distribution = self.gbif_occurrence_client.fetch_distribution_summary(usage_key)
                    summary.distribution_text = self.gbif_occurrence_client.render_distribution_summary(
                        summary.gbif_distribution
                    )
            except Exception as exc:
                logger.warning("GBIF distribution enrichment failed for %s: %s", summary.species, exc)

        return summary

    def summarise_genomes(
        self,
        species_taxid: int | str,
        assembly_input: AssemblySelection | Mapping[str, Any],
        *,
        tolid: str | None = None,
    ) -> str:
        return self.build_summary(
            species_taxid,
            assembly_input,
            tolid=tolid,
            include_distribution=False,
        ).intro_text

    @staticmethod
    def group_reports(
        reports: list[dict[str, Any]],
        ours: set[str],
        tolid: str | None,
    ) -> dict[str, list[GenomeAssemblyReport]]:
        grouped: dict[str, list[GenomeAssemblyReport]] = defaultdict(list)
        seen_core: set[str] = set()

        for report in reports:
            parsed = GenomeAssemblyReport.from_dataset_report(report)
            if not parsed.accession:
                continue

            core = core_acc(parsed.accession)
            if core in seen_core:
                continue
            seen_core.add(core)

            key = parsed.species
            if parsed.accession in ours or (tolid and tolid in parsed.assembly_name):
                key = tolid or parsed.species
            grouped[key].append(parsed)

        return grouped

    @staticmethod
    def find_refseq_category(
        reports: list[dict[str, Any]],
        selected_cores: set[str],
    ) -> str | None:
        for report in reports:
            accession = str(report.get("accession") or "")
            if accession and core_acc(accession) in selected_cores:
                assembly_info = report.get("assembly_info", {}) or {}
                return str(assembly_info.get("refseq_category") or "na")
        return None

    @staticmethod
    def _selected_accessions(assembly_dict: Mapping[str, Any]) -> list[str]:
        if assembly_dict.get("assemblies_type") == "hap_asm":
            ordered = [assembly_dict.get("hap1_accession"), assembly_dict.get("hap2_accession")]
        else:
            ordered = [assembly_dict.get("prim_accession"), assembly_dict.get("alt_accession")]
        return [str(accession) for accession in ordered if accession]

    @staticmethod
    def make_core_sentence(summary: SpeciesSummary) -> str:
        date = datetime.now().strftime("%B %Y")
        genus_count = summary.genus_genome_count
        family_count = summary.family_genome_count
        genus_word = text_num(genus_count)
        family_word = text_num(family_count)
        cite = "[data obtained via NCBI datasets, @oleary2024NCBI]"

        if genus_count == 1:
            return (
                f"This assembly is the first high-quality genome for the genus *{summary.genus}* "
                f"and one of {family_word} {plural(family_count, 'genome')} available for the "
                f"family {summary.family} as of {date} {cite}."
            )
        if genus_count < 5 and family_count < 10:
            return (
                f"Only {family_word} {plural(family_count, 'genome')} are available for the family "
                f"{summary.family}. The present assembly is one of {genus_word} "
                f"{plural(genus_count, 'genome')} for the genus *{summary.genus}* as of {date} {cite}."
            )
        if genus_count < 10 and family_count < 20:
            return (
                f"Fewer than 20 genomes have been published for the family {summary.family} as of "
                f"{date}, including {genus_word} for the genus *{summary.genus}*. This assembly "
                "adds chromosome-scale data for the lineage."
            )
        return (
            f"Although numerous genomes exist for the family {summary.family}, this assembly "
            f"provides the first chromosomally complete sequence for *{summary.species}*, "
            f"enabling comparative analyses {cite}."
        )

    def render_intro(self, summary: SpeciesSummary) -> str:
        sentence = self.make_core_sentence(summary)
        other = summary.other_species_assemblies

        if other:
            level_map = {"chromosome": 3, "scaffold": 2, "contig": 1}
            best_other = max(other, key=lambda report: level_map.get(report.level, 0))
            label = best_other.level or "non-chromosome"
            accessions = ", ".join(report.accession for report in other if report.accession)
            submitters = ", ".join(sorted({report.submitter for report in other if report.submitter}))
            sentence = (
                f"A chromosomally complete genome sequence for *{summary.species}* is presented, "
                "enabling comparative analyses [data obtained via NCBI datasets; @oleary2024NCBI]."
            )
            if len(other) == 1:
                sentence += (
                    f" Another {label}-level assembly for this species is also available "
                    f"({accessions}; submitted by {submitters})."
                )
            else:
                sentence += (
                    f" Other assemblies for this species are also available, including "
                    f"{label}-level assemblies ({accessions}; submitted by {submitters})."
                )
        elif not (
            summary.genus_genome_count == 1
            or (summary.genus_genome_count < 5 and summary.family_genome_count < 10)
        ):
            sentence += " This is currently the only genome assembly available for this species."

        refseq_note = self.refseq_note(summary.refseq_category)
        if refseq_note:
            sentence += refseq_note
        return sentence

    @staticmethod
    def refseq_note(refseq_category: str | None) -> str:
        if refseq_category == "reference genome":
            return " This assembly is the RefSeq reference assembly for this species."
        if refseq_category == "representative genome":
            return " This assembly is the RefSeq representative assembly for this species."
        return ""


__all__ = ["SpeciesSummaryService", "_normalise_assembly_input"]
