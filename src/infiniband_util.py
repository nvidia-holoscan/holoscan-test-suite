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

import os.path
import subprocess
import util


def infiniband_information():
    pci_devices = util.list_pci_devices(["15b3::"])
    # What devices are there?
    command = ["/usr/sbin/ibstat", "--list_of_cas"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
        )
        # Parse the output into an information table.
        s = result.stdout
        devices = []
        for device in s.decode("utf-8").split("\n"):
            if len(device):
                devices.append(device)
    except FileNotFoundError:
        return
    for device in devices:
        command = ["/usr/sbin/ibstat", "--short", device]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
            )
            # Parse the output into an information table.
            s = result.stdout
            l = s.decode("utf-8").split("\n")
            information = {}
            category = None
            for i in l:
                if len(i) == 0:
                    continue
                # We already know what device this is
                if i == ("CA '%s'" % device):
                    continue
                name_value_pair = i.split(":", 1)
                name = name_value_pair[0].strip()
                value = ""
                if len(name_value_pair) > 1:
                    value = name_value_pair[1].strip()
                if len(value) == 0:
                    value = util.Na("No value given")
                information[util.to_snake(name)] = value
            # Can we map this back to a PCI slot?
            path = "/sys/class/infiniband/%s/device" % device
            realpath = os.path.realpath(path)
            _, slot = os.path.split(realpath)
            if slot in pci_devices:
                information.update(pci_devices[slot])
            yield information
        except FileNotFoundError:
            information = {"status": util.Na("V4L2 driver not available")}
            yield information
