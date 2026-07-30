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
        "prepare_controlled_bundle.sbatch",
        "prepare_controlled_bundle_ladder.sbatch",
        "validate_controlled_bundle_replay.sbatch",
        "run_collisions0d.sbatch",
        "run_golovin_matrix.sbatch",
        "run_golovin_resolution_convergence.sbatch",
        "run_golovin_timestep_screen.sbatch",
        "analyze_golovin_timestep_screen.sbatch",
        "analyze_golovin_resolution_convergence.sbatch",
        "analyze_golovin_practical_convergence.sbatch",
        "plan_golovin_adaptive_extension.sbatch",
        "analyze_golovin_variance_scaling.sbatch",
        "validate_controlled_initialization.sbatch",
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
        "run_golovin_resolution_convergence.sbatch",
        "analyze_collisions0d.sbatch",
        "validate_controlled_initialization.sbatch",
        "prepare_controlled_bundle_ladder.sbatch",
        "validate_controlled_bundle_replay.sbatch",
        "run_golovin_timestep_screen.sbatch",
        "analyze_golovin_timestep_screen.sbatch",
        "analyze_golovin_resolution_convergence.sbatch",
        "analyze_golovin_practical_convergence.sbatch",
        "plan_golovin_adaptive_extension.sbatch",
        "analyze_golovin_variance_scaling.sbatch",
    ):
        content = (levante_directory / script_name).read_text(encoding="utf-8")
        expected = 'SCRIPT_DIR="${CLEO_SDM_PROJECT_ROOT}/scripts/levante"'
        assert expected in content
        assert content.index(expected) < content.index('source "${SCRIPT_DIR}/common.sh"')


def test_resolution_runner_is_one_restartable_serial_allocation() -> None:
    runner = (ROOT / "scripts" / "levante" / "run_golovin_resolution_convergence.sbatch").read_text(
        encoding="utf-8"
    )

    assert "#SBATCH --partition=shared" in runner
    assert "#SBATCH --cpus-per-task=1" in runner
    assert "#SBATCH --mem=940M" in runner
    assert "#SBATCH --time=01:00:00" in runner
    assert "#SBATCH --array" not in runner
    assert 'EXPECTED_CASE_COUNT="${EXPECTED_CASE_COUNT:-120}"' in runner
    assert 'export MATRIX_CASE_INDEX="${case_index}"' in runner
    assert 'bash "${SCRIPT_DIR}/run_golovin_matrix.sbatch"' in runner
    assert "GOLOVIN_CONTROLLED_RESOLUTION_RUN_PASS=1" in runner


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
    diagnostics = config["diagnostics"]
    initial_maximum_um = load_reference_config()["python_initconds"]["supers"]["rspan"][1] * 1.0e6
    assert diagnostics["cloud_drop_threshold_um"] < initial_maximum_um
    assert diagnostics["onset_radius_threshold_um"] > initial_maximum_um


