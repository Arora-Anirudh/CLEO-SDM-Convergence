# Apply the one-file collision-seed extension to the build-local CLEO checkout.
#
# Required -D variables:
#   CLEO_PATCH_SOURCE_DIR
#   CLEO_PATCH_FILE
#   CLEO_EXPECTED_COMMIT
#   CLEO_GIT_EXECUTABLE
#
# The operation is deliberately idempotent so an existing build tree can be
# reconfigured. It refuses unrelated modifications in the fetched source tree.
#
# SPDX-License-Identifier: BSD-3-Clause

foreach(required_variable IN ITEMS
    CLEO_PATCH_SOURCE_DIR
    CLEO_PATCH_FILE
    CLEO_EXPECTED_COMMIT
    CLEO_GIT_EXECUTABLE
)
  if(NOT DEFINED ${required_variable} OR "${${required_variable}}" STREQUAL "")
    message(FATAL_ERROR "Missing required variable: ${required_variable}")
  endif()
endforeach()

set(
  collision_header
  "${CLEO_PATCH_SOURCE_DIR}/libs/superdrops/collisions/collisions.hpp"
)
if(NOT EXISTS "${collision_header}")
  message(FATAL_ERROR "Pinned CLEO collision header is missing: ${collision_header}")
endif()
if(NOT EXISTS "${CLEO_PATCH_FILE}")
  message(FATAL_ERROR "Collision-seed patch is missing: ${CLEO_PATCH_FILE}")
endif()

execute_process(
  COMMAND "${CLEO_GIT_EXECUTABLE}" -C "${CLEO_PATCH_SOURCE_DIR}" rev-parse HEAD
  OUTPUT_VARIABLE actual_commit
  OUTPUT_STRIP_TRAILING_WHITESPACE
  RESULT_VARIABLE commit_status
)
if(NOT commit_status EQUAL 0)
  message(FATAL_ERROR "Could not determine the fetched CLEO commit")
endif()
if(NOT actual_commit STREQUAL CLEO_EXPECTED_COMMIT)
  message(
    FATAL_ERROR
    "Refusing to patch CLEO commit ${actual_commit}; expected ${CLEO_EXPECTED_COMMIT}"
  )
endif()

execute_process(
  COMMAND "${CLEO_GIT_EXECUTABLE}" -C "${CLEO_PATCH_SOURCE_DIR}" diff --name-only
  OUTPUT_VARIABLE modified_files
  OUTPUT_STRIP_TRAILING_WHITESPACE
  RESULT_VARIABLE diff_status
)
if(NOT diff_status EQUAL 0)
  message(FATAL_ERROR "Could not inspect the fetched CLEO worktree")
endif()

file(READ "${collision_header}" collision_header_content)
string(
  FIND
  "${collision_header_content}"
  "DoCollisions(const double DELT, Probability p, EnactCollision x, const uint64_t seed)"
  seed_constructor_position
)
string(
  FIND
  "${collision_header_content}"
  "#endif  // LIBS_SUPERDROPS_COLLISIONS_COLLISIONS_HPP_"
  header_guard_end_position
)

if(seed_constructor_position GREATER_EQUAL 0)
  if(
    header_guard_end_position LESS 0
    OR seed_constructor_position GREATER header_guard_end_position
  )
    message(
      FATAL_ERROR
      "The collision-seed constructor is not inside the pinned CLEO header guard"
    )
  endif()
  if(NOT modified_files STREQUAL "libs/superdrops/collisions/collisions.hpp")
    message(
      FATAL_ERROR
      "The fetched CLEO tree contains unexpected modifications: ${modified_files}"
    )
  endif()
  message(STATUS "CLEO collision-seed patch is already present")
else()
  if(NOT modified_files STREQUAL "")
    message(
      FATAL_ERROR
      "Refusing to patch a modified fetched CLEO tree: ${modified_files}"
    )
  endif()

  execute_process(
    COMMAND
      "${CLEO_GIT_EXECUTABLE}" -C "${CLEO_PATCH_SOURCE_DIR}"
      apply --check "${CLEO_PATCH_FILE}"
    RESULT_VARIABLE patch_check_status
  )
  if(NOT patch_check_status EQUAL 0)
    message(FATAL_ERROR "Collision-seed patch does not apply cleanly to pinned CLEO")
  endif()

  execute_process(
    COMMAND
      "${CLEO_GIT_EXECUTABLE}" -C "${CLEO_PATCH_SOURCE_DIR}"
      apply "${CLEO_PATCH_FILE}"
    RESULT_VARIABLE patch_status
  )
  if(NOT patch_status EQUAL 0)
    message(FATAL_ERROR "Failed to apply the collision-seed patch")
  endif()
  message(STATUS "Applied build-local CLEO collision-seed patch")
endif()

execute_process(
  COMMAND "${CLEO_GIT_EXECUTABLE}" -C "${CLEO_PATCH_SOURCE_DIR}" diff --check
  RESULT_VARIABLE final_diff_status
)
if(NOT final_diff_status EQUAL 0)
  message(FATAL_ERROR "Patched CLEO source fails git diff --check")
endif()
