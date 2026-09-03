cmake_minimum_required(VERSION 3.25)
project(issue5024_cmake_repro NONE)

set(PYTHON_EXECUTABLE "" CACHE FILEPATH "Python executable")
set(FILESET_TOOL "" CACHE FILEPATH "TheRock fileset_tool.py")
set(TEATIME_TOOL "" CACHE FILEPATH "TheRock teatime.py")
option(WRAP_WITH_TEATIME "Wrap fileset commands with teatime" OFF)
set(STRESS_WORKERS 12 CACHE STRING "Number of concurrent flatten commands")
set(STRESS_FILES 64 CACHE STRING "Number of overlapping files per artifact")

if(NOT PYTHON_EXECUTABLE OR NOT FILESET_TOOL)
  message(FATAL_ERROR "PYTHON_EXECUTABLE and FILESET_TOOL are required")
endif()

set(fixture_dir "${CMAKE_BINARY_DIR}/fixture")
execute_process(
  COMMAND "${PYTHON_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/prepare_fixture.py"
    "${fixture_dir}" "${STRESS_WORKERS}" "${STRESS_FILES}"
  COMMAND_ERROR_IS_FATAL ANY
)

set(stamps)
math(EXPR last_worker "${STRESS_WORKERS} - 1")
foreach(worker RANGE 0 ${last_worker})
  set(stamp "${CMAKE_BINARY_DIR}/stamp-${worker}")
  set(fileset_command
    "${PYTHON_EXECUTABLE}" "${FILESET_TOOL}" artifact-flatten
    -o "${CMAKE_BINARY_DIR}/dist-rocm"
    "${fixture_dir}/artifact-${worker}"
  )
  if(WRAP_WITH_TEATIME)
    if(NOT TEATIME_TOOL)
      message(FATAL_ERROR "TEATIME_TOOL is required with WRAP_WITH_TEATIME")
    endif()
    set(fileset_command
      "${PYTHON_EXECUTABLE}" "${TEATIME_TOOL}"
      --label "flatten-${worker}" --no-interactive
      "${CMAKE_BINARY_DIR}/flatten-${worker}.log"
      -- ${fileset_command}
    )
  endif()
  add_custom_command(
    OUTPUT "${stamp}"
    COMMAND ${fileset_command}
    COMMAND "${CMAKE_COMMAND}" -E touch "${stamp}"
    COMMENT "Flatten synthetic artifact ${worker}"
    VERBATIM
  )
  list(APPEND stamps "${stamp}")
endforeach()

add_custom_target(stress ALL DEPENDS ${stamps})
