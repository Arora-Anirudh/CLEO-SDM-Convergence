# Contributing

This repository is the public research record for a staged CLEO convergence
study. Contributions should preserve scientific reproducibility and make the
effect of every change reviewable.

## Development workflow

1. Create a focused branch from `main`.
2. Keep source changes separate from generated data.
3. Record the CLEO commit, configuration, initialization seed, collision seed,
   compiler and runtime settings for every experiment.
4. Add or update tests for behavior-changing code.
5. Run `uv run ruff check .`, `uv run ruff format --check .`, and
   `uv run pytest` before requesting review.

## Scientific changes

A pull request that changes the physical or numerical experiment must state:

- the scientific question;
- the exact parameters changed;
- the quantities held fixed;
- the expected effect;
- the validation or comparison used;
- whether previous results remain comparable.

Large binary inputs, Zarr stores and Levante scratch output must not be
committed. Commit compact manifests, checksums, tables and figures instead.

## Attribution

Files adapted from CLEO or PerformanceTestingCLEO must retain their original
copyright and license notices and identify the source commit.
