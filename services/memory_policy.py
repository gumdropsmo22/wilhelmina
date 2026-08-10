from __future__ import annotations

import os
from dataclasses import dataclass

VALID_COLLECTION_MODES = frozenset({"off", "interaction", "ambient"})
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class MemoryPolicyConfigurationError(RuntimeError):
    """Raised when memory collection configuration is contradictory or invalid."""


def _read_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise MemoryPolicyConfigurationError(f"{name} must be a boolean")


@dataclass(frozen=True)
class MemoryRuntimePolicy:
    """Fail-closed runtime switches for interaction and future ambient collection."""

    collection_mode: str = "off"
    ambient_enabled: bool = False
    ambient_approval_reference: str | None = None

    @classmethod
    def from_env(cls) -> "MemoryRuntimePolicy":
        mode = (os.getenv("MEMORY_COLLECTION_MODE", "off").strip() or "off").lower()
        if mode not in VALID_COLLECTION_MODES:
            allowed = ", ".join(sorted(VALID_COLLECTION_MODES))
            raise MemoryPolicyConfigurationError(
                f"MEMORY_COLLECTION_MODE must be one of: {allowed}"
            )
        approval = os.getenv("AMBIENT_MEMORY_APPROVAL_REFERENCE", "").strip() or None
        return cls(
            collection_mode=mode,
            ambient_enabled=_read_bool("ENABLE_AMBIENT_MEMORY", default=False),
            ambient_approval_reference=approval,
        )

    @property
    def interaction_collection_enabled(self) -> bool:
        """Whether direct/participating Wilhelmina interactions may enter extraction."""

        return self.collection_mode in {"interaction", "ambient"}

    @property
    def ambient_collection_ready(self) -> bool:
        """Require all three independent switches before ambient guild collection."""

        return (
            self.collection_mode == "ambient"
            and self.ambient_enabled
            and bool(self.ambient_approval_reference)
        )

    def require_ambient_collection_ready(self) -> None:
        if not self.ambient_collection_ready:
            raise MemoryPolicyConfigurationError(
                "Ambient memory requires MEMORY_COLLECTION_MODE=ambient, "
                "ENABLE_AMBIENT_MEMORY=true, and AMBIENT_MEMORY_APPROVAL_REFERENCE"
            )
