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


def test_adequacy_plot_supports_a_projected_resolution_below_target(tmp_path: Path) -> None:
    module = load_module()
    output = tmp_path / "adequacy.png"
    selection_rows = [
        {"ensemble_size": 49, "selected_max_superdroplets": 131072},
        {"ensemble_size": 50, "selected_max_superdroplets": 65536},
    ]
    limiting_rows = [
        {
            "ensemble_size": count,
            "metric": metric,
            "worst_formal_gate_ratio": 0.8,
        }
        for count in (49, 50)
        for metric in ("ensemble_mean_l1_bins_500", module.M0, module.M6)
    ]
    decision = {
        "target_selected_resolution": 131072,
        "smallest_retrospectively_supported_tested_ensemble_size": None,
    }

    module.plot_result(selection_rows, limiting_rows, decision, output)

    assert output.is_file()
    assert output.stat().st_size > 0
