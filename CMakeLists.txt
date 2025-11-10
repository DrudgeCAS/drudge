cmake_minimum_required(VERSION 3.15)
project(${SKBUILD_PROJECT_NAME} LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Python
find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)

# Include directories
set(LIBCANON_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/deps/libcanon/include")
set(DRUDGE_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/drudge")

# Platform-specific compiler flags
if(MSVC)
  # MSVC compiler flags
  add_compile_options(/EHsc /bigobj /wd4996 /wd4267 /Zc:twoPhase-)
endif()

# canonpy extension
Python_add_library(canonpy MODULE
  drudge/canonpy.cpp
  WITH_SOABI
)
target_include_directories(canonpy PRIVATE
  ${LIBCANON_INCLUDE_DIR}
  ${DRUDGE_INCLUDE_DIR}
)
install(TARGETS canonpy LIBRARY DESTINATION drudge)

# wickcore extension
Python_add_library(wickcore MODULE
  drudge/wickcore.cpp
  WITH_SOABI
)
target_include_directories(wickcore PRIVATE
  ${LIBCANON_INCLUDE_DIR}
  ${DRUDGE_INCLUDE_DIR}
)
install(TARGETS wickcore LIBRARY DESTINATION drudge)
