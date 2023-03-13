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


#
# PRE-REQUISITES:
#       This test fails if we don't find an RTL8822CE (10ec:c822) on the PCI bus.
#
# USAGE:
#       bringup_wifi_igx_orin_devkit.sh
#
# EXIT STATUS:
#       This scripts exits with status 0 if the test succeeds;
#       any non-zero value indicates a test failure.
#

# source kernel based config file
KERNEL_VERSION=$(uname -r | cut -d '.' -f-2)
source "${SCRIPT_DIRECTORY}"/module_common_"${KERNEL_VERSION}".conf

# fail the script on errors
set -e
set -o xtrace

function check_for_wifi_via_pci {
    STATUS=`lspci -m -d 10ec:c822`
    # If lspci can't find our device, then the
    # "set -e" above will terminate our script.
    echo $STATUS | grep -q "RTL8822CE"
    # "set -e" makes it so if grep doesn't see
    # the string we're looking for then we terminate.
    # Note that this check is redundant with
    # the lspci command.
}


function show_usage {
cat << EOF
Usage: ${SCRIPT_NAME}
Checks for the presence of RTL8822CE.
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
check_for_wifi_via_pci

echo "${SCRIPT_NAME}: test complete."
