cmake_minimum_required(VERSION 3.16)
project(AstronautHealthDSPCore CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -Wall -Wextra -pedantic -fPIC -fstack-protector-strong")

include_directories(src_cpp)

# Shared library for Python ctypes binding
add_library(dsp_core SHARED
    src_cpp/dsp_core.cpp
)

# Standalone benchmark executable
add_executable(dsp_benchmark
    src_cpp/main_dsp.cpp
    src_cpp/dsp_core.cpp
)

# Output build artifacts
set_target_properties(dsp_core PROPERTIES
    OUTPUT_NAME "dsp_core"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/health_monitor"
)
