# SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Use SWIG to translate ajantv2.i into a python module that wraps calls to the
# AJA NTV2 library.
#

cmake_minimum_required(VERSION 3.22)

project(python3_ajantv2 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 11)

list(APPEND CMAKE_PREFIX_PATH ${ajantv2_DIR})

find_package(ajantv2 REQUIRED)
get_target_property(ajantv2_include_directories AJA::ajantv2 INTERFACE_INCLUDE_DIRECTORIES)
include_directories(${ajantv2_include_directories})

find_package(SWIG REQUIRED)
include(${SWIG_USE_FILE})

find_package(PythonLibs)
include_directories(${PYTHON_INCLUDE_PATH})

include_directories(${CMAKE_CURRENT_SOURCE_DIR})

list(APPEND CMAKE_SWIG_FLAGS "-py3" "-threads" "-O")

set_source_files_properties(ajantv2.i PROPERTIES CPLUSPLUS ON)
swig_add_module(ajantv2 python ajantv2.i)
swig_link_libraries(ajantv2 ${PYTHON_LIBRARIES} AJA::ajantv2)
