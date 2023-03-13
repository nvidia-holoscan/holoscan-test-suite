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
#       Script fails unless you're running on a Clara AGX Devkit configuration.
#       MGX must have a SATA device on /dev/sda
#
# NOTE:
#       Do NOT run this on your host machine, it will NUKE /dev/sda device.
#       This script does attempt to ensure that you're running on
#       a Clara AGX Devkit unit.
#
# USAGE:
#       bringup_sata_clara_agx_devkit.sh
#
# EXIT STATUS:
#       This scripts exits with status 0 if the test succeeds;
#       any non-zero value indicates a test failure.
#

# source kernel based config file
KERNEL_VERSION=$(uname -r | cut -d '.' -f-2)
source "${SCRIPT_DIRECTORY}"/module_common_"${KERNEL_VERSION}".conf
source "check_clara_agx_devkit.sh"

# fail the script on errors
set -e
set -o xtrace

function check_device {
    DRIVE=${1}
    # This fails is we're not a drive.
    lsblk ${DRIVE}
}

function check_disk_io {
    DRIVE=${1}

    # Start with zeroes.
    dd if=/dev/zero of=$DRIVE bs=1M count=1
    sync
    MD5SUM=`dd if=$DRIVE bs=1M count=1 | md5sum | awk '{print $1}'`
    ZERO_MD5SUM=b6d81b360a5672d80c27430f39153e2c
    test $MD5SUM = $ZERO_MD5SUM

    # Now write some data.
    HELLO="Hello world"
    HELLO_MD5SUM="2c50d80b41b6a44e81ede86bf5bd6e25"
    # We should include "conv=sync" here (to write 0s through the rest of
    # the block) but our busybox doesn't have that enabled.  Since
    # we wrote 0s in the previous step, there's no ambiguity here.
    echo $HELLO | dd of=$DRIVE bs=1M count=1
    sync
    MD5SUM=`dd if=$DRIVE bs=1M count=1 | md5sum | awk '{print $1}'`
    test $MD5SUM = $HELLO_MD5SUM

    # Go back to zeroes.
    dd if=/dev/zero of=$DRIVE bs=1M count=1
    sync
    MD5SUM=`dd if=$DRIVE bs=1M count=1 | md5sum | awk '{print $1}'`
    test $MD5SUM = $ZERO_MD5SUM
}


function show_usage {
cat << EOF
Usage: ${SCRIPT_NAME}
Checks for I/O on all non-boot disks (${DEVICES}).
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

DEVICES="/dev/sda"

# parse arguments
while [ "$1" != "" ] ; do
	case $1 in
		* )
			show_usage
			;;
	esac
	shift
done

for DEVICE_NAME in $DEVICES
do

check_clara_agx_devkit
check_device $DEVICE_NAME
check_disk_io $DEVICE_NAME

done

echo "${SCRIPT_NAME}: test complete."
