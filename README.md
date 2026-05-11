<p align="center">
  <img src="assets/notes-icon.png" alt="data_note icon" width="200">
</p>

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

These publishing steps require a separate Pandoc/typesetting workflow, such as [Inara](https://github.com/openjournals/inara/), [Seismica-sce-v2](https://github.com/WeAreSeismica/seismica-sce-v2), or the [pandoc-data-note](https://github.com/Karenvn/pandoc-data-note) package used for Tree of Life genome notes.

## Quick start

To run `data_note` from a list of BioProject accessions:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

## Common workflows

### Profiles

Different profiles have been created to generate different genome note features. The default profile is `darwin` for Darwin Tree of Life (DToL) genome notes.

For profile selection, use:

```bash
python -m data_note --profile darwin --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

`plant` is the profile name for a subset of DToL notes. It uses the Darwin table and figure plan, but gives plant notes a dedicated profile name so they can diverge later without affecting other DToL notes. It is also the profile that adds plant flow cytometry metadata. It works with plant-specific templates, e.g.:

```bash
python -m data_note --profile plant --template_file ~/genome_note_templates/dtol_plant_template.md bioprojects.txt
```

`psyche` is the profile name for Project Psyche genome notes. It has its own table module, with the first extracted differences from DToL:
- Table 3 adds assigned Merian elements and, for dual chromosome-level haplotypes, reports haplotype 1 only.
- Table 5 includes the extra Psyche software rows.
- Figures include a merian plot of chromosomes, generated via the [merian-busco-painter](https://github.com/Karenvn/merian-busco-painter) scripts.

`asg` is the profile name for Aquatic Symbiosis Genomics genome notes. It currently provides:
- ASG figure numbering, including dedicated numbers for metagenome figures.
- ASG table numbering, with software versions moved to `table6`.
- An optional metagenome `table5` hook driven by `metagenome_table_headers` and `metagenome_table_rows` when metagenome output is available.
- If there are enough metagenome bins, a tree of the bins is generated via [metagenome report](https://github.com/Karenvn/metagenome-report).

### Assembly selection overrides

By default, `data_note` takes an input file containing BioProject accessions and selects the primary assembly or haplotype 1 assembly automatically after taxon-id filtering, then chooses the matching alternate or haplotype 2 assembly.

To run `data_note` on a batch of BioProjects, with automatic selection of assemblies:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md bioprojects.txt
```

For cases where the automatic choice is not the genome of interest, the assembly accession number can be given for a single BioProject run:

- `--assembly GCA_...` and  `--alt-assembly GCA_...`
- `--hap1-assembly GCA_...` and `--hap2-assembly GCA_...`

The same override values can be supplied by setting environment variables:

- `DATA_NOTE_ASSEMBLY` and  `DATA_NOTE_ALT_ASSEMBLY`
- `DATA_NOTE_HAP1_ASSEMBLY` and `DATA_NOTE_HAP2_ASSEMBLY`

These runtime overrides are useful when the assembly cannot be identified reliably from the BioProject metadata, for example because the BioProject structure is unusual or there are several valid candidate assemblies after filtering.


To force an explicit assembly choice within one BioProject:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md \
--assembly GCA_123456789.1 PRJEB12345
```

That tells the workflow to use the supplied primary assembly or haplotype 1 assembly accession for `PRJEB12345` and then infer the matching alternate or haplotype 2 when possible.

Rules for assembly overrides:

- use either `--assembly` with optional `--alt-assembly`, or `--hap1-assembly` with optional `--hap2-assembly`
- `--alt-assembly` requires `--assembly`
- `--hap2-assembly` requires `--hap1-assembly`
- the supplied accession must survive the normal taxon id and excluded-name filtering
- assembly override flags and their environment-variable equivalents only work when the input resolves to exactly one BioProject, not a batch list

Taxonomy overrides:

The assembly overrides do not bypass the normal candidate taxon id filter. They only let you choose explicitly from assemblies that still count as relevant for that BioProject after taxon id and excluded-name filtering.

`data_note` is not intended to produce genome notes from genuinely misassigned organism records. If an assembly is under the wrong organism taxon id, the preferred approach is to wait for the public ENA and NCBI records to be corrected.

The taxonomy override layer in `data_note/taxonomy_mapper.py` is for a narrower problem: accepted taxonomy changes where some public metadata are stale (often following a taxon merger) or inconsistent between sources.

- use `TAX_ID_MAPPINGS` when merged or replacement taxon ids should still be treated as allowed for that species or BioProject
- use `BIOPROJECT_TAX_ID_OVERRIDES` when the umbrella BioProject taxon id itself is outdated and should be replaced before assembly selection
- these overrides are for cases such as taxon mergers, reclassifications, or outdated XML-layer metadata after a taxonomy update


### Automatic intro text

By default, the workflow generates `auto_text`, an introductory summary paragraph built by `SpeciesSummaryService` from NCBI taxonomy and NCBI Datasets assembly reports.

Depending on the taxon and the assemblies currently available at NCBI, this paragraph can:

- describe how many assemblies are available for the genus and family
- note whether other assemblies already exist for the same species
- mention RefSeq reference or representative status when NCBI reports it

Optional additions (separate from `auto_text`):

- the flag `--include-gbif-distribution` adds a `distribution_text` paragraph based on GBIF occurrence data when a matching GBIF usage key can be resolved (slow)
- the flag `--include-bold-barcode` adds a `barcode_text` paragraph from the external BOLD barcode workflow for a single BioProject run (very slow)


## Structure

For each BioProject, `data_note` collects assembly, taxonomy, sequencing, sampling and quality metadata, adds optional local information where it is available, prepares the required tables and figures, and then fills a Jinja2 Markdown template.

The main coordination happens in `data_note/orchestrator.py`. Most of the fetching, lookup and text-building work is done in small modules under `data_note/services/`. The data collected along the way is kept in classes under `data_note/models/` until it is turned into the final template context for rendering.

Project-specific differences are kept in `data_note/profiles/` and `data_note/tables/`. Most of the package code lives in `data_note/`.

The overall flow is:

```text
fetch/service layers -> typed models -> NoteData -> workflow services -> RenderContextBuilder -> NoteContext/dict -> Jinja2 template
```

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

## Configuration

`data_note` can be controlled in three places: the command line, environment variables, and the Markdown template given with `--template_file`. For most runs, the main choices are the profile, the template file, and whether to include optional text such as the GBIF distribution summary or the BOLD barcode paragraph.

Assembly overrides can be set either on the command line or through environment variables. The environment variables mirror the CLI flags: `DATA_NOTE_ASSEMBLY`, `DATA_NOTE_ALT_ASSEMBLY`, `DATA_NOTE_HAP1_ASSEMBLY`, and `DATA_NOTE_HAP2_ASSEMBLY`. Use either the primary/alternate pair or the haplotype 1/2 pair, not both. As with the CLI flags, these overrides only work when the input resolves to exactly one BioProject.

Text corrections, local asset files, and the author database also come from configuration rather than from fixed paths in the code. The current set of variables is shown in [.env.example](.env.example).

## Environment

The setup will need `ENTREZ_EMAIL` and `ENTREZ_API_KEY` to be set. The default profile is `darwin`, but it can be changed with `DATA_NOTE_PROFILE`.

Local file paths are usually taken from `DATA_NOTE_GN_ASSETS`, with `DATA_NOTE_SERVER_DATA` kept as a legacy alias. From that base location, `data_note` can also read per-assembly software-version files, a corrections file, a flow-cytometry table, a long-read sample preparation table, and an author database through `DATA_NOTE_SOFTWARE_VERSIONS_DIR`, `DATA_NOTE_CORRECTIONS_FILE`, `DATA_NOTE_CYTO_INFO_TSV`, `DATA_NOTE_LR_SAMPLE_PREP_TSV`, and `DATA_NOTE_AUTHOR_DB`. The software-version directory defaults to `~/gn_assets/software_versions`, and the corrections file defaults to `~/gn_assets/text_corrections.json`.

Optional text additions are controlled by `DATA_NOTE_INCLUDE_GBIF_DISTRIBUTION` and `DATA_NOTE_INCLUDE_BOLD_BARCODE`. If the BOLD workflow is not installed as a module, `DATA_NOTE_BOLD_REPO` can point to a checkout containing `bold_coi_pipeline.py`.

Sequencing summaries are based on public ENA/NCBI run metadata by default, with an optional internal portal enrichment layer. Set `DATA_NOTE_SEQUENCING_SOURCE` to choose the policy:

- `public`: use only ENA/NCBI metadata
- `public-with-portal`: keep public metadata, but repair missing or zero public counts from matched ToL Portal/TOLQC run data when available
- `portal`: prefer matched ToL Portal/TOLQC counts where available

Matched portal rows are filtered against the public run rows selected for the note. The workflow does not use ToLID-level portal aggregates directly, because portal relations can include multiplexed or misattributed run rows. Diagnostic fields such as `sequencing_portal_excluded_runs`, `sequencing_portal_unmatched_runs`, and `sequencing_portal_warnings` are written to the context CSV when portal data are inspected.

`DATA_NOTE_ILLUMINA_COUNT_UNIT` controls paired-end Illumina count reporting. The default, `read_pairs`, keeps the existing genome-note convention of counting a paired-end fragment/pair as one unit. Set it to `reads` to report individual reads instead.

Internal or machine-local integrations use `PORTAL_URL`, `PORTAL_API_PATH`, `JIRA_BASE_URL`, `JIRA_DOMAIN`, `YAML_CACHE_DIR`, `YAML_SSH_USER`, `YAML_SSH_HOST`, and `YAML_SSH_IDENTITY_FILE`. YAML files are refreshed into `YAML_CACHE_DIR` for inspection, but the remote path recorded in Jira remains the source of truth and the YAML is not copied into the output note folders.

Per-assembly software-version files can be YAML, JSON, CSV, or TSV. The expected local location is `~/gn_assets/software_versions/<tolid>.yml`; flat context keys such as `treeval_version` are accepted, as are raw TreeVal-style nested mappings such as `PROCESS_NAME: {tool: version}`. To collect TreeVal output on a server, run `scripts/collect_assembly_software_versions.py <tolid> --run-dir <treeval_outdir>` or use `--work-root <assembly_work_root>` when the exact output directory is not known.

If you are using the Ensembl transition code, the related variables are `GN_DEBUG_ENSEMBL`, `GN_ENSEMBL_GRAPHQL_URL`, `GN_ENSEMBL_ORGANISMS_BASE`, `GN_ENSEMBL_MAIN_GFF3_BASE`, and `GN_ENSEMBL_MAIN_GTF_BASE`.

## Assumptions and limitations

- The core workflow is designed to work from public assembly project metadata.
- Data for each BioProject should be available in ENA using a structure matching the Earth BioGenome Project recommendation for a Species X assembly project (see https://www.earthbiogenome.org/report-on-assembly-standards).
- Assembly quality assets such as BlobToolKit, GenomeScope, Merqury run results, a chromosome map, ancestral linkage groups plots, and metagenome analyses are expected to exist already.
- Some local metadata lookup steps rely on internal data, and are not required for the public core workflow.
- Optional plant flow-cytometry data is expected at `DATA_NOTE_CYTO_INFO_TSV`, defaulting to `~/gn_assets/cyto_info.tsv`.
- Optional per-assembly software versions are expected at `DATA_NOTE_SOFTWARE_VERSIONS_DIR`, defaulting to `~/gn_assets/software_versions`.
- Optional text corrections are expected at `DATA_NOTE_CORRECTIONS_FILE`, defaulting to `~/gn_assets/text_corrections.json`.
- Optional LR extraction spreadsheet data is expected at `DATA_NOTE_LR_SAMPLE_PREP_TSV`, defaulting to `~/gn_assets/LR_sample_prep.tsv` with a legacy fallback to `~/genome_note_templates/LR_sample_prep.tsv`.
- Templates are expected to be Markdown templates with Jinja2 placeholders and syntax.


## Tests and example data

Minimal unit tests can be run with:

```bash
python -m unittest discover -s tests
```

The repository also includes:

- [tests/fixtures](tests/fixtures/): a small template and BioProject list for test runs
- [tests/output](tests/output/): lightweight representative output folders kept for structure and discussion, not as strict golden-master outputs

For a small run using the example files included in this repository, use:

```bash
python -m data_note --template_file tests/fixtures/template.md tests/fixtures/bioprojects.txt
```

This performs metadata searches, so it is not a completely offline example. Generated species folders are written into the current working directory.


## Standards

This repository is informed by the [Genomic Standards Consortium’s MIxS standard](https://genomicsstandardsconsortium.github.io/mixs/) for sequence-associated metadata. Where appropriate, the workflow attempts to structure metadata in ways that are compatible with MIxS concepts and checklists, although it does not (yet) implement a complete formal MIxS schema.
