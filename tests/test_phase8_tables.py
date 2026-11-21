"""Guard the per-model tables in select.py / number.py (AST only, no HA import)."""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "custom_components" / "xiaomi_miio_fan"


def _tree(name: str) -> ast.Module:
    return ast.parse((PKG / name).read_text(encoding="utf-8"))


def _fan_classes() -> set[str]:
    return {n.name for n in _tree("fan.py").body if isinstance(n, ast.ClassDef)}


def _table_keys(module: str, var: str) -> list[str]:
    for node in _tree(module).body:
        if (
            isinstance(node, ast.AnnAssign)
            and getattr(node.target, "id", None) == var
            and isinstance(node.value, ast.Dict)
        ):
            return [k.value for k in node.value.keys]
    raise AssertionError(f"{var} not found in {module}")


def test_angle_table_names_real_entity_classes():
    """A typo'd class name would silently hide the select for that model."""
    assert set(_table_keys("select.py", "ANGLES_BY_ENTITY_CLASS")) <= _fan_classes()


def test_delay_max_table_names_real_entity_classes():
    """Same guard for the delay-off maximum table."""
    assert (
        set(_table_keys("number.py", "MAX_MINUTES_BY_ENTITY_CLASS")) <= _fan_classes()
    )


def test_rotate_table_names_real_entity_classes():
    """Same guard for the rotate-button table."""
    assert set(_table_keys("button.py", "ROTATE_VIA_DIRECTION")) <= _fan_classes()
