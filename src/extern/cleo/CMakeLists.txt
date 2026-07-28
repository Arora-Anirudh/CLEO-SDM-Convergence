include(FetchContent)
find_package(Git REQUIRED)

# Pin the exact upstream revision used by every experiment. The default was the
# head of CLEO main verified on 2026-07-28. Updating it is a reviewed scientific
# and software change; never replace this with a floating branch silently.
set(
  CLEO_GIT_REPOSITORY
  "https://github.com/yoctoyotta1024/CLEO.git"
  CACHE STRING
  "Canonical upstream CLEO Git repository"
)
set(
  CLEO_GIT_TAG
  "83318c23223546d10759d202d70f4fa2f7fe4688"
  CACHE STRING
  "Exact upstream CLEO commit"
)

message(STATUS "Fetching CLEO from ${CLEO_GIT_REPOSITORY}")
message(STATUS "Pinned CLEO commit: ${CLEO_GIT_TAG}")

FetchContent_Declare(
  cleo
  GIT_REPOSITORY "${CLEO_GIT_REPOSITORY}"
  GIT_TAG "${CLEO_GIT_TAG}"
  GIT_PROGRESS TRUE
)

# Populate first so the project can apply its one explicit, version-locked
# collision-seed extension before CLEO declares its build targets. The patch
# changes only the RNG-pool constructor; the collision algorithm is unchanged.
FetchContent_GetProperties(cleo)
if(NOT cleo_POPULATED)
  FetchContent_Populate(cleo)
endif()

execute_process(
  COMMAND
    "${CMAKE_COMMAND}"
    "-DCLEO_PATCH_SOURCE_DIR=${cleo_SOURCE_DIR}"
    "-DCLEO_PATCH_FILE=${CMAKE_SOURCE_DIR}/patches/cleo/0001-add-explicit-collision-rng-seed.patch"
    "-DCLEO_EXPECTED_COMMIT=${CLEO_GIT_TAG}"
    "-DCLEO_GIT_EXECUTABLE=${GIT_EXECUTABLE}"
    -P "${CMAKE_SOURCE_DIR}/cmake/apply_cleo_collision_seed_patch.cmake"
  RESULT_VARIABLE cleo_patch_status
)
if(NOT cleo_patch_status EQUAL 0)
  message(FATAL_ERROR "Could not prepare the pinned CLEO collision-seed interface")
endif()

add_subdirectory("${cleo_SOURCE_DIR}" "${cleo_BINARY_DIR}")
