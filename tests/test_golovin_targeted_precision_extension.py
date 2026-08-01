import importlib.util
import sys
from pathlib import Path

from test_golovin_practical_convergence import synthetic_inputs

ROOT = Path(__file__).resolve().parents[1]
STAGE0_SCRIPT = ROOT / "scripts" / "golovin_stage0.py"
RESOLUTION_SCRIPT = ROOT / "scripts" / "analyze_golovin_resolution_convergence.py"
PRACTICAL_SCRIPT = ROOT / "scripts" / "analyze_golovin_practical_convergence.py"
TARGETED_SCRIPT = ROOT / "scripts" / "analyze_golovin_targeted_precision_extension.py"


def load_module():
    for name, filename in (
        ("golovin_stage0", STAGE0_SCRIPT),
        ("analyze_golovin_resolution_convergence", RESOLUTION_SCRIPT),
        ("analyze_golovin_practical_convergence", PRACTICAL_SCRIPT),
        ("analyze_golovin_targeted_precision_extension", TARGETED_SCRIPT),
    ):
        spec = importlib.util.spec_from_file_location(name, filename)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["analyze_golovin_targeted_precision_extension"]


def test_targeted_extension_reports_unequal_ensemble_design() -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs()
    retained = {
        row["run_label"]
        for row in matrix_rows
        if int(row["max_superdroplets"]) == 512
        or (int(row["max_superdroplets"]) == 1024 and int(row["member_index"]) < 3)
        or (int(row["max_superdroplets"]) == 2048 and int(row["member_index"]) < 2)
    }
    matrix_rows = [row for row in matrix_rows if row["run_label"] in retained]
    rows = [row for row in rows if row["run_label"] in retained]
    archives = {label: archive for label, archive in archives.items() if label in retained}
    config["matrix"]["members_per_resolution"] = {512: 4, 1024: 3, 2048: 2}
    config["practical_convergence"].pop("ensemble_prefixes")
    config["practical_convergence"].pop("final_prefixes_for_stability")
    config["practical_convergence"]["targeted_member_counts_by_resolution"] = {
        512: 4,
        1024: 3,
        2048: 2,
    }

    estimates, changes, sensitivity, decision = module.analyze_targeted_extension(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    assert estimates
    assert changes
    assert sensitivity
    assert decision["formal_convergence_claim_permitted"] is False
    assert decision["members_by_resolution"] == {"512": 4, "1024": 3, "2048": 2}
