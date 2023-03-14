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

import argparse
import ctypes
import re
import smbus2
import sys
import util
import yaml

# Tests use this with pytest.mark.skip.
igx_orin_devkit = ["p3701"]
clara_agx_devkit = ["p2888"]


RESERVED = "reserved_"


# Adapts the EEPROM layout described here:
# https://docs.nvidia.com/jetson/archives/r34.1/DeveloperGuide/text/HR/JetsonEepromLayout.html
# to the name/[array_]ctype list that ctypes.Structure wants.
def jetson_eeprom_to_ctypes(field_list):
    """field_list is a list of (first_byte_offset, last_byte_offset,
    field_name, ctype) the number of bytes should always be an even multiple of
    the ctype size; for a multiple of greater than one then we'll make an array
    out of that here.
    """
    # order by first_byte_offset
    l = sorted(field_list)
    address = 0
    r = []
    for first_byte_offset, last_byte_offset, field_name, ct in l:
        # No overlapping data is allowed.
        assert first_byte_offset >= address
        # Do we need to fill with "reserved" bytes?
        if address < first_byte_offset:
            n = first_byte_offset - address
            r.append(("%s%s" % (RESERVED, len(r)), ctypes.c_uint8 * n))
            address += n
        # How many of these data are here?
        n = last_byte_offset - address + 1
        count = n // ctypes.sizeof(ct)
        # has to be an even number of elements
        assert (count * ctypes.sizeof(ct)) == n
        if count == 1:
            r.append((field_name, ct))
        else:
            r.append((field_name, ct * count))
        address += n
    return r


# https://docs.nvidia.com/jetson/archives/r34.1/DeveloperGuide/text/HR/JetsonEepromLayout.html
# (also https://docs.nvidia.com/jetson/archives/l4t-archived/l4t-3231/index.html#page/Tegra%20Linux%20Driver%20Package%20Development%20Guide/jetson_eeprom_layout.html)
class JetsonEepromCtypesAdapter(ctypes.Structure):
    _pack_ = 1
    _fields_ = jetson_eeprom_to_ctypes(
        [
            (0, 0, "major_version", ctypes.c_uint8),
            (1, 1, "minor_version", ctypes.c_uint8),
            (2, 3, "id_data_bytes", ctypes.c_uint16),
            (4, 5, "board_number", ctypes.c_uint16),
            (6, 7, "sku", ctypes.c_uint16),
            (8, 8, "fab", ctypes.c_uint8),
            (9, 9, "rev", ctypes.c_uint8),
            (10, 10, "minor_rev", ctypes.c_uint8),
            (11, 11, "memory_type", ctypes.c_uint8),
            (12, 12, "power_configuration", ctypes.c_uint8),
            (13, 13, "miscellaneous_configuration", ctypes.c_uint8),
            (16, 16, "display_configuration", ctypes.c_uint8),
            (17, 17, "rework_level", ctypes.c_uint8),
            (19, 19, "gigabit_mac_ids", ctypes.c_uint8),
            (20, 49, "board_id", ctypes.c_char),
            (50, 55, "wifi_mac_id", ctypes.c_uint8),
            (56, 61, "bluetooth_mac_id", ctypes.c_uint8),
            (62, 67, "secondary_wifi_mac_id", ctypes.c_uint8),
            (68, 73, "gigabit_mac_id", ctypes.c_uint8),
            (74, 88, "serial_number", ctypes.c_char),
            (150, 153, "customer_block_signature", ctypes.c_char),
            (154, 155, "customer_block_length", ctypes.c_uint16),
            (156, 157, "customer_block_type", ctypes.c_char),
            (158, 159, "customer_block_version", ctypes.c_uint16),
            (160, 165, "customer_block_wifi_mac_id", ctypes.c_uint8),
            (166, 171, "customer_block_bluetooth_mac_id", ctypes.c_uint8),
            (172, 177, "customer_block_gigabit_mac_id", ctypes.c_uint8),
            (178, 178, "customer_block_gigabit_mac_ids", ctypes.c_uint8),
            (200, 220, "orin_system_part_number", ctypes.c_char),
            (221, 235, "orin_serial_number", ctypes.c_char),
            (255, 255, "crc8", ctypes.c_uint8),
        ]
    )


def compute_crc8(b, crc=0):
    """See https://docs.nvidia.com/jetson/archives/r34.1/DeveloperGuide/text/HR/JetsonEepromLayout.html"""
    for c in b:
        assert c >= 0
        assert c < 256
        for bit in range(8):
            odd = ((c ^ crc) & 1) == 1
            crc >>= 1
            c >>= 1
            if odd:
                crc ^= 0x8C
    return crc


class EepromStr(str):
    """Some ASCII printable data is stored in eeprom with fill characters (\x00
    or \xFF); use this adapter to get a printable string without that filler.
    By subclassing str (and using __new__ to set immutable fields) we hide the
    fact that we're adapting the value here from something else.  We'd use a str
    directly if we didn't want to have special yaml or html handling.
    """

    def __new__(cls, b, strip=b"\x00"):
        s = b.rstrip(strip).decode("utf-8")
        obj = str.__new__(cls, s)
        obj._s = s
        obj._present = len(obj._s) > 0
        return obj

    def yaml(self, dumper):
        if self._present:
            return dumper.represent_str(self._s)
        return dumper.represent_none(None)

    def html(self):
        if self._present:
            return self._s
        return util.Na("Not specified").html()


