"""Core model and safe installer primitives for G Store."""

from .installer import FlatpakInstaller, InstallNotAllowed, Operation
from .model import AppEntry, Catalog, CatalogValidationError, load_catalog

__all__ = [
    "AppEntry",
    "Catalog",
    "CatalogValidationError",
    "FlatpakInstaller",
    "InstallNotAllowed",
    "Operation",
    "load_catalog",
]
