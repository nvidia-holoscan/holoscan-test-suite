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
import cv2
import holoscan_test_suite
import os
import signal
import time

done = False


def set_done(*args):
    global done
    done = True


signal.signal(signal.SIGTERM, set_done)


def show_test_pattern(filename, display):
    # We may be restarted via control_app.py
    global done
    done = False

    # We only support 1920x1080.
    columns = 1920
    rows = 1080

    #
    image = cv2.imread(filename)  # BGRA
    image_rows, image_columns, image_width = image.shape
    assert image_rows == rows
    assert image_columns == columns

    # Mount an overlayfs so we can temporarily patch /etc/X11/xorg.conf.d.
    print("Setting up overlayfs.")
    os.makedirs("/tmp/overlay/etc", exist_ok=True)
    os.makedirs("/tmp/overlay/work", exist_ok=True)
    s = "/bin/mount -t overlay overlay -o lowerdir=/etc,upperdir=/tmp/overlay/etc,workdir=/tmp/overlay/work /etc"
    assert os.system(s) == 0
    try:
        # Write our special xorg.conf stanza that sets us up for 1920x1080 mode.
        s = """
Section "Screen"
    Identifier     "Screen0"
    Device         "Device0"
    Monitor        "Monitor0"
    DefaultDepth    24
    SubSection     "Display"
        Depth       24
    EndSubSection
    Option "ConnectedMonitor" "GPU-0.DP-7"
    Option "CustomEDID" "GPU-0.DP-7:/etc/X11/edid.bin"
    Option "MetaModes" "GPU-0.DP-7:1920x1080+0+0"
EndSection
"""
        with open("/etc/X11/xorg.conf.d/mgx.conf", "wt") as f:
            f.write(s)
        # That stanza relies on /etc/X11/edid.bin.  Write that now.
        # fmt: off
        # (Without fmt:off, black will spread this out to one byte per line.)
        # This EDID data was recorded using "xrandr --props" when the port
        # was connected to a powered-on P3785.
        edid = bytes([
            0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x4D, 0xD9, 0x06, 0x5A, 0x01, 0x01, 0x01, 0x01,
            0x1E, 0x1E, 0x01, 0x03, 0x80, 0x6F, 0x3E, 0x78, 0x0A, 0xEE, 0x91, 0xA3, 0x54, 0x4C, 0x99, 0x26,
            0x0F, 0x50, 0x54, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x02, 0x3A, 0x80, 0x18, 0x71, 0x38, 0x2D, 0x40, 0x58, 0x2C,
            0x45, 0x00, 0x50, 0x1D, 0x74, 0x00, 0x00, 0x1E, 0x02, 0x3A, 0x80, 0x18, 0x71, 0x38, 0x2D, 0x40,
            0x58, 0x2C, 0x45, 0x00, 0x50, 0x1D, 0x74, 0x00, 0x00, 0x1E, 0x00, 0x00, 0x00, 0xFD, 0x00, 0x18,
            0x4B, 0x0F, 0x87, 0x3C, 0x00, 0x0A, 0x20, 0x20, 0x20, 0x20, 0x20, 0x20, 0x00, 0x00, 0x00, 0xFC,
            0x00, 0x4C, 0x54, 0x36, 0x39, 0x31, 0x31, 0x55, 0x58, 0x43, 0x0A, 0x20, 0x20, 0x20, 0x00, 0x22,
        ])
        # fmt: on
        with open("/etc/X11/edid.bin", "wb") as f:
            f.write(edid)
        # Now restart X so that it sees this new EDID.
        print("Restarting display-manager.")
        assert os.system("/bin/systemctl restart display-manager") == 0
        # Let it start up.
        time.sleep(5)

        # Ask xrandr to change the display for us
        os.environ["DISPLAY"] = display
        s = "/usr/bin/xrandr --size %sx%s" % (columns, rows)
        assert os.system(s) == 0

        # Deactivate the screen saver.  This works to bring
        # up the display if we've been sitting around and it's
        # gone off.
        s = "/usr/bin/xset -dpms s off s noblank s 0 0 s noexpose"
        assert os.system(s) == 0

        #
        cv2.namedWindow(filename, cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty(filename, cv2.WND_PROP_FULLSCREEN, 1)
        cv2.imshow(filename, image)
        # Let cv2 update the display.
        cv2.waitKey(10)
        print("Image displayed.")
        while not done:
            cv2.waitKey(100)
        return 0

    finally:
        # Don't leave our /etc overlay sitting around.
        print("Removing overlayfs.")
        s = "/bin/umount /etc"
        r = os.system(s)
        print("umount returned %s" % (r,))
        # Now restart X to go back to normal
        print("Restarting display-manager.")
        os.system("/bin/systemctl restart display-manager")


def main():
    parser = argparse.ArgumentParser(
        description="Tool to display a .png file in fullscreen mode."
    )
    parser.add_argument(
        "--filename",
        default=holoscan_test_suite.default_test_image,
        help="Name of .png file to display.",
    )
    parser.add_argument(
        "--display",
        default=":0",
        help="Display to use",
    )
    args = parser.parse_args()
    show_test_pattern(args.filename, args.display)


if __name__ == "__main__":
    main()
