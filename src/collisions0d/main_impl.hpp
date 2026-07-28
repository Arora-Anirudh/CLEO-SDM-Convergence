/*
 * Derived from CLEO examples/boxmodelcollisions/src/main_impl.hpp at
 * commit 83318c23223546d10759d202d70f4fa2f7fe4688.
 *
 * Copyright (c) 2024 MPI-M, Clara Bayley
 * Modifications copyright (c) 2026 Anirudh Arora
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#ifndef CLEO_SDM_CONVERGENCE_COLLISIONS0D_MAIN_IMPL_HPP_
#define CLEO_SDM_CONVERGENCE_COLLISIONS0D_MAIN_IMPL_HPP_

#include <Kokkos_Core.hpp>

#include <charconv>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <system_error>

#include "cartesiandomain/cartesianmaps.hpp"
#include "cartesiandomain/createcartesianmaps.hpp"
#include "cartesiandomain/movement/cartesian_movement.hpp"
#include "configuration/communicator.hpp"
#include "configuration/config.hpp"
#include "coupldyn_null/nulldynamics.hpp"
#include "coupldyn_null/nulldyncomms.hpp"
#include "gridboxes/boundary_conditions.hpp"
#include "gridboxes/gridboxmaps.hpp"
#include "initialise/init_all_supers_from_binary.hpp"
#include "initialise/initgbxsnull.hpp"
#include "initialise/initialconditions.hpp"
#include "initialise/timesteps.hpp"
#include "observers/collect_data_for_simple_dataset.hpp"
#include "observers/observers.hpp"
#include "observers/streamout_observer.hpp"
#include "observers/superdrops_observer.hpp"
#include "observers/time_observer.hpp"
#include "runcleo/coupleddynamics.hpp"
#include "runcleo/couplingcomms.hpp"
#include "runcleo/runcleo.hpp"
#include "runcleo/sdmmethods.hpp"
#include "superdrops/microphysicalprocess.hpp"
#include "superdrops/motion.hpp"
#include "zarr/fsstore.hpp"
#include "zarr/simple_dataset.hpp"

template <GridboxMaps GbxMaps>
inline InitialConditions auto create_initial_conditions(const Config &config,
                                                        const GbxMaps &gbxmaps) {
  const auto initsupers = InitAllSupersFromBinary(config.get_initsupersfrombinary());
  const auto initgbxs = InitGbxsNull(gbxmaps.get_local_ngridboxes_hostcopy());
  return InitConds(initsupers, initgbxs);
}

inline GridboxMaps auto create_gridbox_maps(const Config &config) {
  return create_cartesian_maps(config.get_ngbxs(), config.get_nspacedims(),
                               config.get_grid_filename());
}

inline auto create_null_movement(const CartesianMaps &gbxmaps) {
  const Motion<CartesianMaps> auto motion = NullMotion{};
  const BoundaryConditions<CartesianMaps> auto boundary_conditions =
      NullBoundaryConditions{};
  return cartesian_movement(gbxmaps, motion, boundary_conditions);
}

template <typename Dataset, typename Store>
inline Observer auto create_superdroplet_observer(const unsigned int interval,
                                                  Dataset &dataset, Store &store,
                                                  const int maxchunk) {
  CollectDataForDataset<Dataset> auto sdid = CollectSdId(dataset, maxchunk);
  CollectDataForDataset<Dataset> auto xi = CollectXi(dataset, maxchunk);
  CollectDataForDataset<Dataset> auto radius = CollectRadius(dataset, maxchunk);
  CollectDataForDataset<Dataset> auto msol = CollectMsol(dataset, maxchunk);

  const auto collect_sddata = msol >> radius >> xi >> sdid;
  return SuperdropsObserver(interval, dataset, store, maxchunk, collect_sddata);
}

template <typename Dataset, typename Store>
inline Observer auto create_observer(const Config &config, const Timesteps &tsteps,
                                     Dataset &dataset, Store &store) {
  const auto obsstep = tsteps.get_obsstep();
  const auto maxchunk = config.get_maxchunk();

  const Observer auto stream = StreamOutObserver(obsstep, &step2realtime);
  const Observer auto time =
      TimeObserver(obsstep, dataset, store, maxchunk, &step2dimlesstime);
  const Observer auto supers =
      create_superdroplet_observer(obsstep, dataset, store, maxchunk);

  return supers >> time >> stream;
}

template <typename Dataset, typename Store, typename CreateMicrophysics>
inline auto create_sdm(const Config &config, const Timesteps &tsteps,
                       Dataset &dataset, Store &store,
                       const CreateMicrophysics create_microphysics,
                       const std::uint64_t collision_seed) {
  const auto couplstep = static_cast<unsigned int>(tsteps.get_couplstep());
  const GridboxMaps auto gbxmaps = create_gridbox_maps(config);
  const MicrophysicalProcess auto microphysics =
      create_microphysics(config, tsteps, collision_seed);
  const MoveSupersInDomain movesupers = create_null_movement(gbxmaps);
  const Observer auto observer = create_observer(config, tsteps, dataset, store);

  return SDMMethods(couplstep, gbxmaps, microphysics, movesupers, observer);
}

inline std::uint64_t parse_collision_seed(const std::string_view text) {
  if (text.empty() || text.front() == '-') {
    throw std::invalid_argument(
        "collision seed must be an integer in [0, 2^64 - 1]");
  }

  std::uint64_t seed{};
  const auto result =
      std::from_chars(text.data(), text.data() + text.size(), seed);
  if (result.ec != std::errc{} ||
      result.ptr != text.data() + text.size()) {
    throw std::invalid_argument(
        "collision seed must be an integer in [0, 2^64 - 1]");
  }
  return seed;
}

template <typename CreateMicrophysics>
inline int run_collisions0d(int argc, char *argv[],
                            const CreateMicrophysics create_microphysics) {
  if (argc != 3) {
    throw std::invalid_argument(
        "usage: collisions0d_<kernel> CONFIG_FILE COLLISION_SEED");
  }

  Kokkos::Timer timer;
  const std::filesystem::path config_filename(argv[1]);
  const std::uint64_t collision_seed = parse_collision_seed(argv[2]);
  const Config config(config_filename);

  init_communicator communicator(argc, argv, config);
  if (init_communicator::get_comm_size() > 1) {
    throw std::invalid_argument(
        "collisions0d currently supports exactly one MPI process");
  }

  Kokkos::initialize(config.get_kokkos_initialization_settings());
  {
    Kokkos::print_configuration(std::cout);
    std::cout << "collision_rng_seed=" << collision_seed << "\n";
    const Timesteps tsteps(config.get_timesteps());

    auto store = FSStore(config.get_zarrbasedir());
    auto dataset = SimpleDataset(store);

    const SDMMethods sdm =
        create_sdm(config, tsteps, dataset, store, create_microphysics,
                   collision_seed);
    const CoupledDynamics auto dynamics =
        NullDynamics(tsteps.get_couplstep());
    const CouplingComms<CartesianMaps, NullDynamics> auto communications =
        NullDynComms{};
    const InitialConditions auto initial_conditions =
        create_initial_conditions(config, sdm.gbxmaps);

    const RunCLEO run_cleo(sdm, dynamics, communications);
    run_cleo(initial_conditions, tsteps.get_t_end());
  }
  Kokkos::finalize();

  std::cout << "-----\nCLEO collisions0d duration: " << timer.seconds()
            << " s\n-----\n";
  return 0;
}

#endif  // CLEO_SDM_CONVERGENCE_COLLISIONS0D_MAIN_IMPL_HPP_
