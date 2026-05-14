<p align="center">
  <img src="assets/notes-icon.png" alt="data_note icon" width="200">
</p>

# Genome notes Markdown creation

`data_note` is a Python workflow for generating genome note documents in [Pandoc](https://pandoc.org/) Markdown from a list of BioProject accession numbers. It collects sampling, sequencing, taxonomy, assembly, annotation and quality metadata from public sources, with optional addition of metadata for methods and analyses from local systems. It then renders, for each BioProject, a species directory containing the note with associated figures and references in the required formats.

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

`plant` is the profile name for a subset of DToL notes. It adds plant flow cytometry metadata and works with plant-specific templates.


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

These overrides are useful when the assembly cannot be identified reliably from the BioProject metadata, e.g., if the BioProject structure is unusual or if there are several valid candidate assemblies after filtering.

To force an explicit assembly choice within one BioProject:

```bash
python -m data_note --template_file ~/genome_note_templates/dtol_template.md --assembly GCA_123456789.1 PRJEB12345
```

That tells the workflow to use the supplied primary assembly or haplotype 1 assembly accession for `PRJEB12345` and then infer the matching alternate or haplotype 2 when possible.

Rules for assembly overrides:

- use either `--assembly` with optional `--alt-assembly`, or `--hap1-assembly` with optional `--hap2-assembly`
- `--alt-assembly` requires `--assembly`
- `--hap2-assembly` requires `--hap1-assembly`
- the supplied accession must survive the normal taxon id and excluded-name filtering
- assembly override flags only work when the input resolves to exactly one BioProject, not a batch list

Taxonomy overrides:

The taxonomy override layer in `data_note/taxonomy_mapper.py` is for cases where the metadata are stale (often following a taxon merger) or inconsistent between sources.

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

The main coordination happens in `data_note/orchestrator.py`. Most of the fetching, lookup and text-building work is done in small modules under `data_note/services/`. The data collected along the way is kept in classes under `data_note/models/` until it is turned into the final template context for rendering.

Project-specific differences are kept in `data_note/profiles/` and `data_note/tables/`. Most of the package code lives in `data_note/`.

The overall flow is:

```text
fetch/service layers -> typed models -> NoteData -> workflow services -> RenderContextBuilder -> NoteContext/dict -> Jinja2 template
```

## Requirements

- `Python 3.10+`
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

Most runs are controlled by the BioProject input, the profile, and the Markdown template.

Environment variables are mainly for things that are local to a machine or lab setup: NCBI credentials, paths to local assets, optional portal/Jira access, and a few switches for sequencing summaries. The full list is in [.env.example](.env.example).

The minimum setup is:

- `ENTREZ_EMAIL`
- `ENTREZ_API_KEY`
- `DATA_NOTE_GN_ASSETS`, if your local assets are not in `~/gn_assets`

`DATA_NOTE_GN_ASSETS` is the base folder for local files such as software versions, text corrections, flow cytometry data, LR sample-prep data, and the author database. Individual paths can still be overridden when needed.

Sequencing summaries use public ENA/NCBI metadata by default, with an optional portal check where available. The default count style keeps paired-end Illumina libraries as read pairs. Both behaviours can be changed through `.env.example`.

Internal integrations are optional. The public workflow does not need portal, Jira, YAML cache, or server-side result access, but those hooks are there for local Tree of Life work.

## Wet lab protocol notes

`data_note` keeps a local copy of the published Sanger Tree of Life Wet Laboratory Protocol Collection V.3 in [data_note/wet_lab_protocols.py](data_note/wet_lab_protocols.py). During rendering, it adds likely protocol matches to the context and templates can insert `wet_lab_protocol_editor_comment` into the generated Markdown.

That comment is hidden in rendered output, but visible when editing the `.md` file. It lists the source metadata, likely protocol choices, any warnings, and the full published protocol catalog, so the methods prose can still be corrected by hand.

Ambiguous values such as `MagAttract Standard 48xrn` are flagged for review rather than silently treated as final.

## Assumptions and limitations

- The core workflow is designed to work from public assembly project metadata.
- Data for each BioProject should be available in ENA using a structure matching the Earth BioGenome Project recommendation for a Species X assembly project (see https://www.earthbiogenome.org/report-on-assembly-standards).
- Assembly quality assets such as BlobToolKit, GenomeScope, Merqury run results, a chromosome map, ancestral linkage groups plots, and metagenome analyses are expected to exist already.
- Some local metadata lookup steps rely on internal data, and are not required for the public core workflow.
- Optional local assets are expected under `~/gn_assets` unless configured otherwise.
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
