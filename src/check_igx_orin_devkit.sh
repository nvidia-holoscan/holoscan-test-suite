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

# Calling check_igx_orin_devkit.sh will return with a non-zero error code
# if you're not in an IGX Orin Devkit configuration.

function check_igx_orin_devkit {
    if ! python3 nvidia_util.py --is-model p3701
    then
        echo Not running on an IGX Orin Devkit system.
        exit 1
    fi
}

