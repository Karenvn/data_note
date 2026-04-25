from __future__ import annotations

from contextlib import chdir
import copy
import tempfile
import unittest
from pathlib import Path

from data_note.profiles import DarwinProfile, PsycheProfile
from data_note.services.rendering_service import RenderingService


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "regression"
TEMPLATE_PATH = FIXTURES_DIR / "render_template.md"
DARWIN_SNAPSHOT = FIXTURES_DIR / "darwin_expected.md"
PSYCHE_SNAPSHOT = FIXTURES_DIR / "psyche_expected.md"


def _base_context() -> dict[str, object]:
    return {
        "species": "Example species",
        "bioproject": "PRJEB12345",
        "tolid": "ixExamSpec1",
        "hic_tolid": "ixExamSpec1",
        "rna_tolid": "ixExamSpec1",
        "isoseq_tolid": "ixExamSpec1",
        "assemblies_type": "prim_alt",
        "assembly_name": "ixExamSpec1.1",
        "prim_accession": "GCA_123456789.1",
        "alt_accession": "GCA_123456790.1",
        "assembly_level": "chromosome",
        "total_length": "512.3",
        "chromosome_count": "12",
        "num_contigs": "34",
        "contig_N50": "18.2",
        "num_scaffolds": "20",
        "scaffold_N50": "41.7",
        "sex_chromosomes": "X",
        "supernumerary_chromosomes": "B1",
        "length_mito_kb": "16.4",
        "chromosome_data": [
            {
                "INSDC": "OX000001.1",
                "molecule": "1",
                "length": "45.1",
                "GC": "39.8",
            }
        ],
        "ebp_metric": "6.C.Q40",
        "prim_QV": "52.1",
        "alt_QV": "50.0",
        "combined_QV": "51.0",
        "prim_kmer_completeness": "99.2",
        "alt_kmer_completeness": "98.7",
        "combined_kmer_completeness": "99.5",
        "BUSCO_string": "C:98.0%[S:97.0%,D:1.0%],F:1.0%,M:1.0%,n:1000",
        "perc_assembled": "96.4",
        "blobtoolkit_version": "4.2.1",
        "busco_version": "5.7.1",
        "diamond_version": "2.1.8",
        "hifiasm_version": "0.19.8",
        "minimap2_version": "2.28",
        "mitohifi_version": "3.2.2",
        "oatk_version": "0.4.0",
        "nextflow_version": "24.10.0",
        "purge_dups_version": "1.2.6",
        "samtools_version": "1.21",
        "btk_pipeline_version": "1.6.0",
        "yahs_version": "1.2.2",
        "pacbio_specimen_id": "SPEC-001",
        "hic_specimen_id": "SPEC-001",
        "rna_specimen_id": "SPEC-001",
        "isoseq_specimen_id": "SPEC-001",
        "pacbio_sample_derived_from": "SAMEA-DERIVED",
        "hic_sample_derived_from": "SAMEA-DERIVED",
        "rna_sample_derived_from": "SAMEA-DERIVED",
        "isoseq_sample_derived_from": "SAMEA-DERIVED",
        "pacbio_sample_accession": "SAMEA-PB",
        "hic_sample_accession": "SAMEA-HIC",
        "rna_sample_accession": "SAMEA-RNA",
        "isoseq_sample_accession": "SAMEA-ISO",
        "pacbio_organism_part": "whole organism",
        "hic_organism_part": "whole organism",
        "rna_organism_part": "thorax",
        "isoseq_organism_part": "thorax",
        "pacbio_instrument": "Sequel IIe",
        "hic_instrument": "NovaSeq 6000",
        "rna_instrument": "NovaSeq 6000",
        "isoseq_instrument": "Sequel IIe",
        "pacbio_run_accessions": "ERR000001",
        "hic_run_accessions": "ERR000002",
        "rna_run_accessions": "ERR000003",
        "isoseq_run_accessions": "ERR000004",
        "pacbio_reads_millions": "12.3",
        "hic_reads_millions": "45.6",
        "rna_reads_millions": "22.1",
        "isoseq_reads_millions": "4.2",
        "pacbio_bases_gb": "33.4",
        "hic_bases_gb": "14.8",
        "rna_bases_gb": "6.5",
        "isoseq_bases_gb": "1.7",
        "jira": "RC-1000",
        "formatted_parent_projects": "PRJEB99999",
        "auto_text": "Example automatic summary.",
    }


