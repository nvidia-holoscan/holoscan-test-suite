#

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


# Calling check_clara_agx_devkit will return with a non-zero error code
# if you're not in a Clara AGX DevKit configuration.

function check_clara_agx_devkit {
    if ! python3 nvidia_util.py --is-model p2888
    then
        echo Not running on a Clara AGX Devkit.
        exit 1
    fi
}

