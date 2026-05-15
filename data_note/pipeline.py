from __future__ import annotations

from pathlib import Path

from .orchestrator import DataNoteOrchestrator
from .config import AppConfig, load_config


class DataNotePipeline:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_config()
        self._orchestrator: DataNoteOrchestrator | None = None

    def process_bioproject(self, bioproject: str):
        return self.process_bioproject_result(bioproject).context

    def process_bioproject_result(self, bioproject: str):
        return self._orchestrator_instance().process_bioproject_result(bioproject)

    def run(self, bioproject_input: str, template_file: str, error_file: str = "error_log.txt") -> int:
        orchestrator = self._orchestrator_instance()
        bioproject_list = orchestrator.read_bioproject_input(bioproject_input)
        if self.config.assembly_selection_input() is not None and len(bioproject_list) != 1:
            raise ValueError(
                "Assembly selection overrides require exactly one BioProject input, not a list"
            )

        with open(error_file, "w") as error_log:
            for bioproject in bioproject_list:
                try:
                    print(f"Processing BioProject: {bioproject}")
                    processed = self.process_bioproject_result(bioproject)
                    context = processed.context

                    assemblies_type = context.get("assemblies_type")
                    if assemblies_type in ["prim_alt", "hap_asm"]:
                        try:
                            genome_note_dir = orchestrator.write_note(template_file, context)
                            if genome_note_dir:
                                output_csv = Path(genome_note_dir) / f"{bioproject}_context.csv"
                                output_json = Path(genome_note_dir) / f"{bioproject}_context.json"
                                output_note_data_json = Path(genome_note_dir) / f"{bioproject}_note_data.json"
                                orchestrator.write_context_csv(context, str(output_csv))
                                orchestrator.write_context_json(context, str(output_json))
                                orchestrator.write_note_data_json(
                                    processed.note_data,
                                    str(output_note_data_json),
                                )
                        except Exception as exc:
                            error_message = f"Error in write_note for BioProject {bioproject}: {exc}\n"
                            error_log.write(error_message)
                            print(error_message)
                except Exception as exc:
                    error_message = f"Error processing BioProject {bioproject}: {exc}\n"
                    error_log.write(error_message)
                    print(error_message)

        print(f"Processing completed. Errors logged to {error_file}.")
        return 0

    def _orchestrator_instance(self):
        if self._orchestrator is None:
            self.config.apply_environment()
            self._orchestrator = DataNoteOrchestrator(
                profile=self.config.profile_name,
                include_gbif_distribution=self.config.include_gbif_distribution,
                include_bold_barcode=self.config.include_bold_barcode,
                sequencing_source=self.config.sequencing_source,
                illumina_count_unit=self.config.illumina_count_unit,
                assembly_selection_input=self.config.assembly_selection_input(),
            )
        return self._orchestrator
