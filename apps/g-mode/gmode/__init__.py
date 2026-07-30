"""Core, GUI-independent APIs for G Mode."""

from .model import (
    AppRequirement,
    GModeProfile,
    LayoutPlan,
    MonitorPlacement,
    ObsSettings,
    ProfileRepository,
    ProfileValidationError,
    SessionToggles,
    load_profile,
)

__all__ = [
    "AppRequirement",
    "GModeProfile",
    "LayoutPlan",
    "MonitorPlacement",
    "ObsSettings",
    "ProfileRepository",
    "ProfileValidationError",
    "SessionToggles",
    "load_profile",
]

__version__ = "0.1.0"
