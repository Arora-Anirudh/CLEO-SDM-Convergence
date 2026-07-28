import re
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
CLEO_COMMIT = "83318c23223546d10759d202d70f4fa2f7fe4688"


def load_reference_config() -> dict:
    yaml = YAML(typ="safe")
    with (ROOT / "config" / "collisions0d_reference.yaml").open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def test_cleo_dependency_is_canonical_and_pinned() -> None:
    cmake = (ROOT / "src" / "extern" / "cleo" / "CMakeLists.txt").read_text()
    assert "https://github.com/yoctoyotta1024/CLEO.git" in cmake
    assert CLEO_COMMIT in cmake
    assert "refs/heads/main" not in cmake
    assert re.fullmatch(r"[0-9a-f]{40}", CLEO_COMMIT)


def test_reference_initializer_matches_collisions0d() -> None:
    supers = load_reference_config()["python_initconds"]["supers"]
    assert supers == {
        "dryradius": 1.0e-16,
        "rspan": [1.0e-6, 7.5e-5],
        "xi_min": 10,
        "volexpr0": 30.531e-6,
        "numconc": 8388608,
    }


def test_reference_model_is_one_collision_box() -> None:
    config = load_reference_config()
    assert config["domain"]["ngbxs"] == 1
    assert config["domain"]["maxnsupers"] > 0
    assert config["timesteps"]["COLLTSTEP"] > 0
    assert config["timesteps"]["OBSTSTEP"] > 0
    assert config["timesteps"]["T_END"] >= config["timesteps"]["OBSTSTEP"]


def test_both_kernel_targets_are_declared() -> None:
    cmake = (ROOT / "src" / "collisions0d" / "CMakeLists.txt").read_text()
    assert "collisions0d_golovin" in cmake
    assert "collisions0d_long" in cmake