def _build_rendering_service() -> RenderingService:
    def make_triple(output_dir: str, stem: str) -> tuple[Path, Path, Path]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        png = output_path / f"{stem}.png"
        tif = output_path / f"{stem}.tif"
        gif = output_path / f"{stem}.gif"
        png.write_text("png")
        tif.write_text("tif")
        gif.write_text("gif")
        return png, tif, gif

    return RenderingService(
        gscope_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(
            output_dir, output_stem or "Fig_2_Gscope"
        ),
        pretext_labeler=lambda tolid, context, output_dir, output_stem=None: make_triple(
            output_dir, output_stem or "Fig_3_Pretext"
        ),
        merian_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(
            output_dir, output_stem or "Fig_4_Merian"
        ),
        merqury_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(
            output_dir, output_stem or "Fig_4_Merqury"
        ),
        btk_image_processor=lambda accession, output_dir, output_names=None: [
            make_triple(
                output_dir,
                (output_names or {}).get("snail", "Fig_5_Snail.png").removesuffix(".png"),
            ),
            make_triple(
                output_dir,
                (output_names or {}).get("blob", "Fig_6_Blob.png").removesuffix(".png"),
            ),
        ],
        special_character_replacer=lambda text, target_format="markdown": text,
    )


class ProfileRegressionTests(unittest.TestCase):
    maxDiff = None

    def _assert_snapshot_equal(self, rendered: str, snapshot_path: Path) -> None:
        self.assertEqual(rendered.rstrip("\n"), snapshot_path.read_text().rstrip("\n"))

    def _render_profile(self, profile):
        with tempfile.TemporaryDirectory() as tmpdir, chdir(tmpdir):
            service = _build_rendering_service()
            context = copy.deepcopy(_base_context())
            context = profile.build_tables(context)
            output_dir = Path(service.write_note(str(TEMPLATE_PATH), context, profile))
            markdown_path = output_dir / f"{context['tolid']}.md"
            rendered = markdown_path.read_text()
            generated_files = {path.name for path in output_dir.iterdir()}
            return rendered, context, generated_files

    def test_darwin_render_snapshot(self) -> None:
        rendered, context, generated_files = self._render_profile(DarwinProfile())

        self._assert_snapshot_equal(rendered, DARWIN_SNAPSHOT)
        self.assertEqual(tuple(context["tables"].keys()), ("table1", "table2", "table3", "table4", "table5"))
        self.assertIn("Fig_4_Merqury", context)
        self.assertIn("Fig_5_Snail", context)
        self.assertIn("Fig_6_Blob", context)
        self.assertNotIn("Fig_4_Merian", context)
        self.assertIn("**Iso-Seq**", context["tables"]["table1"]["rows"][0])
        self.assertIn("**RNA-seq**", context["tables"]["table1"]["rows"][0])
        self.assertIn("Fig_4_Merqury.gif", generated_files)
        self.assertIn("Fig_5_Snail.gif", generated_files)
        self.assertIn("Fig_6_Blob.gif", generated_files)

    def test_psyche_render_snapshot(self) -> None:
        rendered, context, generated_files = self._render_profile(PsycheProfile())

        self._assert_snapshot_equal(rendered, PSYCHE_SNAPSHOT)
        self.assertEqual(tuple(context["tables"].keys()), ("table1", "table2", "table3", "table4", "table5"))
        self.assertIn("Fig_4_Merian", context)
        self.assertIn("Fig_5_Merqury", context)
        self.assertIn("Fig_6_Snail", context)
        self.assertIn("Fig_7_Blob", context)
        self.assertNotIn("Fig_4_Merqury", context)
        self.assertIn("lep_busco_painter,1.0.0", "\n".join(context["tables"]["table5"]["rows"]))
        self.assertEqual(context["tables"]["table3"]["native_headers"][-1], "**Assigned Merian elements**")
        self.assertIn("Fig_4_Merian.gif", generated_files)
        self.assertIn("Fig_5_Merqury.gif", generated_files)
        self.assertIn("Fig_6_Snail.gif", generated_files)
        self.assertIn("Fig_7_Blob.gif", generated_files)


if __name__ == "__main__":
    unittest.main()