def test_registered_golovin_definitions_are_explicit_but_not_compute_authorization() -> None:
    config_path = ROOT / "config" / "golovin_stage0_development.yaml"
    config = YAML(typ="safe").load(config_path.read_text(encoding="utf-8"))

    diagnostics = config["diagnostics"]
    assert diagnostics["radius_minimum_um"] == 1.0
    assert diagnostics["radius_maximum_um"] == 5000.0
    assert diagnostics["number_of_log_radius_bins"] == 500
    assert diagnostics["bin_robustness_counts"] == [250, 500, 1000]
    assert diagnostics["maximum_out_of_range_mass_fraction"] == 1.0e-6
    assert diagnostics["decision_times_s"] == [
        600.0,
        1200.0,
        1800.0,
        2400.0,
        3000.0,
        3600.0,
    ]

    initialization = config["controlled_initialization"]
    assert (
        initialization["status"]
        == "frozen_bundle_levante_creation_validated_compiled_reuse_pending"
    )
    assert initialization["maximum_relative_moment0_error"] == 1.0e-10
    assert initialization["maximum_relative_moment3_error"] == 1.0e-10
    assert initialization["maximum_relative_moment6_error"] == 0.01

    criteria = config["convergence_criteria"]
    assert criteria["status"] == "accepted_for_implementation"
    assert criteria["analytical_agreement"]["maximum_l1_upper_95ci"] == 0.05
    assert criteria["adjacent_level_equivalence"]["l1_absolute_difference_margin"] == 0.01
    assert config["levante"]["temporary_account"] == "bb1153"
    assert config["levante"]["production_compute_authorized"] is False

    decision = ROOT / "docs" / "decisions" / "0004-golovin-production-definitions.md"
    assert decision.is_file()

    initializer = ROOT / "scripts" / "controlled_initialization.py"
    initializer_tests = ROOT / "tests" / "test_controlled_initialization.py"
    initializer_guide = ROOT / "docs" / "implementation" / "controlled-initialization-guide.md"
    binary_validator = ROOT / "scripts" / "validate_controlled_initialization_binary.py"
    native_gate = ROOT / "scripts" / "levante" / "validate_controlled_initialization.sbatch"
    assert initializer.is_file()
    assert initializer_tests.is_file()
    assert initializer_guide.is_file()
    assert binary_validator.is_file()
    assert native_gate.is_file()
    native_gate_content = native_gate.read_text(encoding="utf-8")
    assert "--max-superdroplets 4096" in native_gate_content
    assert "collisions0d_solution.zarr" in native_gate_content
    assert "srun" not in native_gate_content

    bundle_tool = ROOT / "scripts" / "controlled_bundle.py"
    bundle_preparer = ROOT / "scripts" / "levante" / "prepare_controlled_bundle.sbatch"
    assert bundle_tool.is_file()
    assert bundle_preparer.is_file()
    bundle_preparer_content = bundle_preparer.read_text(encoding="utf-8")
    assert "CONTROLLED_BUNDLE_PREPARATION_PASS=1" in bundle_preparer_content
    assert "srun" not in bundle_preparer_content

    replay_gate = ROOT / "scripts" / "levante" / "validate_controlled_bundle_replay.sbatch"
    replay_gate_content = replay_gate.read_text(encoding="utf-8")
    assert "CONTROLLED_BUNDLE_SAME_STACK_REPLAY_PASS=1" in replay_gate_content
    assert "cmp --silent" in replay_gate_content
    assert "srun" not in replay_gate_content

    bundle_ladder = ROOT / "scripts" / "levante" / "prepare_controlled_bundle_ladder.sbatch"
    bundle_ladder_content = bundle_ladder.read_text(encoding="utf-8")
    assert "CONTROLLED_BUNDLE_LADDER_PASS=1" in bundle_ladder_content
    assert "CANONICAL_N4096_BUNDLE" in bundle_ladder_content
    assert "REUSE_CANONICAL_N4096" in bundle_ladder_content
    assert "BUNDLE_LABEL_STEM" in bundle_ladder_content
    assert "srun" not in bundle_ladder_content

    parallel_runner = (
        ROOT / "scripts" / "levante" / "run_golovin_resolution_convergence_parallel.sbatch"
    )
    parallel_runner_content = parallel_runner.read_text(encoding="utf-8")
    assert "WORKER_COUNT" in parallel_runner_content
    assert "EXPECTED_CASE_COUNT" in parallel_runner_content
    assert "GOLOVIN_CONTROLLED_PARALLEL_RESOLUTION_RUN_PASS=1" in parallel_runner_content
    assert "#SBATCH --ntasks=4" in parallel_runner_content
    assert "#SBATCH --mem=3600M" in parallel_runner_content
    assert "#SBATCH --time=02:15:00" in parallel_runner_content

    collision_runner = (ROOT / "scripts" / "levante" / "run_collisions0d.sbatch").read_text(
        encoding="utf-8"
    )
    assert "srun \\\n  --exclusive" in collision_runner

    build_runner = (ROOT / "scripts" / "levante" / "build.sbatch").read_text(encoding="utf-8")
    assert "#SBATCH --cpus-per-task=8" in build_runner
    assert "#SBATCH --mem=4G" in build_runner
    assert "#SBATCH --time=00:10:00" in build_runner

    resolution_analyzer = (
        ROOT / "scripts" / "levante" / "analyze_golovin_resolution_convergence.sbatch"
    ).read_text(encoding="utf-8")
    assert "#SBATCH --cpus-per-task=1" in resolution_analyzer
    assert "#SBATCH --mem=940M" in resolution_analyzer
    assert "#SBATCH --time=01:00:00" in resolution_analyzer

    practical_analyzer = (
        ROOT / "scripts" / "levante" / "analyze_golovin_practical_convergence.sbatch"
    ).read_text(encoding="utf-8")
    assert "#SBATCH --cpus-per-task=1" in practical_analyzer
    assert "#SBATCH --mem=940M" in practical_analyzer
    assert "#SBATCH --time=00:20:00" in practical_analyzer
    assert "srun" not in practical_analyzer

    adaptive_planner = (
        ROOT / "scripts" / "levante" / "plan_golovin_adaptive_extension.sbatch"
    ).read_text(encoding="utf-8")
    assert "#SBATCH --cpus-per-task=1" in adaptive_planner
    assert "#SBATCH --mem=940M" in adaptive_planner
    assert "#SBATCH --time=00:20:00" in adaptive_planner
    assert "srun" not in adaptive_planner
    assert "GOLOVIN_ADAPTIVE_EXTENSION_PLAN_PASS=1" in adaptive_planner

    variance_scaling = (
        ROOT / "scripts" / "levante" / "analyze_golovin_variance_scaling.sbatch"
    ).read_text(encoding="utf-8")
    assert "#SBATCH --cpus-per-task=1" in variance_scaling
    assert "#SBATCH --mem=940M" in variance_scaling
    assert "#SBATCH --time=00:20:00" in variance_scaling
    assert "srun" not in variance_scaling
    assert "GOLOVIN_VARIANCE_SCALING_ANALYSIS_PASS=1" in variance_scaling


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
        "controlled_bundle=",
        "bundle_manifest_sha256=",
        "bundle_superdroplet_sha256=",
    ):
        assert required_record in runner
    assert "prepare_collisions0d_inputs.py" in runner
    assert 'if [[ "${INITIALIZATION_FAMILY}" == "operational_stochastic" ]]' in runner
    assert runner.count("controlled_bundle.py") >= 2


