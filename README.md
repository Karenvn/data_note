# Genome notes workflow

`data_note` is a Python workflow for generating publication-oriented genome note markdown from BioProject accession numbers. It collects assembly, sequencing, taxonomy and quality metadata from public sources, with optional addition of metadata from local systems, and renders a Pandoc-ready markdown note together with associated figures and context data.

The repository is designed for genome note preparation rather than genome analysis. It treats metadata integration, text generation, figure preparation and standards-aware note assembly as a distinct workflow, separate from upstream pipelines that produce assembly and quality assessment outputs.

## Scope

This repository covers:

- BioProject-driven metadata collection
- assembly and sequencing summaries
- fetching local metadata from JIRA / ToL Portal / local files
- markdown note generation
- figure and table preparation needed by the markdown note

This repository does not aim to cover:

- Pandoc-to-docx / PDF / JATS conversion
- BibTeX cleanup and publication-specific bibliography repair
- final publication packaging

Those publishing steps are better treated as a separate Pandoc/typesetting workflow.

## Quick start

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

This runs the package entrypoint directly.

For a lightweight in-repo smoke-test run, use the fixture files and do:

```bash
python -m data_note --template_file tests/fixtures/template.md tests/fixtures/bioprojects.txt
```

This still performs live metadata lookups. By default, generated species folders are written into the current working directory.

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

Optional local integrations may also require:

- `tol-sdk`
- JIRA credentials in `~/.netrc`
- local access to internal YAML and results files

## Environment

The main runtime configuration is environment-variable based. See [.env.example](.env.example) for the current set.

Important variables include:

- `ENTREZ_EMAIL`
- `ENTREZ_API_KEY`
- `DATA_NOTE_GN_ASSETS` (preferred)
- `DATA_NOTE_SERVER_DATA` (legacy alias)
- `DATA_NOTE_CORRECTIONS_FILE`
- `DATA_NOTE_LR_SAMPLE_PREP_TSV`
- `DATA_NOTE_AUTHOR_DB`

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

## Assumptions and limitations

- The core pipeline is designed to work from public assembly project metadata.
- Data for each BioProject should be available in ENA using a structure matching the Earth BioGenome Project recommendation for a Species X assembly project (see https://www.earthbiogenome.org/report-on-assembly-standards).
- Assembly quality assets such as BlobToolKit, GenomeScope, Merqury, a chromosome map, ancestral linkage groups plots, and metagenome analyses are expected to exist already.
- Templates are expected to be Jinja2-based markdown templates.
- Some local enrichment paths are institution-specific and are not required for the public core pipeline.

## Repository Layout

- [data_note](data_note/): the package code
- [data_note/services](data_note/services/): service-layer components for assembly, taxonomy, sequencing, rendering, BTK, and local data
- [data_note/models](data_note/models/): typed models such as `NoteContext`
- [tests](tests/): minimal unit tests, fixtures and representative output folders
- [.env.example](.env.example): example environment configuration

## Tests and example data

Minimal unit tests can be run with:

```bash
python -m unittest discover -s tests
```

The repository also includes:

- [tests/fixtures](tests/fixtures/): a small template and BioProject list for smoke-test runs
- [tests/output](tests/output/): lightweight representative output folders kept for structure and discussion, not as strict golden-master outputs

## Current Status

- The supported entrypoint is `python -m data_note ...`.
- Internal integrations are environment dependent.
- Automated regression testing is still limited.

## Standards

This repository is informed by the Genomic Standards Consortium’s MIxS standard for sequence-associated contextual metadata. Where appropriate, the workflow attempts to structure metadata in ways that are compatible with MIxS concepts and checklists, although it does not yet implement a complete formal MIxS schema.
