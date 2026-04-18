from .config import AppConfig, load_config

__all__ = ["AppConfig", "DataNotePipeline", "load_config"]


def __getattr__(name: str):
    if name == "DataNotePipeline":
        from .pipeline import DataNotePipeline

        return DataNotePipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
