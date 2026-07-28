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

    patch = ROOT / "patches" / "cleo" / "0001-add-explicit-collision-rng-seed.patch"
    assert patch.is_file()
    patch_content = patch.read_text(encoding="utf-8")
    assert "libs/superdrops/collisions/collisions.hpp" in patch_content
    assert "genpool(seed)" in patch_content
    assert "scaled_probability" not in patch_content


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


def test_levante_scripts_are_project_owned_and_account_neutral() -> None:
    levante_directory = ROOT / "scripts" / "levante"
    expected = {
        "README.md",
        "analyze_collisions0d.sbatch",
        "build.sbatch",
        "common.sh",
        "run_collisions0d.sbatch",
        "run_golovin_matrix.sbatch",
        "validate_collision_seed_replay.sbatch",
    }
    assert expected <= {path.name for path in levante_directory.iterdir()}

    for script_name in ("build.sbatch", "run_collisions0d.sbatch"):
        content = (levante_directory / script_name).read_text(encoding="utf-8")
        assert "#SBATCH --account=" not in content
        assert "mh0731" not in content
        assert "/home/m/m300950" not in content


def test_slurm_entrypoints_resolve_common_from_explicit_project_root() -> None:
    levante_directory = ROOT / "scripts" / "levante"
    for script_name in (
        "build.sbatch",
        "run_collisions0d.sbatch",
        "run_golovin_matrix.sbatch",
        "analyze_collisions0d.sbatch",
    ):
        content = (levante_directory / script_name).read_text(encoding="utf-8")
        expected = 'SCRIPT_DIR="${CLEO_SDM_PROJECT_ROOT}/scripts/levante"'
        assert expected in content
        assert content.index(expected) < content.index('source "${SCRIPT_DIR}/common.sh"')


def test_runtime_config_materializer_exists() -> None:
    materializer = ROOT / "scripts" / "materialize_collisions0d_config.py"
    assert materializer.is_file()


def test_stage0_tools_and_development_config_exist() -> None:
    expected = (
        ROOT / "config" / "golovin_stage0_development.yaml",
        ROOT / "scripts" / "golovin_stage0.py",
        ROOT / "scripts" / "prepare_golovin_matrix.py",
        ROOT / "scripts" / "summarize_golovin_ensemble.py",
    )
    assert all(path.is_file() for path in expected)

    config = YAML(typ="safe").load(expected[0].read_text(encoding="utf-8"))
    assert config["experiment"]["status"] == "development_only"
    assert config["provisional_decisions"]["approved_for_production"] is False


def test_collision_seed_is_required_and_recorded() -> None:
    runner = (ROOT / "scripts" / "levante" / "run_collisions0d.sbatch").read_text(encoding="utf-8")
    assert ': "${COLLISION_SEED:?' in runner
    assert '"${runtime_config}" \\\n  "${COLLISION_SEED}"' in runner
    assert 'echo "collision_seed=${COLLISION_SEED}"' in runner

    implementation = (ROOT / "src" / "collisions0d" / "main_impl.hpp").read_text(encoding="utf-8")
    assert "argc != 3" in implementation
    assert "parse_collision_seed(argv[2])" in implementation
    assert "collision_rng_seed=" in implementation


def test_run_manifest_records_stage0_provenance() -> None:
    runner = (ROOT / "scripts" / "levante" / "run_collisions0d.sbatch").read_text(encoding="utf-8")
    for required_record in (
        "matrix_stage=",
        "matrix_case_index=",
        "initialization_family=",
        "max_superdroplets=",
        "collision_timestep_s=",
        "observation_timestep_s=",
        "zarr_tree_sha256=",
        "job_wall_seconds=",
        "module_list=",
    ):
        assert required_record in runner


def test_collision_box_analyzer_uses_pinned_cleo_tools() -> None:
    analyzer = (ROOT / "scripts" / "analyze_collisions0d.py").read_text(encoding="utf-8")
    assert "from cleopy.sdmout_src import pygbxsdat, pysetuptxt, pyzarr" in analyzer
    assert "from plotcleo import shima2009fig" in analyzer
    assert "shima2009fig.plot_validation_figure" in analyzer

    wrapper = (ROOT / "scripts" / "levante" / "analyze_collisions0d.sbatch").read_text(
        encoding="utf-8"
    )
    assert wrapper.count("sha256sum -c SHA256SUMS") == 2
