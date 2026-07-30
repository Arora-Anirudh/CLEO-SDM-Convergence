# Parallel execution of `collisions0d` on Levante

- Status: verified from the project source, CLEO build configuration, and DKRZ documentation
- Scope: the project's `src/collisions0d` executables only

## The short answer

`collisions0d` is **not an MPI-decomposed model**. It accepts exactly one MPI
process per model member. This is enforced directly in
[`main_impl.hpp`](../../src/collisions0d/main_impl.hpp): after creating the
communicator, it rejects a communicator size greater than one.

OpenMPI is nevertheless part of the build and runtime environment because
CLEO and its dependencies use MPI-aware compiler wrappers and libraries. A
successful OpenMPI build is not permission to start the same 0-D member with
four MPI ranks. `srun --ntasks=4 collisions0d_golovin ...` would fail the
explicit one-process guard, and even without the guard it would duplicate the
same one-box calculation rather than divide it across ranks.

## The two different forms of parallelism

| Level | What it means here | Current project decision |
| --- | --- | --- |
| MPI ranks *within one member* | Splitting one simulation across processes/nodes | Unsupported for `collisions0d`; always one rank |
| Kokkos/OpenMP threads *within one member* | Parallel loops inside one rank | Available in the build, but not assumed beneficial or replay-equivalent without a benchmark |
| Independent members *within one allocation* | Several distinct seeded 0-D runs at once | Supported and preferred |

Each member remains one MPI rank and one Kokkos/OpenMP thread. A four-task
Slurm allocation can therefore execute four *different* members concurrently.
This does not change any member's numerical definition, seed, initialization,
or output path. It only changes scheduler layout.

## Why concurrent members are the safe speed-up

The resolution screen requires independent collision RNG streams. Those
members have no data dependency, so they are embarrassingly parallel. The
project's restartable runner launches up to four workers, each with a
disjoint subset of the immutable matrix. Each worker calls `srun` for one
rank/one thread with `--exclusive --mem=0`; Slurm binds it to a separate
allocated logical CPU without assigning the complete allocation memory to
each member step.

The `--mem=0` is important on this specific four-worker layout. Without it,
each nested `srun` inherited the allocation's full 3.6-GiB memory request;
Slurm therefore allowed only one such step at a time even though four CPUs
were available. It does not change the model's memory limit: the four steps
share the job allocation's 3.6 GiB. It only makes that shared allocation
available to concurrent steps. This behavior and the meanings of
`--exclusive`/`--mem=0` are documented in the
[Slurm `srun` manual](https://slurm.schedmd.com/srun.html).

Levante has two simultaneous hardware threads per physical core. The
four-worker allocation and each nested member step therefore also use
`--hint=nomultithread`. This prevents Slurm from packing four requested
logical CPUs onto two physical cores, which allowed only two CPU-exclusive
steps at once in probe job `26561873`. DKRZ recommends one task per physical
core for typical applications and documents this exact hint in its
[Levante batch examples](https://docs.dkrz.de/doc/levante/running-jobs/example-batch-scripts.html).

For a fixed amount of model work, four concurrent one-thread members use
approximately the same CPU-hours as four sequential members, but reduce
elapsed time toward one quarter, subject to load imbalance and filesystem
overhead. The previous 400-member high-resolution Golovin calculation already
used this layout successfully: four workers inside one job allocation, not
400 separate scheduler jobs.

## What Levante contributes

Levante exposes 256 logical CPUs per node because simultaneous multithreading
is enabled, while the node has 128 physical cores. A Slurm `--cpus-per-task`
request is the number of logical CPUs reserved for one task; it is not a free
set of threads hidden inside one allocated CPU. Increasing this request also
increases the resource allocation.

DKRZ specifies that multiple `srun` job steps may use disjoint subsets of one
allocation simultaneously, and recommends `srun` rather than `mpirun` or
`mpiexec` to launch an application on Levante. DKRZ also notes that a typical
OpenMP/MPI hybrid calculation can use up to eight OpenMP threads effectively,
but that is application dependent. For `collisions0d`, we therefore keep the
scientific production members at one thread until a separate fixed-seed
thread-scaling and invariants test demonstrates a benefit.

Relevant operational documentation:

- [DKRZ Slurm introduction](https://docs.dkrz.de/doc/levante/running-jobs/slurm-introduction.html)
- [DKRZ example batch scripts](https://docs.dkrz.de/doc/levante/running-jobs/example-batch-scripts.html)
- [DKRZ runtime settings](https://docs.dkrz.de/doc/levante/running-jobs/runtime-settings.html)

## Fixed-10 screen layout

The proposed Golovin screen uses four simultaneous independent members per
allocation:

```text
one Slurm allocation: 4 tasks x 1 CPU/task
    worker 0 -> distinct matrix rows -> one rank/thread per row
    worker 1 -> distinct matrix rows -> one rank/thread per row
    worker 2 -> distinct matrix rows -> one rank/thread per row
    worker 3 -> distinct matrix rows -> one rank/thread per row
```

It does **not** use an MPI parallel domain decomposition. It also does not
run several threads inside a member. This is the fastest reproducible route
currently supported by the executable, and it keeps the CPU-hour budget
approximately unchanged relative to sequential execution.

## Before changing this policy

A multi-threaded `collisions0d` benchmark must be a separate experiment. It
must compare one, two, four, and eight Kokkos/OpenMP threads at fixed binary
inputs and collision seed; record CPU time, elapsed time, maximum RSS,
conservation, diagnostic outputs, and any reproducibility change; and show a
useful speed-up. It must not be folded into a convergence ensemble, because a
thread-count change may alter Kokkos execution/RNG ordering and becomes a
second numerical factor.
