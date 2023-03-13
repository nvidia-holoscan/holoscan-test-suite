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

import subprocess
import util
import xml.etree.ElementTree as ET


def dgpu_board_information():
    # Find all NVIDIA Video controller devices on the PCI bus.
    command = ["/usr/bin/lspci", "-n", "-d", "10de::0300"]
    for l in util.run_command(command):
        pci_bus_address, pci_class, pci_id, rev = l.split(None, 3)
        r = {
            "pci_bus_address": pci_bus_address,
            "pci_class": pci_class,
            "pci_id": pci_id,
            "rev": rev,
        }
        # Get nvidia-smi's output in XML format
        command = ["nvidia-smi", "-q", "--xml-format", "-i", pci_bus_address]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
            )
            xml_data = result.stdout
            root = ET.fromstring(xml_data)
            gpus = root.findall("./gpu")
            assert len(gpus) == 1
            gpu = gpus[0]
            r.update(
                {
                    "serial": gpu.find("serial").text,
                    "uuid": gpu.find("uuid").text,
                    "vbios_version": gpu.find("vbios_version").text,
                    "board_id": util.Hex(int(gpu.find("board_id").text, 0)),
                    "gpu_part_number": gpu.find("gpu_part_number").text,
                    "img_version": gpu.find("inforom_version").find("img_version").text,
                }
            )
        except FileNotFoundError:
            r["driver_status"] = util.Na("DGPU driver not available")
        yield r


def dgpu_driver_information():
    # Get nvidia-smi's output in XML format
    command = ["nvidia-smi", "-q", "--xml-format"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
        )
        xml_data = result.stdout
        root = ET.fromstring(xml_data)
        information = {
            "driver_version": root.find("driver_version").text,
            "cuda_version": root.find("cuda_version").text,
            "attached_dgpus": int(root.find("./attached_gpus").text),
        }
    except FileNotFoundError:
        information = {"status": util.Na("DGPU driver not available")}
    return information
