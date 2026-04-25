from __future__ import annotations

from pathlib import Path

from .orchestrator import DataNoteOrchestrator
from .config import AppConfig, load_config


class DataNotePipeline:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_config()
        self._orchestrator: DataNoteOrchestrator | None = None

    def process_bioproject(self, bioproject: str):
        return self._orchestrator_instance().process_bioproject(bioproject)

    def run(self, bioproject_file: str, template_file: str, error_file: str = "error_log.txt") -> int:
        orchestrator = self._orchestrator_instance()
        bioproject_list = orchestrator.read_bioprojects_file(bioproject_file)

        with open(error_file, "w") as error_log:
            for bioproject in bioproject_list:
                try:
                    print(f"Processing BioProject: {bioproject}")
                    context = self.process_bioproject(bioproject)

                    assemblies_type = context.get("assemblies_type")
                    if assemblies_type in ["prim_alt", "hap_asm"]:
                        try:
                            genome_note_dir = orchestrator.write_note(template_file, context)
                            if genome_note_dir:
                                output_csv = Path(genome_note_dir) / f"{bioproject}_context.csv"
                                orchestrator.write_context_csv(context, str(output_csv))
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
                assembly_selection_input=self.config.assembly_selection_input(),
            )
        return self._orchestrator
