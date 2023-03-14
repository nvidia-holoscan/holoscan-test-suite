#!/bin/sh

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

# PRE-REQUISITES:
#       Script must be run as root.
#       Runs on an IGX Orin Devkit or Clara AGX Devkit configuration.
#       Relies on an AJA HDMI video adapter.
#
# USAGE:
#       bringup_aja_igx_orin_devkit.sh
#
# EXIT STATUS:
#       This scripts exits with status 0 if the test succeeds;
#       any non-zero value indicates a test failure.
#

set -o xtrace
# source kernel based config file
KERNEL_VERSION=$(uname -r | cut -d '.' -f-2)
source "${SCRIPT_DIRECTORY}"/module_common_"${KERNEL_VERSION}".conf

# fail the script on errors
set -e
set -o xtrace

function check_aja_rdma {
    # Transfer 50 frames from AJA to DGPU.
    testrdma -t50
}

function show_usage {
cat << EOF
Usage: ${SCRIPT_NAME}
Runs testrdma to ensure frames can be transferred from AJA to DGPU.
EOF
	exit 1
}

# script name
SCRIPT_NAME=`basename $0`

# if the user is not root, fail
THISUSER=`whoami`
if [ "${THISUSER}" != "root" ] ; then
	echo "${SCRIPT_NAME}: ERROR: requires script to be run as root!"
	exit 1
fi

# parse arguments
while [ "$1" != "" ] ; do
	case $1 in
		* )
			show_usage
			;;
	esac
	shift
done

# Run the test.
check_aja_rdma

echo "${SCRIPT_NAME}: test complete."