def test_collision_box_analyzer_uses_pinned_cleo_tools() -> None:
    analyzer = (ROOT / "scripts" / "analyze_collisions0d.py").read_text(encoding="utf-8")
    assert "from cleopy.sdmout_src import pygbxsdat, pysetuptxt, pyzarr" in analyzer
    assert "from plotcleo import shima2009fig" in analyzer
    assert "shima2009fig.plot_validation_figure" in analyzer

    wrapper = (ROOT / "scripts" / "levante" / "analyze_collisions0d.sbatch").read_text(
        encoding="utf-8"
    )
    assert wrapper.count("sha256sum -c SHA256SUMS") == 2
    assert "fixed_bin_distributions.npz" in analyzer
    assert "fixed_bin_distributions.npz" in wrapper
    assert "ANALYSIS_LABEL" in wrapper


def test_timestep_screen_uses_ensemble_distribution_and_current_summary_name() -> None:
    analyzer = (ROOT / "scripts" / "analyze_golovin_timestep_screen.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts" / "levante" / "analyze_golovin_timestep_screen.sbatch").read_text(
        encoding="utf-8"
    )
    config = YAML(typ="safe").load(
        (ROOT / "config" / "golovin_controlled_timestep_screen.yaml").read_text(encoding="utf-8")
    )

    assert "ensemble_mean_fixed_bin_relative_l1" in analyzer
    assert "common_stream_bootstrap_l1_difference" in analyzer
    assert "fixed_bin_distributions.npz" in analyzer
    assert "all_member_time_diagnostics.csv" in wrapper
    assert "fixed_bin_distributions.npz" in wrapper
    assert (
        config["screening"]["bin_robustness_policy"]
        == "require_timestep_equivalence_at_all_registered_bin_counts"
    )


