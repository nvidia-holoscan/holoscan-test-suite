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
# See README.md for detailed information.
#

import os
import holoscan_test_suite.html_render as html_render
import json
import os.path
import re
import subprocess
import yaml


def run_command(command, not_found_callback=None):
    """Runs the command (e.g. ["/usr/sbin/ethtool", "-i", "wlan0"]) in a
    subshell, assert fails if there's anything on stderr or if the returncode
    isn't 0, and yields back each line of stdout converted to a string (from
    bytes).  If the command fails with a FileNotFoundError, we'll call
    not_found_callback(command) unless it's None, in which case we'll propogate
    the FileNotFoundError."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
        )
    except FileNotFoundError:
        if not_found_callback is None:
            raise
        not_found_callback(command)
        return
    if len(result.stderr) != 0:
        print('ignoring "%s"' % (result.stderr,))
    for s in result.stdout.decode("utf-8").split("\n"):
        # don't bother with blank lines.
        if len(s) == 0:
            continue
        yield s
    return result.returncode


def fetch(*path):
    """Shorthand that makes it easy to fetch the
    contents of a file.  Typically used to fetch
    e.g. /sys/class/net/(ethernet)/(setting)"""
    with open(os.path.join(*path), "rt") as f:
        v = f.read()
    return v.strip()


class Hex(int):
    """Wraps int so that YAML and HTML will display it using hex.  NOTE that
    because int's __new__ method stores the value that is used when this is
    used in an int context, we don't need to worry about how that works here.
    We just cache it for our own purposes."""

    def __init__(self, i, width=""):
        self._i = i
        self._format = "0x%%%sX" % (width,)

    def html(self):
        return str(self)

    def __str__(self):
        return self._format % self._i


yaml.add_representer(Hex, lambda dumper, data: dumper.represent_int(str(data)))


class Na:
    """Wraps a e.g. string value so that when it's rendered as HTML,
    it uses the html_render.na style (e.g. italic)."""

    def __init__(self, context):
        self._context = context

    def html(self):
        return html_render.na(self._context)

    def __str__(self):
        return "N/A: %s" % self._context


yaml.add_representer(Na, lambda dumper, data: dumper.represent_str(str(data)))


def emmc_information(path):
    """Fish around in e.g. /sys/block/mmcblk0 to
    acquire data about the given device."""
    information = {
        "path": path,
        "name": fetch(path, "device", "name"),
        "rev": Hex(int(fetch(path, "device", "rev"), 0)),
        "date": fetch(path, "device", "date"),
        "fwrev": fetch(path, "device", "fwrev"),
        "hwrev": Hex(int(fetch(path, "device", "hwrev"), 0)),
        "serial": int(fetch(path, "device", "serial"), 0),
        "type": fetch(path, "device", "type"),
        "oemid": Hex(int(fetch(path, "device", "oemid"), 0)),
    }
    return information


def list_pci_devices(device_ids):
    # Find the devices on PCI.  pci_devices is indexed bus ID
    # (e.g. "0001:04:00.0").  device_ids is a list of "vendor:device:class"
    # per the lspci command-- leave a section blank to match all,
    # (e.g. "::0280" will find all wifi devices).
    pci_devices = {}
    for device_id in device_ids:
        # Sorry, we're not following the man page's instructions
        # to use the "machine readable" format-- those values have
        # quotes and stuff in them that make them hard to deal with.
        command = ["/usr/bin/lspci", "-n", "-d", device_id]
        for l in run_command(command):
            pci_rev = Na("No value given")
            try:
                pci_bus_address, pci_class, pci_id, pci_rev = l.split(None, 3)
            except ValueError:
                pci_bus_address, pci_class, pci_id = l.split(None, 2)
            pci_devices[pci_bus_address] = {
                "pci_bus_address": pci_bus_address,
                "pci_class": pci_class,
                "pci_id": pci_id,
                "pci_rev": pci_rev,
            }
    return pci_devices


def nvme_information(path):
    """Use the "nvme" tool to fetch information about
    this device."""
    # TO DO: Add PCI mapping information.
    command = ["/usr/sbin/nvme", "id-ctrl", "--output-format=json", path]
    information = {"tool_status": Na("nvme tool not found")}
    try:
        result = subprocess.run(
            command,
            capture_output=True,
        )
        if len(result.stderr) != 0:
            print("ignoring %s" % (result.stderr,))
        if result.returncode == 0:
            m = json.loads(result.stdout)
            information = {
                "path": path,
                "vendor_oui": m["ieee"],
                "model_number": m["mn"].strip(),
                "serial_number": m["sn"].strip(),
                "firmware_revision": m["fr"].strip(),
                "pci_vendor_id": m["vid"],
                "pci_subsystem_vendor_id": m["ssvid"],
                "total_capacity_bytes": m["tnvmcap"],
                "total_capacity_gb": round(m["tnvmcap"] / (1024 * 1024 * 1024), 1),
            }
    except FileNotFoundError:
        pass
    return information


def sata_information(path):
    """Use hdparam to find information about this device (e.g. "/dev/sda")."""
    command = ["/sbin/hdparm", "-I", path]
    result = subprocess.run(
        command,
        capture_output=True,
    )
    binary_data = result.stdout
    if len(result.stderr) != 0:
        print("Ignoring stderr=%s" % (result.stderr,))
    if result.returncode != 0:
        return {"status": Na("No device detected.")}
    data = binary_data.decode("utf-8")

    def match_group(rexp, group):
        m = re.search(rexp, data, flags=re.MULTILINE)
        return m.group(group)

    # These regular expressions collect all the data, including spaces, in the
    # line starting with e.g. "Model Number:"; but scraps spaces on either side of
    # the model number string.
    r = {
        "model_number": match_group("Model Number:[ ]+(.+?)[ ]*$", 1),
        "serial_number": match_group("Serial Number:[ ]+(.+?)[ ]*$", 1),
        "firmware_revision": match_group("Firmware Revision:[ ]+(.+?)[ ]*$", 1),
    }
    return r


def pci_network_device_information():
    pci_devices = list_pci_devices(["::0200", "::0280"])
    """Look in /sys/class/net to learn about network devices."""
    network_path = "/sys/class/net"
    interfaces = os.listdir(network_path)
    for interface in interfaces:
        # Can we map this back to a PCI slot?
        path = "/sys/class/net/%s/device" % interface
        realpath = os.path.realpath(path)
        _, slot = os.path.split(realpath)
        if slot not in pci_devices:
            continue
        information = {
            "interface": interface,
            "mac_address": fetch(network_path, interface, "address"),
        }
        information.update(pci_devices[slot])
        command = ["/usr/sbin/ethtool", "-i", interface]
        result = subprocess.run(
            command,
            capture_output=True,
        )
        if len(result.stderr) > 0:
            # lo produces this error; don't include it at all.
            assert b"Operation not supported" in result.stderr
            continue
        assert result.returncode == 0
        for binary_line in result.stdout.split(b"\n"):
            if len(binary_line) == 0:
                continue
            l = binary_line.decode("utf-8")
            name, value = l.split(": ", 1)
            # don't clutter the report with irrelevant "supports-..." stuff
            if name.startswith("supports-"):
                continue
            name = name.replace("-", "_")  # ethtool uses '-' to split up words in name
            value = value if len(value) else Na("No value given")
            information[name] = value
        yield information


def test_information(timestamp):
    # What is our git revision
    version = Na("Version not available.")
    try:
        with open("project-version", "rt") as f:
            version = f.read().strip()
    except FileNotFoundError:
        pass
    #
    return {
        "device_time": timestamp.isoformat(),
        "version": version,
    }


def to_snake(s):
    l = "_".join(s.lower().split(" "))
    return l


def v4l2_information(device):
    try:
        information = {}
        category = None
        for s in run_command(["/usr/bin/v4l2-ctl", "--device", device, "--info"]):
            name_value_pair = s.split(":", 1)
            name = name_value_pair[0].strip()
            value = ""
            if len(name_value_pair) > 1:
                value = name_value_pair[1].strip()
            if len(value) == 0:
                value = Na("No value given")
            if s.startswith("\t\t"):
                continue
            if s.startswith("\t"):
                information["%s.%s" % (category, to_snake(name))] = value
                continue
            category = to_snake(name)
    except FileNotFoundError:
        information = {"status": Na('V4L2 device "%s" not available' % device)}
    return information
