include(FetchContent)

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
FetchContent_MakeAvailable(cleo)
