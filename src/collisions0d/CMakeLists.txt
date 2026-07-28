project(collisions0d LANGUAGES CXX)

set(CLEO_LIBS configuration gridboxes initialise observers runcleo superdrops zarr)

add_executable(collisions0d_golovin EXCLUDE_FROM_ALL main_golovin.cpp)
add_executable(collisions0d_long EXCLUDE_FROM_ALL main_long.cpp)

foreach(target IN ITEMS collisions0d_golovin collisions0d_long)
  target_link_libraries(${target} PRIVATE cartesiandomain "${CLEO_LIBS}")
  target_link_libraries(${target} PUBLIC Kokkos::kokkos)
  target_include_directories(${target} PRIVATE "${CLEO_SOURCE_DIR}/libs")
  set_target_properties(
    ${target}
    PROPERTIES
      CXX_STANDARD 20
      CXX_STANDARD_REQUIRED ON
      CXX_EXTENSIONS ON
  )
endforeach()
