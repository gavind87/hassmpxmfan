"""Tests for the model -> (client, entity) lookup table."""

import pytest

from custom_components.xiaomi_miio_fan.const import SUPPORTED_MODELS
from custom_components.xiaomi_miio_fan.fan import (
    XiaomiGenericDevice,
    _build_device,
    _model_spec,
    build_fan_client,
    get_available_attributes,
)


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_every_supported_model_resolves(model):
    """Every model advertised in SUPPORTED_MODELS must map to a client + entity."""
    spec = _model_spec(model)
    assert spec is not None, f"{model} is listed as supported but has no spec"
    _client_cls, _client_model, entity_cls = spec
    assert issubclass(entity_cls, XiaomiGenericDevice)


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_entity_can_be_built_without_touching_the_device(model):
    """Entity construction must be side-effect free (relied on by __init__.py)."""
    entity = _build_device(None, model, "Test fan", "uid", 3, None)
    assert isinstance(entity, XiaomiGenericDevice)
    assert entity.unique_id == "uid"


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_available_attributes_is_a_dict(model):
    """The sensor platforms rely on this returning a (possibly empty) dict."""
    assert isinstance(get_available_attributes(model), dict)


def test_unknown_model_is_unsupported():
    """An unknown model must return None / empty rather than raising."""
    assert _model_spec("acme.fan.nope") is None
    assert build_fan_client("127.0.0.1", "0" * 32, "acme.fan.nope") is None
    assert _build_device(None, "acme.fan.nope", "n", "u", 3, None) is None
    assert get_available_attributes("acme.fan.nope") == {}
