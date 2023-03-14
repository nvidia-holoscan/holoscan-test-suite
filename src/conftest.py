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

# See README.md for detailed information.

#
# This file provides pytest with the "script" fixture.  Calling "script.run"
# provides the convenient mechanism for executing a shell script and preserving
# the returncode, stdout, and stderr.  flask_wrapper.py then knows how to fetch the
# results from script instances and put those in the HTML generated output.
#

import pytest
import nvidia_util
import subprocess


class Script:
    """
    The "script" fixture fetches an instance of
    this object; use the "run" method here to run
    the given script in the current directory
    and save the data written to stdout and stderr.
    In the nominal case, flask_wrapper.py will
    write that data to the HTML page passed to
    the calling browser.
    """

    def __init__(self):
        self._result = None

    def run(self, script):
        command = ["bash", script]
        r = subprocess.run(
            command,
            capture_output=True,
        )
        self._result = r
        return r.returncode


@pytest.fixture
def script():
    r = Script()
    return r


def pytest_collection_modifyitems(items):
    model = nvidia_util.model()
    igx_orin_devkit = model in nvidia_util.igx_orin_devkit
    clara_agx_devkit = model in nvidia_util.clara_agx_devkit
    for item in items:
        if "igx_orin_devkit_only" in item.keywords:
            skip = pytest.mark.skip(
                reason="%s isn't appropriate for %s" % (item.name, model)
            )
            if not igx_orin_devkit:
                item.add_marker(skip)
        if "clara_agx_devkit_only" in item.keywords:
            skip = pytest.mark.skip(
                reason="%s isn't appropriate for %s" % (item.name, model)
            )
            if not clara_agx_devkit:
                item.add_marker(skip)
