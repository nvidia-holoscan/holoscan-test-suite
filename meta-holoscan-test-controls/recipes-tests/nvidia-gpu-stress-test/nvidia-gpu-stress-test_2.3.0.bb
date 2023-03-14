DESCRIPTION = "NVIDIA GPU Stress test"
HOMEPAGE = "https://github.com/NVIDIA/GPUStrestTest/"

LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://License;md5=5d5211213623d8c0032f9a9bcb4e514c"

SRC_URI = "git://github.com/NVIDIA/GPUStressTest.git;branch=2.3;protocol=https"
SRCREV = "f15f6c5f8b2d46219de1f0115d907b30ae991fbb"

SRC_URI += "file://0001-Update-CMakefile-for-OE-build.patch"

S = "${WORKDIR}/git"

inherit cmake cuda
