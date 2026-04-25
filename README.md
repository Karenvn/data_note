# Genome notes markdown creation

`data_note` is a Python workflow for generating genome note markdown from BioProject accession numbers. It collects assembly, sequencing, taxonomy, annotation, curation, sampling, and quality metadata from public sources, with optional addition of metadata from local systems. It then renders a Pandoc markdown note with associated figures and references in the required formats.

The repository is designed for preparation of genome notes in markdown. It treats metadata integration, text generation and figure preparation as a distinct workflow, separate from upstream pipelines that produce genome assembly and quality assessment outputs.

## Scope

This repository covers:

- BioProject-driven metadata collection
- assembly and sequencing summaries
- fetching local sample and sequencing metadata from the ToL Portal
- fetching local quality analysis stats and figures
- markdown note generation
- figure and table preparation needed by the markdown note

This repository does not aim to cover:

- Pandoc-to-docx / PDF / JATS conversion
- BibTeX cleanup and publication-specific bibliography management
- final publication packaging

Those publishing steps are a separate Pandoc/typesetting workflow, such as [Inara](https://github.com/openjournals/inara/tree/main/test), [Seismica-sce-v2](https://github.com/WeAreSeismica/seismica-sce-v2) or the package used for Tree of Life genome notes: https://github.com/Karenvn/pandoc-data-note.

## Quick start

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

This runs the package entrypoint directly.

For explicit profile selection, use:

```bash
python -m data_note --profile darwin --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

`plant` is now also available as a profile name. It currently inherits the Darwin table and figure plan, but gives plant notes a dedicated profile name so they can diverge later without affecting Darwin notes. It is also the profile that enables plant flow-cytometry enrichment. It works with plant-specific templates such as:

```bash
python -m data_note --profile plant --template_file ~/genome_note_templates/dtol_plant_template.md bioprojects.txt
```

`psyche` is also available as a profile name. It now has its own table module, with the first extracted differences from Darwin:
- Table 3 adds assigned Merian elements and, for dual chromosome-level haplotypes, reports haplotype 1 only.
- Table 5 includes the extra Psyche software rows.

All profiles can now include an Iso-Seq column in the specimen/sequencing table when Iso-Seq data is present.

`asg` is now also available as a profile name. It currently provides:
- ASG figure numbering, including metagenome figure slots.
- ASG table numbering, with software versions moved to `table6`.
- an optional metagenome `table5` hook driven by `metagenome_table_headers` and `metagenome_table_rows` when metagenome output is available.

## Assembly Selection Overrides

By default, `data_note` selects the primary assembly or haplotype 1 assembly automatically after tax-id filtering, then chooses the matching alternate or haplotype 2 assembly.

For cases where the automatic choice is not the one you want, the CLI now supports explicit assembly-selection inputs:

- `--assembly GCA_...`
- `--alt-assembly GCA_...`
- `--hap1-assembly GCA_...`
- `--hap2-assembly GCA_...`

The same run-wide override path is also available through environment variables:

- `DATA_NOTE_ASSEMBLY`
- `DATA_NOTE_ALT_ASSEMBLY`
- `DATA_NOTE_HAP1_ASSEMBLY`
- `DATA_NOTE_HAP2_ASSEMBLY`

Typical usage is:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md --assembly GCA_123456789.1 bioprojects.txt
```

That tells the workflow to use the supplied primary assembly or haplotype 1 assembly accession and then infer the matching alternate or haplotype 2 when possible.

To force an explicit primary/alternate pair:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md \
--assembly GCA_123456789.1 --alt-assembly GCA_123456790.1 bioprojects.txt
```

To force an explicit haplotype pair:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md \
--hap1-assembly GCA_123456789.1 --hap2-assembly GCA_123456790.1 bioprojects.txt
```

Rules:

- use either `--assembly` with optional `--alt-assembly`, or `--hap1-assembly` with optional `--hap2-assembly`
- `--alt-assembly` requires `--assembly`
- `--hap2-assembly` requires `--hap1-assembly`
- the supplied accession must still survive the normal tax-id and excluded-name filtering

These flags apply to the current run as a whole. They are therefore most useful when `bioprojects.txt` contains a single BioProject, or when every BioProject in the input file should use the same explicit assembly choice.

## Architecture

The refactor of genome note writing scripts is centered on a typed internal model with a flattened template context only at the point of filling the markdown template.

- `data_note/orchestrator.py` coordinates the end-to-end workflow for one BioProject.
- `data_note/models/` contains typed slices for base note info, assembly, sequencing, sampling, curation, taxonomy, annotation, quality, and author metadata.
- `data_note/models/note_data.py` bundles those typed slices into a single `NoteData` object during orchestration.
- `data_note/services/assembly_workflow_service.py`, `sequencing_workflow_service.py`, and `annotation_quality_workflow_service.py` now own the main stage-level workflow logic.
- `data_note/services/render_context_builder.py` is the main boundary that derives and flattens typed slices into the final template-facing `NoteContext`.
- `data_note/profiles/` defines project-specific behaviour for Darwin, Psyche, and ASG.
- `data_note/tables/` contains profile-specific table builders for the different Tree of Life projects.
- `data_note/services/figure_service.py` plus the image helper modules handle profile-driven figure collection and naming separately from markdown rendering.

The intended flow is:

```text
fetch/service layers -> typed models -> NoteData -> workflow services -> RenderContextBuilder -> NoteContext/dict -> Jinja2 template
```

For a lightweight in-repo test run, use the fixture files and do:

```bash
python -m data_note --template_file tests/fixtures/template.md tests/fixtures/bioprojects.txt
```

This still performs live metadata lookups. Generated species folders are written into the current working directory.

## Requirements

- Python 3.10+
- `biopython`
- `jinja2`
- `num2words`
- `pandas`
- `Pillow`
- `python-dateutil`
- `PyYAML`
- `requests`
- `tenacity`

Optional local integration would also require:

- `tol-sdk`
- JIRA credentials in `~/.netrc`
- local access to internal YAML and results files
- access to a local author SQLite database.

## Environment

The main runtime configuration is environment-variable based. See [.env.example](.env.example) for the current set.

Important variables include:

- `ENTREZ_EMAIL`
- `ENTREZ_API_KEY`
- `DATA_NOTE_GN_ASSETS` (preferred)
- `DATA_NOTE_SERVER_DATA` (legacy alias)
- `DATA_NOTE_PROFILE` (`darwin` by default)
- `DATA_NOTE_ASSEMBLY` (explicit primary assembly override)
- `DATA_NOTE_ALT_ASSEMBLY` (explicit alternate assembly override)
- `DATA_NOTE_HAP1_ASSEMBLY` (explicit haplotype 1 override)
- `DATA_NOTE_HAP2_ASSEMBLY` (explicit haplotype 2 override)
- `DATA_NOTE_CORRECTIONS_FILE`
- `DATA_NOTE_CYTO_INFO_TSV`
- `DATA_NOTE_LR_SAMPLE_PREP_TSV`
- `DATA_NOTE_AUTHOR_DB`

The assembly override variables mirror the CLI flags and apply to the whole run. Use either the primary/alternate pair or the haplotype 1/2 pair, not both.

Optional internal variables include:

- `PORTAL_URL`
- `PORTAL_API_PATH`
- `DATA_NOTE_TOLA_TSV_URL`
- `JIRA_BASE_URL`
- `JIRA_DOMAIN`
- `YAML_CACHE_DIR`
- `YAML_SSH_USER` (optional; defaults to the current OS username for local server fetches)
- `YAML_SSH_HOST` (optional; defaults to `tol22` for local server fetches)
- `YAML_SSH_IDENTITY_FILE`

Internal YAML handling now always treats the remote path recorded in Jira as the authoritative source. The file is refreshed into `YAML_CACHE_DIR` for manual inspection and is not copied into generated genome note output folders.

Optional Ensembl transition variables include:

- `GN_ENSEMBL_GRAPHQL_URL`
- `GN_ENSEMBL_ORGANISMS_BASE`
- `GN_ENSEMBL_MAIN_GFF3_BASE`
- `GN_ENSEMBL_MAIN_GTF_BASE`

## Assumptions and limitations

- The core pipeline is designed to work from public assembly project metadata.
- Data for each BioProject should be available in ENA using a structure matching the Earth BioGenome Project recommendation for a Species X assembly project (see https://www.earthbiogenome.org/report-on-assembly-standards).
- Assembly quality assets such as BlobToolKit, GenomeScope, Merqury run results, a chromosome map, ancestral linkage groups plots, and metagenome analyses are expected to exist already.
- Optional plant flow-cytometry data is expected at `DATA_NOTE_CYTO_INFO_TSV`, defaulting to `~/gn_assets/cyto_info.tsv`.
- Optional LR extraction spreadsheet data is expected at `DATA_NOTE_LR_SAMPLE_PREP_TSV`, defaulting to `~/gn_assets/LR_sample_prep.tsv` with a legacy fallback to `~/genome_note_templates/LR_sample_prep.tsv`.
- Templates are expected to be Jinja2-based markdown templates.
- Some local metadata lookup steps rely on internal data, and are not required for the public core pipeline.

## Repository Layout

- [data_note](data_note/): the package code
- [data_note/services](data_note/services/): service-layer components for assembly, taxonomy, annotation, sequencing, sampling, curation, quality, rendering, and context assembly
- [data_note/models](data_note/models/): typed models such as `AssemblyBundle`, `SequencingSummary`, `SamplingInfo`, `CurationBundle`, `TaxonomyInfo`, `AnnotationInfo`, `QualityMetrics`, `NoteData`, and `NoteContext`
- [data_note/profiles](data_note/profiles/): programme-specific profile definitions for Darwin, Psyche, and ASG
- [data_note/tables](data_note/tables/): profile-specific table builders and shared table utilities
- [tests](tests/): minimal unit tests, fixtures and representative output folders
- [.env.example](.env.example): example environment configuration

## Tests and example data

Minimal unit tests can be run with:

```bash
python -m unittest discover -s tests
```

The repository also includes:

- [tests/fixtures](tests/fixtures/): a small template and BioProject list for test runs
- [tests/output](tests/output/): lightweight representative output folders kept for structure and discussion, not as strict golden-master outputs

## Current Status

- The supported entrypoint is `python -m data_note ...`.
- `darwin` is the default profile.
- The core workflow now uses typed internal slices for base note info, assembly, sequencing, sampling, curation, taxonomy, annotation, quality, and author metadata, with context flattening centralised in `RenderContextBuilder`.
- The orchestrator is now mostly a high-level coordinator over dedicated workflow services rather than a large inline script.
- `psyche` is now a separate runtime profile with its own table module and figure plan; it still shares much of the Darwin workflow where behaviour is the same.
- `asg` is now a separate runtime profile with its own table/figure numbering, but metagenome-specific data collection and figure generation are not yet implemented in the core pipeline.
- Darwin and Psyche regression coverage now exists alongside the unit tests.
- Internal integrations are environment dependent.


## Standards

This repository is informed by the [Genomic Standards Consortium’s MIxS standard](https://genomicsstandardsconsortium.github.io/mixs/) for sequence-associated metadata. Where appropriate, the workflow attempts to structure metadata in ways that are compatible with MIxS concepts and checklists, although it does not (yet) implement a complete formal MIxS schema.
