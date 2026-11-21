"""Guard the single `async_update` template in fan.py (AST only, no HA import)."""

import ast
from pathlib import Path

FAN = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "xiaomi_miio_fan"
    / "fan.py"
)


def _classes() -> dict[str, ast.ClassDef]:
    tree = ast.parse(FAN.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def _methods(cls: ast.ClassDef) -> set[str]:
    return {
        n.name
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_only_base_class_defines_async_update():
    """Model classes customise `_apply_state`, never the polling wrapper."""
    owners = [n for n, c in _classes().items() if "async_update" in _methods(c)]
    assert owners == ["XiaomiGenericDevice"]


def test_every_concrete_fan_has_apply_state():
    """Each XiaomiFan* model class or one of its parents maps device state."""
    classes = _classes()

    def resolves(name: str) -> bool:
        cls = classes[name]
        if "_apply_state" in _methods(cls):
            return name != "XiaomiGenericDevice"
        return any(
            isinstance(b, ast.Name) and b.id in classes and resolves(b.id)
            for b in cls.bases
        )

    for name in classes:
        if name.startswith("XiaomiFan"):
            assert resolves(name), f"{name} has no _apply_state"
