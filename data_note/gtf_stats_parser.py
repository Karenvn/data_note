from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import gzip
import re

from .formatting_utils import format_with_nbsp


@dataclass(slots=True)
class GtfStatsParser:
    def parse(self, annot_file: str) -> dict[str, str]:
        gtf_dict: dict[str, str] = {}
        transcript_count = 0
        gene_count = 0
        exon_count = 0
        gene_lengths: list[int] = []
        transcript_lengths: list[int] = []
        exon_lengths: list[int] = []
        intron_lengths: list[int] = []
        cds_lengths: list[int] = []

        protein_coding_genes = 0
        pseudogene_genes = 0
        non_coding_genes = 0

        coding_like_biotypes = {
            "protein_coding",
            "IG_V_gene",
            "IG_C_gene",
            "IG_D_gene",
            "IG_J_gene",
            "TR_V_gene",
            "TR_D_gene",
            "TR_J_gene",
            "TR_C_gene",
        }

        if annot_file.endswith(".gz"):
            handle = gzip.open(annot_file, "rt")
        else:
            handle = open(annot_file, "r")

        current_transcript = None
        transcript_exons: dict[str, list[tuple[int, int]]] = defaultdict(list)

        try:
            for line in handle:
                if line.startswith("#"):
                    continue

                columns = line.strip().split("\t")
                if len(columns) < 9:
                    continue

                feature_type = columns[2]
                start = int(columns[3])
                end = int(columns[4])
                length = end - start + 1

                if feature_type == "gene":
                    gene_count += 1
                    gene_lengths.append(length)
                    match = re.search(r'gene_biotype\s+"([^"]+)"', line)
                    if match:
                        biotype = match.group(1)
                        if biotype in coding_like_biotypes:
                            protein_coding_genes += 1
                        elif "pseudogene" in biotype:
                            pseudogene_genes += 1
                        else:
                            non_coding_genes += 1
                elif feature_type == "transcript":
                    transcript_count += 1
                    current_transcript = re.search(r'transcript_id\s+"([^"]+)"', line).group(1)
                    transcript_lengths.append(length)
                elif feature_type == "exon":
                    exon_count += 1
                    exon_lengths.append(length)
                    if current_transcript:
                        transcript_exons[current_transcript].append((start, end))
                elif feature_type == "CDS":
                    cds_lengths.append(length)
        finally:
            handle.close()

        for exons in transcript_exons.values():
            exons.sort()
            for index in range(1, len(exons)):
                intron_length = exons[index][0] - exons[index - 1][1] - 1
                if intron_length > 0:
                    intron_lengths.append(intron_length)

        av_transc = round(transcript_count / gene_count, 2) if gene_count > 0 else 0
        av_exon = round(exon_count / transcript_count, 2) if transcript_count > 0 else 0
        av_gene_length = round(sum(gene_lengths) / len(gene_lengths), 2) if gene_lengths else 0
        av_transcript_length = round(sum(transcript_lengths) / len(transcript_lengths), 2) if transcript_lengths else 0
        av_exon_length = round(sum(exon_lengths) / len(exon_lengths), 2) if exon_lengths else 0
        av_intron_length = round(sum(intron_lengths) / len(intron_lengths), 2) if intron_lengths else 0
        av_cds_length = round(sum(cds_lengths) / len(cds_lengths), 2) if cds_lengths else 0

        gtf_dict["genes"] = format_with_nbsp(gene_count, as_int=True)
        gtf_dict["transcripts"] = format_with_nbsp(transcript_count, as_int=True)
        gtf_dict["av_transc"] = format_with_nbsp(av_transc, as_int=False)
        gtf_dict["av_exon"] = format_with_nbsp(av_exon, as_int=False)
        gtf_dict["prot_genes"] = format_with_nbsp(protein_coding_genes, as_int=True)
        gtf_dict["pseudogenes"] = format_with_nbsp(pseudogene_genes, as_int=True)
        gtf_dict["non_coding"] = format_with_nbsp(non_coding_genes, as_int=True)
        gtf_dict["av_gene_length"] = format_with_nbsp(av_gene_length, as_int=False)
        gtf_dict["av_transcript_length"] = format_with_nbsp(av_transcript_length, as_int=False)
        gtf_dict["av_exon_length"] = format_with_nbsp(av_exon_length, as_int=False)
        gtf_dict["av_intron_length"] = format_with_nbsp(av_intron_length, as_int=False)
        gtf_dict["av_cds_length"] = format_with_nbsp(av_cds_length, as_int=False)
        return gtf_dict


__all__ = ["GtfStatsParser"]
