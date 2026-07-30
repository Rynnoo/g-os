"""Security policy shared by catalog validation and command construction.

Catalog data is intentionally not executable. Adding an installable application
requires both a catalog change and an explicit change to this allowlist.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

APPROVED_BACKEND = "flatpak"
APPROVED_REMOTE = "flathub"

# An app ID is bound to one exact Flatpak ref. A modified catalog therefore
# cannot substitute another otherwise-valid application ref.
APPROVED_FLATPAK_TARGETS: Mapping[str, str] = MappingProxyType(
    {
        "obs-studio": "com.obsproject.Studio",
        "chatterino": "com.chatterino.chatterino",
        "bottles": "com.usebottles.bottles",
    }
)


class AllowlistError(ValueError):
    """Raised when catalog data is outside G Store's fixed install policy."""


def validate_flatpak_target(
    app_id: str, backend: str, remote: str, ref: str
) -> None:
    """Require the exact approved backend, remote, app ID, and ref mapping."""

    if backend != APPROVED_BACKEND:
        raise AllowlistError(f"backend {backend!r} is not approved")
    if remote != APPROVED_REMOTE:
        raise AllowlistError(f"remote {remote!r} is not approved")

    approved_ref = APPROVED_FLATPAK_TARGETS.get(app_id)
    if approved_ref is None:
        raise AllowlistError(f"app {app_id!r} has no approved install target")
    if ref != approved_ref:
        raise AllowlistError(
            f"ref {ref!r} is not the approved target for app {app_id!r}"
        )
