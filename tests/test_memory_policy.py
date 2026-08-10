import pytest

from services import memory_policy


def test_memory_collection_defaults_fail_closed(monkeypatch) -> None:
    for name in (
        "MEMORY_COLLECTION_MODE",
        "ENABLE_AMBIENT_MEMORY",
        "AMBIENT_MEMORY_APPROVAL_REFERENCE",
    ):
        monkeypatch.delenv(name, raising=False)

    policy = memory_policy.MemoryRuntimePolicy.from_env()

    assert policy.collection_mode == "off"
    assert policy.interaction_collection_enabled is False
    assert policy.ambient_collection_ready is False


def test_interaction_mode_enables_only_participating_interactions(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    monkeypatch.setenv("ENABLE_AMBIENT_MEMORY", "true")
    monkeypatch.setenv("AMBIENT_MEMORY_APPROVAL_REFERENCE", "approval-123")

    policy = memory_policy.MemoryRuntimePolicy.from_env()

    assert policy.interaction_collection_enabled is True
    assert policy.ambient_collection_ready is False


@pytest.mark.parametrize(
    ("mode", "enabled", "approval"),
    [
        ("ambient", "false", "approval-123"),
        ("ambient", "true", ""),
        ("interaction", "true", "approval-123"),
    ],
)
def test_ambient_memory_requires_all_independent_gates(
    monkeypatch,
    mode,
    enabled,
    approval,
) -> None:
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", mode)
    monkeypatch.setenv("ENABLE_AMBIENT_MEMORY", enabled)
    monkeypatch.setenv("AMBIENT_MEMORY_APPROVAL_REFERENCE", approval)

    policy = memory_policy.MemoryRuntimePolicy.from_env()

    assert policy.ambient_collection_ready is False
    with pytest.raises(memory_policy.MemoryPolicyConfigurationError, match="Ambient memory"):
        policy.require_ambient_collection_ready()


def test_ambient_memory_is_ready_only_when_every_gate_is_present(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "ambient")
    monkeypatch.setenv("ENABLE_AMBIENT_MEMORY", "true")
    monkeypatch.setenv("AMBIENT_MEMORY_APPROVAL_REFERENCE", "discord-review-approval")

    policy = memory_policy.MemoryRuntimePolicy.from_env()

    assert policy.interaction_collection_enabled is True
    assert policy.ambient_collection_ready is True
    policy.require_ambient_collection_ready()


def test_invalid_collection_mode_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "everywhere-bitch")

    with pytest.raises(
        memory_policy.MemoryPolicyConfigurationError,
        match="MEMORY_COLLECTION_MODE",
    ):
        memory_policy.MemoryRuntimePolicy.from_env()


def test_invalid_ambient_boolean_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_AMBIENT_MEMORY", "maybe")

    with pytest.raises(memory_policy.MemoryPolicyConfigurationError, match="boolean"):
        memory_policy.MemoryRuntimePolicy.from_env()
