import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_golovin_ensemble_size_adequacy.py"


def load_module():
    spec = importlib.util.spec_from_file_location("golovin_ensemble_size_adequacy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_operational_adequacy_uses_the_formal_resolution_decision(tmp_path: Path) -> None:
    module = load_module()
    decision = tmp_path / "resolution_decision.json"
    decision.write_text(
        '{"status": "selected_operational_resolution", "selected_max_superdroplets": 131072}\n',
        encoding="utf-8",
    )

    assert module.load_formal_target_resolution(decision) == 131072


def test_unselected_operational_resolution_cannot_define_adequacy_target(tmp_path: Path) -> None:
    module = load_module()
    decision = tmp_path / "resolution_decision.json"
    decision.write_text(
        '{"status": "no_operational_resolution_selected", "selected_max_superdroplets": null}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not contain an operational selection"):
        module.load_formal_target_resolution(decision)
