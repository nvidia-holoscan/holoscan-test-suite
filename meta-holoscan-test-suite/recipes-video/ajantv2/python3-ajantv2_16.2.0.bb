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


DESCRIPTION = "AJA NTV2 Library for python"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${THISDIR}/../../../LICENSE.txt;md5=480539e97a7fb5ad9df72e45418ff4ec"

SRC_URI = " \
    file://CMakeLists.txt \
    file://ajantv2.i \
"
S = "${WORKDIR}"

inherit cmake python3-dir

DEPENDS += " \
    python3 \
    swig-native \
    ajantv2-sdk \
"

FILES:${PN} = " \
    ${PYTHON_SITEPACKAGES_DIR}/_ajantv2.so \
    ${PYTHON_SITEPACKAGES_DIR}/ajantv2.py \
"

do_install() {
    install -d ${D}${PYTHON_SITEPACKAGES_DIR}
    install -m 0755 ${WORKDIR}/build/_ajantv2.so ${D}${PYTHON_SITEPACKAGES_DIR}
    install -m 0755 ${WORKDIR}/build/ajantv2.py ${D}${PYTHON_SITEPACKAGES_DIR}
}
