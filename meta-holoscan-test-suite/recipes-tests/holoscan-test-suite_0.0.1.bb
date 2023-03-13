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
# This bitbake file supports running holoscan-test-suite via systemd
# and screen.  systemd is used to start the flask webserver (see
# https://gitlab-master.nvidia.com/clara-holoscan/holoscan-test-suite/-/blob/699f450236dfa9988c907e24fa37d892fdc6a846/README.md
# for information about how holoscan-test-suite work) under
# screen (https://linux.die.net/man/1/screen) -- this way you can 
# observe the console output from the webserver by using the command
#
#   screen -d -r holoscan-test-suite
#
# ("screen -ls" is useful to list out the screen instances currrently
# running.)  To disconnect from the screen instance, press control/A then d.
# This will detach the console; but that screen instance will continue
# to run.
#

#
# Run the appropriate configuration based on MACHINE.
#
HOLOSCAN_TEST_SUITE:clara-agx-xavier-devkit = "holoscan-test-suite-clara-agx-devkit"
HOLOSCAN_TEST_SUITE:igx-orin-devkit = "holoscan-test-suite-igx-orin-devkit"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${THISDIR}/../../LICENSE.txt;md5=480539e97a7fb5ad9df72e45418ff4ec"

RDEPENDS:${PN} = " \
    ajantv2-sdk \
    python3-ajantv2 \
    python3-flask \
    python3-holoscan-test-suite \
    python3-pytest \
    python3-pyyaml \
    python3-smbus2 \
    screen \
    util-linux-lsblk \
    ethtool \
    nvme-cli \
    opencv \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    v4l-utils \
"

inherit systemd

# By default this guy is set to start at boot.
HOLOSCAN_TEST_SUITE_SERVICE = "${HOLOSCAN_TEST_SUITE}.service"
SYSTEMD_SERVICE:${PN} = "${HOLOSCAN_TEST_SUITE_SERVICE}"

FILESEXTRAPATHS:prepend := "${THISDIR}/../..:"
SRC_URI = " \
    file://src \
    file://${HOLOSCAN_TEST_SUITE_SERVICE} \
"
S="${WORKDIR}/src"
HOLOSCAN_TEST_SUITE_DIRECTORY := "${THISDIR}"

do_install() {
    install -d ${D}/opt/nvidia
    cp -rd --no-preserve=ownership ${S} ${D}/opt/nvidia/holoscan-test-suite
    (cd ${HOLOSCAN_TEST_SUITE_DIRECTORY}; git describe --abbrev=8 --dirty --always --tags >${D}/opt/nvidia/holoscan-test-suite/project-version)
    install -d ${D}/${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/${HOLOSCAN_TEST_SUITE_SERVICE} ${D}/${systemd_unitdir}/system
}

FILES:${PN} = " \
    /opt/nvidia/holoscan-test-suite \
    ${systemd_unitdir}/system/${HOLOSCAN_TEST_SUITE_SERVICE} \
"
