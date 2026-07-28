cmake_minimum_required(VERSION 3.18.0)

project(
  CLEO_SDM_Convergence
  VERSION 0.1.0
  DESCRIPTION "Reproducible CLEO experiments for superdroplet-method convergence"
  LANGUAGES CXX C
)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS ON)

# This project supplies its own applications and does not need to build CLEO's
# examples or rough-paper targets.
set(CLEO_NO_EXAMPLES ON CACHE BOOL "Exclude upstream CLEO examples" FORCE)
set(CLEO_NO_ROUGHPAPER ON CACHE BOOL "Exclude upstream CLEO rough-paper targets" FORCE)

add_subdirectory(src)