def test_actual_golovin_matrix_is_reviewed_but_not_compute_authorization() -> None:
    config_filename = ROOT / "config" / "golovin_controlled_resolution_convergence.yaml"
    experiment_root = ROOT / "experiments" / "golovin_controlled_resolution_convergence_v1"
    config = YAML(typ="safe").load(config_filename.read_text(encoding="utf-8"))

    assert config["experiment"]["status"] == "production_ready_not_submitted"
    assert config["matrix"]["max_superdroplets"] == [512, 1024, 2048, 4096, 8192, 16384]
    assert config["matrix"]["collision_timesteps_s"] == [0.1]
    assert config["matrix"]["members_per_cell"] == 20
    assert config["authorization"]["submission_authorized"] is False

    matrix_rows = (experiment_root / "cases.tsv").read_text(encoding="utf-8").splitlines()
    manifest = YAML(typ="safe").load(
        (experiment_root / "matrix_manifest.json").read_text(encoding="utf-8")
    )
    assert len(matrix_rows) == 121
    assert manifest["case_count"] == 120
    assert manifest["case_index_minimum"] == 0
    assert manifest["case_index_maximum"] == 119
    assert manifest["submission_authorized"] is False

    analyzer = ROOT / "scripts" / "analyze_golovin_resolution_convergence.py"
    auditor = ROOT / "scripts" / "audit_golovin_matrix.py"
    wrapper = ROOT / "scripts" / "levante" / "analyze_golovin_resolution_convergence.sbatch"
    assert analyzer.is_file()
    assert auditor.is_file()
    assert wrapper.is_file()
    analyzer_content = analyzer.read_text(encoding="utf-8")
    wrapper_content = wrapper.read_text(encoding="utf-8")
    assert "bootstrap_ensemble_mean_l1" in analyzer_content
    assert "independent_bootstrap_l1_difference" in analyzer_content
    assert "analysis_v1" in wrapper_content
    assert "--times 0 600 1200 1800 2400 3000 3600" in wrapper_content
    assert "audit_golovin_matrix.py" in wrapper_content


def test_fresh_high_resolution_matrix_is_complete_but_not_compute_authorization() -> None:
    config_filename = ROOT / "config" / "golovin_controlled_high_resolution_convergence.yaml"
    experiment_root = ROOT / "experiments" / "golovin_controlled_high_resolution_convergence_v1"
    config = YAML(typ="safe").load(config_filename.read_text(encoding="utf-8"))

    assert config["experiment"]["status"] == "production_ready_not_submitted"
    assert config["matrix"]["max_superdroplets"] == [
        16_384,
        32_768,
        65_536,
        131_072,
    ]
    assert config["matrix"]["members_per_cell"] == 100
    assert config["data_isolation"] == {
        "previous_raw_members_reused": 0,
        "previous_collision_seeds_reused": 0,
        "previous_bundle_labels_reused": 0,
        "fresh_member_count": 400,
        "previous_compact_result_used_for_planning_only": True,
    }
    assert config["authorization"]["submission_authorized"] is False

    matrix_rows = (experiment_root / "cases.tsv").read_text(encoding="utf-8").splitlines()
    manifest = YAML(typ="safe").load(
        (experiment_root / "matrix_manifest.json").read_text(encoding="utf-8")
    )
    assert len(matrix_rows) == 401
    assert manifest["case_count"] == 400
    assert manifest["case_index_minimum"] == 0
    assert manifest["case_index_maximum"] == 399
    assert manifest["submission_authorized"] is False
