__all__ = [
    "AuthorService",
    "AssemblyService",
    "BtkService",
    "ChromosomeService",
    "ContextAssembler",
    "CurationService",
    "LocalMetadataService",
    "NcbiDatasetsService",
    "RenderingService",
    "SequencingService",
    "ServerDataService",
    "TaxonomyService",
]


def __getattr__(name: str):
    if name == "AuthorService":
        from .author_service import AuthorService

        return AuthorService
    if name == "AssemblyService":
        from .assembly_service import AssemblyService

        return AssemblyService
    if name == "BtkService":
        from .btk_service import BtkService

        return BtkService
    if name == "ChromosomeService":
        from .chromosome_service import ChromosomeService

        return ChromosomeService
    if name == "ContextAssembler":
        from .context_assembler import ContextAssembler

        return ContextAssembler
    if name == "CurationService":
        from .curation_service import CurationService

        return CurationService
    if name == "LocalMetadataService":
        from .local_metadata_service import LocalMetadataService

        return LocalMetadataService
    if name == "NcbiDatasetsService":
        from .ncbi_datasets_service import NcbiDatasetsService

        return NcbiDatasetsService
    if name == "RenderingService":
        from .rendering_service import RenderingService

        return RenderingService
    if name == "SequencingService":
        from .sequencing_service import SequencingService

        return SequencingService
    if name == "ServerDataService":
        from .server_data_service import ServerDataService

        return ServerDataService
    if name == "TaxonomyService":
        from .taxonomy_service import TaxonomyService

        return TaxonomyService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
