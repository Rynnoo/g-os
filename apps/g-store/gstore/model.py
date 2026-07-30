"""Pure-Python G Store catalog model and strict JSON validation."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

from .security import AllowlistError, validate_flatpak_target

SUPPORTED_SCHEMA_VERSION = 1
VALID_STATUSES = frozenset({"available", "planned", "disabled"})
_APP_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_TOP_LEVEL_KEYS = frozenset({"schema_version", "apps"})
_APP_KEYS = frozenset(
    {
        "id",
        "name",
        "summary",
        "description",
        "category",
        "status",
        "enabled",
        "tags",
        "homepage",
        "source",
        "notes",
        "install",
    }
)
_INSTALL_KEYS = frozenset({"backend", "remote", "ref"})


class CatalogValidationError(ValueError):
    """Raised when a catalog does not match the supported, safe data format."""


@dataclass(frozen=True, slots=True)
class InstallSpec:
    backend: str
    remote: str
    ref: str


@dataclass(frozen=True, slots=True)
class AppEntry:
    id: str
    name: str
    summary: str
    description: str
    category: str
    status: str
    enabled: bool
    tags: tuple[str, ...]
    homepage: str | None
    source: str | None
    notes: str
    install: InstallSpec | None

    @property
    def installable(self) -> bool:
        """Whether the UI may offer install/remove actions for this entry."""

        return self.enabled and self.status == "available" and self.install is not None

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (
                self.id,
                self.name,
                self.summary,
                self.description,
                self.category,
                self.notes,
                *self.tags,
            )
        ).casefold()


@dataclass(frozen=True, slots=True)
class Catalog:
    schema_version: int
    apps: tuple[AppEntry, ...]
    _apps_by_id: Mapping[str, AppEntry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_apps_by_id",
            MappingProxyType({app.id: app for app in self.apps}),
        )

    def get(self, app_id: str) -> AppEntry:
        try:
            return self._apps_by_id[app_id]
        except KeyError as exc:
            raise KeyError(f"unknown G Store app ID: {app_id}") from exc

    def search(self, query: str) -> tuple[AppEntry, ...]:
        """Return entries containing every whitespace-delimited search term."""

        terms = tuple(part.casefold() for part in query.split() if part)
        if not terms:
            return self.apps
        return tuple(
            app for app in self.apps if all(term in app.searchable_text for term in terms)
        )


def _require_object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogValidationError(f"{where} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise CatalogValidationError(f"{where} contains a non-string key")
    return value


def _require_exact_keys(
    value: Mapping[str, Any], expected: frozenset[str], where: str
) -> None:
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise CatalogValidationError(
            f"{where} is missing required field(s): {', '.join(sorted(missing))}"
        )
    if unknown:
        raise CatalogValidationError(
            f"{where} contains unknown field(s): {', '.join(sorted(unknown))}"
        )


def _require_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{where} must be a non-empty string")
    if "\x00" in value:
        raise CatalogValidationError(f"{where} must not contain NUL characters")
    return value.strip()


def _optional_https_url(value: Any, where: str) -> str | None:
    if value is None:
        return None
    url = _require_text(value, where)
    if not url.startswith("https://"):
        raise CatalogValidationError(f"{where} must use https://")
    return url


def _parse_install(app_id: str, raw: Any, where: str) -> InstallSpec:
    install = _require_object(raw, where)
    _require_exact_keys(install, _INSTALL_KEYS, where)
    backend = _require_text(install["backend"], f"{where}.backend")
    remote = _require_text(install["remote"], f"{where}.remote")
    ref = _require_text(install["ref"], f"{where}.ref")
    try:
        validate_flatpak_target(app_id, backend, remote, ref)
    except AllowlistError as exc:
        raise CatalogValidationError(f"{where}: {exc}") from exc
    return InstallSpec(backend=backend, remote=remote, ref=ref)


def _parse_app(raw: Any, index: int) -> AppEntry:
    where = f"apps[{index}]"
    data = _require_object(raw, where)
    _require_exact_keys(data, _APP_KEYS, where)

    app_id = _require_text(data["id"], f"{where}.id")
    if not _APP_ID_PATTERN.fullmatch(app_id):
        raise CatalogValidationError(
            f"{where}.id must contain lowercase letters, numbers, and single hyphens"
        )

    status = _require_text(data["status"], f"{where}.status")
    if status not in VALID_STATUSES:
        raise CatalogValidationError(
            f"{where}.status must be one of {', '.join(sorted(VALID_STATUSES))}"
        )

    enabled = data["enabled"]
    if type(enabled) is not bool:
        raise CatalogValidationError(f"{where}.enabled must be a boolean")

    raw_tags = data["tags"]
    if not isinstance(raw_tags, list):
        raise CatalogValidationError(f"{where}.tags must be an array")
    tags = tuple(
        _require_text(tag, f"{where}.tags[{tag_index}]")
        for tag_index, tag in enumerate(raw_tags)
    )
    if len(set(tags)) != len(tags):
        raise CatalogValidationError(f"{where}.tags must not contain duplicates")

    raw_install = data["install"]
    if status == "available":
        if not enabled:
            raise CatalogValidationError(f"{where} is available but not enabled")
        if raw_install is None:
            raise CatalogValidationError(f"{where} is available but has no install spec")
        install = _parse_install(app_id, raw_install, f"{where}.install")
    else:
        if enabled:
            raise CatalogValidationError(
                f"{where} is {status!r} and therefore cannot be enabled"
            )
        if raw_install is not None:
            raise CatalogValidationError(
                f"{where} is {status!r} and therefore cannot contain install data"
            )
        install = None

    return AppEntry(
        id=app_id,
        name=_require_text(data["name"], f"{where}.name"),
        summary=_require_text(data["summary"], f"{where}.summary"),
        description=_require_text(data["description"], f"{where}.description"),
        category=_require_text(data["category"], f"{where}.category"),
        status=status,
        enabled=enabled,
        tags=tags,
        homepage=_optional_https_url(data["homepage"], f"{where}.homepage"),
        source=_optional_https_url(data["source"], f"{where}.source"),
        notes=_require_text(data["notes"], f"{where}.notes"),
        install=install,
    )


def parse_catalog(raw: Any) -> Catalog:
    """Parse already-decoded JSON into an immutable, validated catalog."""

    data = _require_object(raw, "catalog")
    _require_exact_keys(data, _TOP_LEVEL_KEYS, "catalog")

    version = data["schema_version"]
    if type(version) is not int or version != SUPPORTED_SCHEMA_VERSION:
        raise CatalogValidationError(
            f"catalog.schema_version must be {SUPPORTED_SCHEMA_VERSION}"
        )

    raw_apps = data["apps"]
    if not isinstance(raw_apps, list) or not raw_apps:
        raise CatalogValidationError("catalog.apps must be a non-empty array")

    apps = tuple(_parse_app(raw_app, index) for index, raw_app in enumerate(raw_apps))
    app_ids = [app.id for app in apps]
    if len(set(app_ids)) != len(app_ids):
        duplicates = sorted({app_id for app_id in app_ids if app_ids.count(app_id) > 1})
        raise CatalogValidationError(
            f"catalog.apps contains duplicate ID(s): {', '.join(duplicates)}"
        )
    return Catalog(schema_version=version, apps=apps)


def load_catalog(path: str | Path) -> Catalog:
    """Read and validate a UTF-8 catalog JSON file."""

    catalog_path = Path(path)
    try:
        with catalog_path.open("r", encoding="utf-8") as catalog_file:
            raw = json.load(catalog_file)
    except OSError as exc:
        raise CatalogValidationError(f"cannot read catalog {catalog_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogValidationError(
            f"catalog {catalog_path} is not valid JSON: {exc}"
        ) from exc
    return parse_catalog(raw)
