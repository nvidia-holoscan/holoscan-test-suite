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

import ajantv2
import util


def aja_board_information():
    # Find the devices on PCI.  pci_devices is indexed by pci-id
    # (e.g. "f1d0:eb1f") and is a list of boards found with that
    # id.
    command = ["/usr/bin/lspci", "-n", "-d", "f1d0::0400"]
    pci_devices = {}
    for l in util.run_command(command):
        pci_rev = util.Na("No value given")
        try:
            pci_bus_address, pci_class, pci_id, pci_rev = l.split(None, 3)
        except ValueError:
            pci_bus_address, pci_class, pci_id = l.split(None, 2)
        r = {
            "pci_bus_address": pci_bus_address,
            "pci_class": pci_class,
            "pci_id": pci_id,
            "pci_rev": pci_rev,
        }
        pci_devices.setdefault(pci_id, []).append(r)
    #
    device_scanner = ajantv2.CNTV2DeviceScanner()
    device_count = device_scanner.GetNumDevices()
    #
    for i in range(device_count):
        card = ajantv2.CNTV2Card(i)
        serial_number_status, serial_number_string = card.GetSerialNumberString()
        pci_device_id_status, pci_device_id = card.GetPCIDeviceID()
        (
            firmware_status,
            firmware_bytes,
            firmware_date,
            firmware_time,
        ) = card.GetInstalledBitfileInfo()
        firmware_info = util.Na("No bitfile info provided")
        if firmware_status:
            firmware_info = "firmware_bytes=%s firmware_date=%s firmware_time=%s" % (
                firmware_bytes,
                firmware_date,
                firmware_time,
            )
        (
            failsafe_firmware_status,
            failsafe_firmware_loaded,
        ) = card.IsFailSafeBitfileLoaded()
        pci_device_id_information = util.Na("Not provided")
        if pci_device_id_status:
            pci_device_id_information = util.Hex(pci_device_id)
        failsafe_firmware_loaded_information = util.Na("Not provided")
        if failsafe_firmware_status:
            failsafe_firmware_loaded_information = failsafe_firmware_loaded
        serial_number_information = util.Na("Not provided")
        if serial_number_status:
            serial_number_information = serial_number_string
        board_information = {
            "device_id": util.Hex(card.GetDeviceID()),
            "model": card.GetModelName(),
            "device_version": card.GetDeviceVersion(),
            "driver_version": card.GetDriverVersionString(),
            "serial_number": serial_number_information,
            "pci_device_id": pci_device_id_information,
            "breakout_hardware": card.GetBreakoutHardware(),
            "firmware_info": firmware_info,
            "failsafe_firmware": failsafe_firmware_loaded_information,
            "fpga_version": card.GetPCIFPGAVersionString(),
        }
        # The information from GetPCIDeviceID isn't enough to point us to
        # a specific instance-- so if the length of devices in pci_devices[...]
        # is 1, then we'll use that.  Otherwise we can't tell.
        if pci_device_id_status:
            pci_device = pci_devices.get("f1d0:%04x" % pci_device_id, {})
            if len(pci_device) == 1:
                board_information.update(pci_device[0])
        yield board_information


def aja_driver_information():
    r = {
        "sdk_version": "%s.%s.%s (0x%08X) build %s; %s"
        % (
            ajantv2.AJA_NTV2_SDK_VERSION_MAJOR,
            ajantv2.AJA_NTV2_SDK_VERSION_MINOR,
            ajantv2.AJA_NTV2_SDK_VERSION_POINT,
            ajantv2.AJA_NTV2_SDK_VERSION,
            ajantv2.AJA_NTV2_SDK_BUILD_NUMBER,
            ajantv2.AJA_NTV2_SDK_BUILD_DATETIME,
        ),
    }
    device_scanner = ajantv2.CNTV2DeviceScanner()
    device_count = device_scanner.GetNumDevices()
    r["device_count"] = device_count
    return r
