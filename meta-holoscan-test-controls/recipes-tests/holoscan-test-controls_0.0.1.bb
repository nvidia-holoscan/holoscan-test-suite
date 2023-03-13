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

#
# This bitbake file supports running holoscan-test-controls via systemd
# and screen.  systemd is used to start the flask webserver under
# screen (https://linux.die.net/man/1/screen) -- this way you can 
# observe the console output from the webserver by using the command
#
#   screen -d -r holoscan-test-controls
#
# ("screen -ls" is useful to list out the screen instances currrently
# running.)  To disconnect from the screen instance, press control/A then d.
# This will detach the console; but that screen instance will continue
# to run.
#

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${THISDIR}/../../LICENSE.txt;md5=480539e97a7fb5ad9df72e45418ff4ec"

RDEPENDS:${PN} = " \
    holoscan-test-suite \
    iperf3 \
    memtester \
    nvidia-gpu-stress-test \
    python3-flask-socketio \
    util-linux-taskset \
"

inherit systemd

# By default this guy is set to start at boot.
SYSTEMD_SERVICE:${PN} = "holoscan-test-controls.service"

FILESEXTRAPATHS:prepend := "${THISDIR}/../..:"
SRC_URI = " \
    file://src \
    file://holoscan-test-controls.service \
"
S="${WORKDIR}/src"
HOLOSCAN_TEST_CONTROLS_DIRECTORY := "${THISDIR}"

do_install() {
    install -d ${D}/opt/nvidia
    cp -rd --no-preserve=ownership ${S} ${D}/opt/nvidia/holoscan-test-controls
    (cd ${HOLOSCAN_TEST_CONTROLS_DIRECTORY}; git describe --abbrev=8 --dirty --always --tags >${D}/opt/nvidia/holoscan-test-controls/project-version)
    install -d ${D}/${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/holoscan-test-controls.service ${D}/${systemd_unitdir}/system
}

FILES:${PN} = " \
    /opt/nvidia/holoscan-test-controls \
    ${systemd_unitdir}/system/holoscan-test-controls.service \
"
