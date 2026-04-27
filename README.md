# Genome notes Markdown creation

`data_note` is a Python workflow for generating genome note documents in [Pandoc](https://pandoc.org/) Markdown from a list of BioProject accession numbers. It collects sampling, sequencing, taxonomy, assembly, annotation and quality metadata from public sources, with optional addition of metadata for methods and analyses from local systems. It then renders, for each BioProject, a species directory containing the note with associated figures and references in the required formats.

The repository is designed for preparation of genome notes in Markdown. It treats metadata integration, text generation and figure preparation as a distinct workflow, separate from upstream pipelines that analyse genome assembly quality.

## Scope

This repository covers:

- collection of metadata for input BioProject accession numbers
- assembly and sequencing summaries
- fetching local sample and sequencing metadata from the Tree of Life Portal
- fetching local quality analysis stats and figures
- creating Markdown genome notes
- preparing figures and tables needed by the Markdown note

This repository does not handle:

- Pandoc-to-docx / PDF / JATS conversion
- BibTeX cleanup and publication-specific bibliography management
- final publication packaging

These publishing steps require a separate Pandoc/typesetting workflow, such as [Inara](https://github.com/openjournals/inara/tree/main/test), [Seismica-sce-v2](https://github.com/WeAreSeismica/seismica-sce-v2), or the [pandoc-data-note](https://github.com/Karenvn/pandoc-data-note) package used for Tree of Life genome notes.

## Quick start

To run `data_note` from a list of BioProject accessions:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

### Profiles

Different profiles have been created to generate different genome note features. The default profile is `darwin` for Darwin Tree of Life (DToL) genome notes.

For profile selection, use:

```bash
python -m data_note --profile darwin --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

`plant` is the profile name for a subset of DToL notes. It currently inherits the Darwin table and figure plan, but gives plant notes a dedicated profile name so they can diverge later without affecting DToL notes. It is also the profile that adds plant flow cytometry metadata. It works with plant-specific templates such as:

```bash
python -m data_note --profile plant --template_file ~/genome_note_templates/dtol_plant_template.md bioprojects.txt
```

`psyche` is the profile name for Project Psyche genome notes. It has its own table module, with the first extracted differences from DToL:
- Table 3 adds assigned Merian elements and, for dual chromosome-level haplotypes, reports haplotype 1 only.
- Table 5 includes the extra Psyche software rows.
- Figures include a merian plot of chromosomes, generated via the [merian-busco-painter](https://github.com/Karenvn/merian-busco-painter) scripts.

`asg` is the profile name for Aquatic Symbiosis Genomics genome notes. It currently provides:
- ASG figure numbering, including metagenome figure slots.
- ASG table numbering, with software versions moved to `table6`.
- An optional metagenome `table5` hook driven by `metagenome_table_headers` and `metagenome_table_rows` when metagenome output is available.
- If there are enough metagenome bins, a tree of the bins is generated via [metagenome report](https://github.com/Karenvn/metagenome-report).

### Assembly selection overrides

By default, `data_note` takes an input file containing BioProject accessions and selects the primary assembly or haplotype 1 assembly automatically after taxon-id filtering, then chooses the matching alternate or haplotype 2 assembly.

For cases where the automatic choice is not the genome of interest, the assembly accession number can be given for a single BioProject run:

- `--assembly GCA_...` and  `--alt-assembly GCA_...`
- `--hap1-assembly GCA_...` and `--hap2-assembly GCA_...`

The same override values can be supplied by setting environment variables:

- `DATA_NOTE_ASSEMBLY` and  `DATA_NOTE_ALT_ASSEMBLY`
- `DATA_NOTE_HAP1_ASSEMBLY` and `DATA_NOTE_HAP2_ASSEMBLY`

This is useful for cases where the assembly cannot be identified reliably from the BioProject metadata, for example because the BioProject structure is unusual, the taxon metadata have changed after a taxon merger, or the assembly of interest is not selected by the automatic filtering.


To run `data_note` on a batch of BioProjects, with automatic selection of assemblies:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

To add the optional GBIF distribution summary text:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md \
--include-gbif-distribution bioprojects.txt
```

To force an explicit assembly choice within one BioProject:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md \
--assembly GCA_123456789.1 PRJEB12345
```

That tells the workflow to use the supplied primary assembly or haplotype 1 assembly accession for `PRJEB12345` and then infer the matching alternate or haplotype 2 when possible.

To force an explicit primary/alternate pair:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md \
--assembly GCA_123456789.1 --alt-assembly GCA_123456790.1 PRJEB12345
```

To force an explicit haplotype pair:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md \
--hap1-assembly GCA_123456789.1 --hap2-assembly GCA_123456790.1 PRJEB12345
```

Rules:

- use either `--assembly` with optional `--alt-assembly`, or `--hap1-assembly` with optional `--hap2-assembly`
- `--alt-assembly` requires `--assembly`
- `--hap2-assembly` requires `--hap1-assembly`
- the supplied accession must survive the normal taxon id and excluded-name filtering
- assembly override flags and their environment-variable equivalents only work when the input resolves to exactly one BioProject, not a batch list

## Structure

The refactor of the genome note writing scripts is centred on a typed internal model, which is converted into a context dictionary just before filling the Markdown template.

- `data_note/orchestrator.py` coordinates the workflow for each BioProject.
- `data_note/models/` contains typed data sections for base note information, assembly, sequencing, sampling, curation, taxonomy, annotation, quality, and author metadata.
- `data_note/models/note_data.py` combines these typed data sections into a single `NoteData` object during orchestration.
- `data_note/services/assembly_workflow_service.py`, `sequencing_workflow_service.py`, and `annotation_quality_workflow_service.py` contain the main workflow logic.
- `data_note/services/render_context_builder.py` converts the typed data sections into the final `NoteContext`, which is used to fill the template.
- `data_note/profiles/` defines project-specific behaviour for Darwin, Psyche, and ASG projects.
- `data_note/tables/` contains profile-specific table builders for the different projects.
- `data_note/services/figure_service.py` and the image helper modules handle profile-driven figure collection and naming separately from Markdown rendering.

The intended flow is:

```text
fetch/service layers -> typed models -> NoteData -> workflow services -> RenderContextBuilder -> NoteContext/dict -> Jinja2 template
```

For a small test run using the example files included in this repository, use:

```bash
python -m data_note --template_file tests/fixtures/template.md tests/fixtures/bioprojects.txt
```

This performs metadata searches, so it is not a completely offline example. Generated species folders are written into the current working directory.

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
- `DATA_NOTE_INCLUDE_GBIF_DISTRIBUTION` (`1` to enable optional GBIF distribution enrichment)
- `DATA_NOTE_CORRECTIONS_FILE`
- `DATA_NOTE_CYTO_INFO_TSV`
- `DATA_NOTE_LR_SAMPLE_PREP_TSV`
- `DATA_NOTE_AUTHOR_DB`

The assembly override variables mirror the CLI flags. Use either the primary/alternate pair or the haplotype 1/2 pair, not both. Like the CLI flags, they are only valid when the input resolves to exactly one BioProject.

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

- The core workflow is designed to work from public assembly project metadata.
- Data for each BioProject should be available in ENA using a structure matching the Earth BioGenome Project recommendation for a Species X assembly project (see https://www.earthbiogenome.org/report-on-assembly-standards).
- Assembly quality assets such as BlobToolKit, GenomeScope, Merqury run results, a chromosome map, ancestral linkage groups plots, and metagenome analyses are expected to exist already.
- Some local metadata lookup steps rely on internal data, and are not required for the public core workflow.
- Optional plant flow-cytometry data is expected at `DATA_NOTE_CYTO_INFO_TSV`, defaulting to `~/gn_assets/cyto_info.tsv`.
- Optional LR extraction spreadsheet data is expected at `DATA_NOTE_LR_SAMPLE_PREP_TSV`, defaulting to `~/gn_assets/LR_sample_prep.tsv` with a legacy fallback to `~/genome_note_templates/LR_sample_prep.tsv`.
- Templates are expected to be Markdown templates with Jinja2 placeholders and syntax.


## Repository layout

- [data_note](data_note/): the package code
- [data_note/services](data_note/services/): workflow components for assembly, taxonomy, annotation, sequencing, sampling, curation, quality, rendering, and context assembly
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

## Current status

- The package is run using `python -m data_note ...`.
- `darwin` is the default profile.
- The core workflow uses typed data sections for base note info, assembly, sequencing, sampling, curation, taxonomy, annotation, quality, and author metadata. These data sections are converted into the final template context by `RenderContextBuilder`.
- The orchestrator now coordinates dedicated workflow services rather than containing most of the workflow in one large script.
- `psyche` is a separate profile with its own table module and figure plan; it still shares much of the Darwin workflow where behaviour is the same.
- `asg` is now a separate profile with its own table/figure numbering, but metagenome-specific data collection and figure generation are not yet implemented in the core workflow.
- Collection of internal metadata depends on the availability of the required resources.


## Standards

This repository is informed by the [Genomic Standards Consortium’s MIxS standard](https://genomicsstandardsconsortium.github.io/mixs/) for sequence-associated metadata. Where appropriate, the workflow attempts to structure metadata in ways that are compatible with MIxS concepts and checklists, although it does not (yet) implement a complete formal MIxS schema.
