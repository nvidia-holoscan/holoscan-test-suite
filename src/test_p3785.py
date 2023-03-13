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

import cv2
import holoscan_test_suite
import numpy as np
import pytest
import subprocess
import sys
import time


# Check for video ingress on P3785;
# relies on
#   - a working P3785
#   - Test image at 1920x1080,60fps
#       presented to the HDMI input--
#       show_test_pattern.py does this
# "capsys" here is how we save our stdout/stderr
# into the generated report.
@pytest.mark.igx_orin_devkit_only
def test_p3785(capsys):
    print("Test IGX Orin Devkit P3785.")
    # We only support 1920x1080 images.
    columns = 1920
    rows = 1080
    pixel_format = "BGRA"
    bytes_per_pixel = 4
    device = "/dev/video0"
    frames_per_sec = 60
    record_filename = "/tmp/video.raw"
    pixels_per_image = columns * rows
    bytes_per_image = pixels_per_image * bytes_per_pixel
    # Load up our test image; this is the same
    # image that's expected to be recorded
    test_image_filename = holoscan_test_suite.default_test_image
    test_image_bgr = cv2.imread(test_image_filename)  # cv2.imread always returns BGR
    # We acquire BGRA data, so convert our test image to that
    test_image_bgra = cv2.cvtColor(test_image_bgr, cv2.COLOR_BGR2BGRA)
    image_rows, image_columns, image_width = test_image_bgra.shape
    assert image_rows == rows
    assert image_columns == columns
    # Run "show_test_pattern" to bring up the test image on X
    command = f"show_test_pattern --filename {test_image_filename}"
    print('Running "%s"' % (command,))
    show_test_pattern = subprocess.Popen(
        command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        # Let show_test_pattern start up
        time.sleep(5)

        # Run the recorder for 1 second at 60fps.
        # Note that we impose the timeoverlay on the image--
        # this way we see changes in the image itself and
        # a difference from the test image that is greater
        # than 0 but less than a relatively small threshold.
        assert pixel_format == "BGRA"
        command = f"/usr/bin/gst-launch-1.0 v4l2src io-mode=mmap device={device} ! video/x-raw,format={pixel_format},width={columns},height={rows},framerate={frames_per_sec}/1 ! timeoverlay ! videoconvert ! filesink location={record_filename}"
        print('Running "%s"' % (command,))
        gst = subprocess.Popen(
            command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            # Record a few frames
            time.sleep(5)
        finally:
            gst.kill()
            time.sleep(2)
        out, err = gst.communicate()
        for l in out.decode("utf-8").split("\n"):
            print(l)
        for l in err.decode("utf-8").split("\n"):
            print(l, file=sys.stderr)
    finally:
        show_test_pattern.terminate()
        time.sleep(2)
        out, err = show_test_pattern.communicate()
        for l in out.decode("utf-8").split("\n"):
            print(l)
        for l in err.decode("utf-8").split("\n"):
            print(l, file=sys.stderr)
    # Load our actual recorded data.
    with open(record_filename, "rb") as f:
        # How many frames did we record?
        SEEK_END = 2
        f.seek(0, SEEK_END)
        video_byte_length = f.tell()
        # frames may have a fraction given that we kill gst without
        # respect to where it was writing data.
        frames = video_byte_length / bytes_per_image
        print("video_byte_length=%s frames=%s" % (video_byte_length, frames))
        assert frames > 1
        # Load the last frame.
        last_whole_frame = int(frames) - 1
        f.seek(last_whole_frame * bytes_per_image)
        np_raw_data = np.fromfile(f, dtype=np.uint8, count=bytes_per_image)
        last_acquired_image_bgra = np_raw_data.reshape(
            rows, columns, bytes_per_pixel
        )  # this is BGRA per pixel_format above
        # How different is this from our test image?
        diff = cv2.absdiff(test_image_bgra, last_acquired_image_bgra)
        # Now many pixels are different?
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGRA2GRAY)
        differences = np.count_nonzero(gray_diff)
        percent = (differences / pixels_per_image) * 100.0
        print(
            "differences, test_image_bgra to last_acquired_image_bgra=%s (%.1f%%)"
            % (differences, percent)
        )
        # gstreamer superimposed the timestamp on the test image,
        # so it has have some differences; the display stream is also
        # mathematically lossy, so some difference is expected.
        assert percent > 0.1
        # but not TOO different.
        assert percent < 10.0
