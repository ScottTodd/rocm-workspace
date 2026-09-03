cmake_minimum_required(VERSION 3.25)
project(issue5024_touch_repro NONE)

set(LOCKED_FILE "" CACHE FILEPATH "Existing file held open by the probe")
if(NOT LOCKED_FILE)
  message(FATAL_ERROR "LOCKED_FILE is required")
endif()

add_custom_command(
  OUTPUT "${CMAKE_BINARY_DIR}/done.stamp"
  COMMAND "${CMAKE_COMMAND}" -E echo "before locked touch"
  COMMAND "${CMAKE_COMMAND}" -E touch "${LOCKED_FILE}"
  COMMAND "${CMAKE_COMMAND}" -E touch "${CMAKE_BINARY_DIR}/done.stamp"
  COMMENT "Touch an externally locked stamp"
  VERBATIM
)
add_custom_target(probe ALL DEPENDS "${CMAKE_BINARY_DIR}/done.stamp")
