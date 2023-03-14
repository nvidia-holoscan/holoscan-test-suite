#!/usr/bin/env python

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


from setuptools import setup

setup(
    name="holoscan_test_suite",
    version="0.1",
    author="Patrick O'Grady",
    author_email="pogrady@nvidia.com",
    description="Tools used by Holoscan Test Suite.",
    packages=["holoscan_test_suite"],
    include_package_data = True,
    package_data = {"": ["test_image.png"]},
    entry_points=dict(
        console_scripts=["show_test_pattern=holoscan_test_suite.show_test_pattern:main"]
    ),
    install_requires=[
        "opencv-python",
        "pyyaml",
    ],
    zip_safe=False,
)