yaml.add_representer(EepromStr, lambda dumper, data: data.yaml(dumper))


class EepromMac:
    def __init__(self, b):
        self._s = ":".join(["%02X" % c for c in b])

    def __str__(self):
        return self._s

    def yaml(self, dumper):
        return dumper.represent_str(self._s)

    def html(self):
        return self._s


yaml.add_representer(EepromMac, lambda dumper, data: data.yaml(dumper))


def _jetson_eeprom_information(device=0, address=0x50):
    """NOTE this returns the JetsonEeprom instance AND the computed CRC of
    EEPROM data.  You really want to use jetson_eeprom_information() instead.
    """
    with smbus2.SMBus(device) as bus:
        bs = 16
        r = bytearray()
        for a in range(0, 256, bs):
            assert (a >> 8) == 0
            wr = smbus2.i2c_msg.write(address, [a & 0xFF])
            rd = smbus2.i2c_msg.read(address, bs)
            bus.i2c_rdwr(wr, rd)
            r.extend(list(rd))
    eeprom = JetsonEepromCtypesAdapter.from_buffer(r)
    computed_crc = compute_crc8(r[:-1])
    jetson_eeprom = {
        "version": "%d.%d" % (eeprom.major_version, eeprom.minor_version),
        "board_number": eeprom.board_number,
        "sku": eeprom.sku,
        "fab": eeprom.fab,
        "rev": "%d.%d" % (eeprom.rev, eeprom.minor_rev),
        "memory_type": eeprom.memory_type,
        "power_configuration": eeprom.power_configuration,
        "miscellaneous_configuration": eeprom.miscellaneous_configuration,
        "display_configuration": eeprom.display_configuration,
        "rework_level": eeprom.rework_level,
        "gigabit_mac_ids": eeprom.gigabit_mac_ids,
        "board_id": EepromStr(eeprom.board_id, strip=b"\x00\xFF"),
        "wifi_mac_id": EepromMac(eeprom.wifi_mac_id),
        "bluetooth_mac_id": EepromMac(eeprom.bluetooth_mac_id),
        "secondary_wifi_mac_id": EepromMac(eeprom.secondary_wifi_mac_id),
        "gigabit_mac_id": EepromMac(eeprom.gigabit_mac_id),
        "serial_number": EepromStr(eeprom.serial_number),
        "customer_block_signature": EepromStr(eeprom.customer_block_signature),
        "customer_block_length": eeprom.customer_block_length,
        "customer_block_type": EepromStr(eeprom.customer_block_type),
        "customer_block_version": util.Hex(eeprom.customer_block_version),
        "customer_block_wifi_mac_id": EepromMac(eeprom.customer_block_wifi_mac_id),
        "customer_block_bluetooth_mac_id": EepromMac(
            eeprom.customer_block_bluetooth_mac_id
        ),
        "customer_block_gigabit_mac_id": EepromMac(
            eeprom.customer_block_gigabit_mac_id
        ),
        "customer_block_gigabit_mac_ids": eeprom.customer_block_gigabit_mac_ids,
        "orin_system_part_number": EepromStr(eeprom.orin_system_part_number),
        "orin_serial_number": EepromStr(eeprom.orin_serial_number),
        "crc8": util.Hex(eeprom.crc8),
    }
    return jetson_eeprom, computed_crc


def jetson_eeprom_information(device=0, address=0x50):
    """Returns a dict with the data found in the on-board IDROM."""
    eeprom, computed_crc = _jetson_eeprom_information(device, address)
    eeprom_crc = eeprom["crc8"]
    # If the EEPROM CRC doesn't match, let the user know.
    eeprom["computed_crc"] = util.Hex(computed_crc)
    eeprom["crc_check"] = "CRC VALUES DO NOT MATCH"
    if eeprom_crc == computed_crc:
        eeprom["crc_check"] = "Check ok"
    return eeprom


def model():
    eeprom = jetson_eeprom_information()
    board_id = eeprom["board_id"]
    g = re.match("699-(.)(....)-(....)-(...) (...)", board_id)
    assert g is not None
    board_class, module_id, sku, version, revision = (
        g.group(1),
        g.group(2),
        g.group(3),
        g.group(4),
        g.group(5),
    )
    return "p" + module_id


def main():
    #
    parser = argparse.ArgumentParser(
        description="Tool to query NVIDIA configuration.",
    )
    parser.add_argument(
        "--is-model",
        help="exits with a 0 if the given model is present.",
    )
    parser.add_argument(
        "--model",
        action="store_true",
        help="Display the current board model.",
    )
    args = parser.parse_args()
    #
    if args.is_model:
        if model() == args.is_model:
            return 0
        else:
            return 1
    #
    if args.model:
        print("model=%s" % (model(),))
        return 0
    # By default, just dump the contents.
    eeprom = _jetson_eeprom_information()
    return 0


if __name__ == "__main__":
    sys.exit(main())
