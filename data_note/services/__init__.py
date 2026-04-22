__all__ = [
    "AnnotationService",
    "AnnotationQualityWorkflowService",
    "AuthorService",
    "AssemblyService",
    "AssemblyWorkflowService",
    "BtkService",
    "ChromosomeService",
    "ContextAssembler",
    "CurationService",
    "FigureService",
    "FlowCytometryService",
    "LocalMetadataService",
    "NcbiDatasetsService",
    "RenderContextBuilder",
    "RenderingService",
    "SequencingFetchService",
    "SequencingService",
    "SequencingWorkflowService",
    "ServerDataService",
    "TaxonomyService",
]


def __getattr__(name: str):
    if name == "AnnotationService":
        from .annotation_service import AnnotationService

        return AnnotationService
    if name == "AnnotationQualityWorkflowService":
        from .annotation_quality_workflow_service import AnnotationQualityWorkflowService

        return AnnotationQualityWorkflowService
    if name == "AuthorService":
        from .author_service import AuthorService

        return AuthorService
    if name == "AssemblyService":
        from .assembly_service import AssemblyService

        return AssemblyService
    if name == "AssemblyWorkflowService":
        from .assembly_workflow_service import AssemblyWorkflowService

        return AssemblyWorkflowService
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
    if name == "FigureService":
        from .figure_service import FigureService

        return FigureService
    if name == "FlowCytometryService":
        from .flow_cytometry_service import FlowCytometryService

        return FlowCytometryService
    if name == "LocalMetadataService":
        from .local_metadata_service import LocalMetadataService

        return LocalMetadataService
    if name == "NcbiDatasetsService":
        from .ncbi_datasets_service import NcbiDatasetsService

        return NcbiDatasetsService
    if name == "RenderContextBuilder":
        from .render_context_builder import RenderContextBuilder

        return RenderContextBuilder
    if name == "RenderingService":
        from .rendering_service import RenderingService

        return RenderingService
    if name == "SequencingFetchService":
        from .sequencing_fetch_service import SequencingFetchService

        return SequencingFetchService
    if name == "SequencingService":
        from .sequencing_service import SequencingService

        return SequencingService
    if name == "SequencingWorkflowService":
        from .sequencing_workflow_service import SequencingWorkflowService

        return SequencingWorkflowService
    if name == "ServerDataService":
        from .server_data_service import ServerDataService

        return ServerDataService
    if name == "TaxonomyService":
        from .taxonomy_service import TaxonomyService

        return TaxonomyService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
