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

# holoscan_test_controls.py creates the web UI that allows users to execute a list of
# commands on demand.  See HoloscanTestControls.setup() below.

import engineio.payload
import flask
import flask_socketio
from holoscan_test_suite import controls
from holoscan_test_suite import html_render
from holoscan_test_suite import reactor
import os
import re
import subprocess

# When the UI requests the initial state, we get
# a number of small requests-- don't limit the number
# of requests we're allowed to queue up.
engineio.payload.Payload.max_decode_packets = 100


class HoloscanTestControls:
    """
    HoloscanTestControls is a webapp where an HTML UI displays
    - status values that are dynamically updated from the server
    - actions that the user can perform.
    The values shown on the display are dynamically updated
    by snippets of javascript included in the HTML that
    coordinate with a websocket server running here.
    """

    def __init__(self, app):
        self._app = app
        self._actions = []
        self._status = []
        self._request = {}
        self._update = {}
        self._proc_stat = {}
        #
        self._reactor = reactor.Reactor()
        self._reactor.start()
        #
        self.setup()
        # Generate the index HTML page from the controls initialized by
        # setup().  We always publish the same page so let's just cache that
        # for whoever wants it.  (The controls update themselves dynamically.)
        self._index_cache = self._index()

    def setup(self):
        # Control: show the test pattern
        self.checkbox_command(
            control_name="show_test_pattern",
            label="Enable 1920x1080 video test pattern",
            command="show_test_pattern",
        )
        # Control: show the endoscopy demo from a recorded video input.
        self.checkbox_command(
            control_name="recorded_endoscopy_demo",
            label="Run the tool tracking demo (with recorded input)",
            command="./applications/endoscopy_tool_tracking/cpp/endoscopy_tool_tracking",
            env_update={"DISPLAY": ":0"},
            cwd="/opt/nvidia/holohub",
        )
        # Control: run iperf3, the server that supports network performance testing
        self.checkbox_command(
            control_name="enable_iperf3",
            label="Run iperf server, listening to TCP and UDP port 5201 on all ethernets including WIFI",
            command="iperf3 -s",
        )
        # Control: run "e2fsck" on nvme0n1
        e2fsck_command = "e2fsck -c -y /dev/nvme0n1"
        self.checkbox_command(
            control_name="e2fsck_nvme0n1",
            label='Filesystem check of envme0n1 (via "%s")' % e2fsck_command,
            command=e2fsck_command,
        )
        # Control: run "mke2fs" on nvme0n1; e2fsck won't work until
        # we have a filesystem there.
        mke2fs_command = "mke2fs /dev/nvme0n1"
        self.checkbox_command(
            control_name="mke2fs_nvme0n1",
            label='Make a ext2 filesystem on nvme0n1 (via "%s")' % mke2fs_command,
            command=mke2fs_command,
        )
        # Control: run memtest on each core.
        mb = 1024 * 1024
        gb = 1024 * mb
        memory_test_size = 2 * gb
        for cpu in os.sched_getaffinity(0):
            command = "taskset -c %s memtester %sM" % (cpu, (memory_test_size // mb))
            self.checkbox_command(
                control_name="memtest_with_cpu_%s" % cpu,
                label='Run memtest on CPU %s (via "%s")' % (cpu, command),
                command=command,
            )
        # Control: disable the X-windows screen saver.
        disable_screen_saver_command = (
            "/usr/bin/xset -dpms s off s noblank s 0 0 s noexpose"
        )
        self.checkbox_command(
            control_name="disable_screensaver",
            label='Disable X screen saver (via "%s")' % disable_screen_saver_command,
            command=disable_screen_saver_command,
            env_update={"DISPLAY": ":0"},
        )

        # Status: Available RAM
        def memory_free_status(control_name):
            meminfo = self.get_meminfo()
            r = {
                "value": "%sM" % (meminfo["MemFree"] // mb),
            }
            return r

        memory_status = self.status(
            control_name="memory_status",
            label="Memory free (MB)",
            requester=memory_free_status,
        )
        self._reactor.periodic_alarm(
            period_s=5, callback=lambda: memory_status.publish(memory_free_status(None))
        )

        # Status: Thermal zones.
        def get_thermal_zone(control_name, filename):
            with open(filename, "rt") as f:
                s = f.read()
            v = int(s)
            c = v / 1000
            r = "%.2fC" % (c,)
            # print("%s=%s" % (self._control_name, r))
            return {
                "value": r,
            }

        for type_name, filename in self.thermal_zones():
            requester = lambda control_name, filename=filename: get_thermal_zone(
                control_name, filename
            )
            status = self.status(
                control_name=type_name.lower().replace("-", "_"),
                label="Thermal zone: %s" % type_name,
                requester=requester,
            )
            self._reactor.periodic_alarm(
                period_s=5,
                callback=lambda status=status, requester=requester: status.publish(
                    requester(None)
                ),
            )
        # Status: CPU usage
        self.update_proc_stat()

        def get_cpu_usage(cpu_name):
            r = "Offline"
            with open("/sys/devices/system/cpu/%s/online" % cpu_name, "rt") as f:
                s = f.read()
            online = int(s)
            if online > 0:
                u = self._proc_stat[cpu_name]
                stat = [int(s) for s in u.split()]
                last_cpu_name = "last_%s" % cpu_name
                last_stat = self._proc_stat.get(last_cpu_name, None)
                if last_stat:
                    delta = [b - a for a, b in zip(last_stat, stat)]
                else:
                    delta = ["N/A" for a in stat]
                self._proc_stat[last_cpu_name] = stat
                r = "user=%s nice=%s system=%s idle=%s iowait=%s irq=%s softirq=%s" % (
                    *delta[:7],
                )
            return {
                "value": r,
            }

        # cpu_usage_update is set up so that it first calls
        # self.update_proc_stat, then calls get_cpu_usage (which
        # reads self._proc_stat) for each processor.  This way we
        # don't get aliasing around the CPU usage on the display.
        cpu_usage_update = [self.update_proc_stat]
        for cpu_name in self.cpus():
            requester = lambda control_name, cpu_name=cpu_name: get_cpu_usage(cpu_name)
            status = self.status(
                control_name="cpu_usage_%s" % cpu_name,
                label="CPU usage: %s" % cpu_name,
                requester=requester,
            )
            updater = lambda status=status, cpu_name=cpu_name: status.publish(
                get_cpu_usage(cpu_name)
            )
            cpu_usage_update.append(updater)
        self._reactor.periodic_alarm(
            period_s=5,
            callback=lambda cpu_usage_update=cpu_usage_update: [
                u() for u in cpu_usage_update
            ],
        )
        # Status: dGPU usage
        dgpu_usage_command = "/usr/bin/nvidia-smi pmon -c 1"
        dgpu_usage_status = controls.Status(
            self._app, label="dGPU Usage", control_name="dgpu_usage"
        )
        self._status.append(dgpu_usage_status)

        def update_dgpu_usage():
            process = subprocess.Popen(
                args=dgpu_usage_command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            outs, errs = process.communicate(timeout=2)
            stdout_value = outs.decode("utf-8")
            dgpu_usage_status.publish({"value": stdout_value})

        self._reactor.periodic_alarm(period_s=5, callback=update_dgpu_usage)
        self._request[dgpu_usage_status._control_name] = lambda control_name: {
            "value": "N/A"
        }
        # Control: run gst, NVIDIA GPU stress test (https://github.com/NVIDIA/GPUStressTest)
        self.checkbox_command(
            control_name="gst",
            label="Run GST, the NVIDIA GPU Stress test",
            command="/usr/bin/gst",
        )
        #

    def checkbox_command(self, control_name, label, command, cwd=None, env_update={}):
        """
        Creates an HTML UI element that is a checkbox; when the
        user clicks it, we'll start the given command in the background.
        If that program terminates, we'll drive the UI back to the
        unchecked state; if it's checked and the user unchecks it,
        we'll kill the background program.
        """
        # runner is what supervises the command that this checkbox runs.
        runner = controls.Runner(
            self._reactor, self._app, command.split(), cwd=cwd, env_update=env_update
        )
        # control is how the checkbox and stdout/stderr is displayed
        control = controls.Checkbox(
            self._app, label, control_name, update=runner.update
        )
        # runner has asynchronous stdout/stderr data that it wants to pass up to UI
        runner.set_control(control)
        # when the control calls "request" (to fetch the current status), here's the handler for it
        self._request[control_name] = control.request
        # when the control calls "update" (to provide a new value), here's the handler for it
        self._update[control_name] = control.update
        # this is the list of items that are displayed on the page.
        self._actions.append(control)
        return runner

    def status(self, control_name, label, requester):
        """
        Creates an HTML UI item (which is really just a PRE section) that
        we can write stuff to via websocket.
        @returns the status object, call "status.publish(dict)" to update
        the value displayed on the UI there.  For details on the dict to
        be published, @see request() below.
        @param requester fetches the value to be displayed and
        takes control_name as a parameter.
        """
        status = controls.Status(self._app, label, control_name)
        # when the control calls "request" (to fetch the current status on startup), here's the handler for it
        self._request[control_name] = requester
        # add ourselves to the list of status displayed on the page.
        self._status.append(status)
        return status

    def index(self):
        """
        Called when a user requests the index page.  We've already
        created (and cached) the index page so just publish that.
        """
        return self._index_cache

    def _index(self):
        """
        Actually render the index page.  We sort the status
        items for display at the top of the page, then sort
        actions (which the user can enable or disable) and display
        them next.  Items are sorted using "naturally_sorted"
        below so that UI shows items in a consistent order.
        """
        # Status comes first
        rendered_status = []
        for a in self.naturally_sorted(self._status):
            a.render(rendered_status)
        # Actions are next
        rendered_actions = []
        for a in self.naturally_sorted(self._actions):
            a.render(rendered_actions)
        # Here's the page itself
        doc = [
            html_render.socket_io_js,
            html_render.javascript("var socket = io();"),
            self._reload_on_server_update(),
            html_render.header(3, "Status"),
            html_render.table(rendered_status),
            html_render.horizontal_rule(),
            html_render.header(3, "Actions"),
            html_render.ul(rendered_actions),
            html_render.horizontal_rule(),
        ]
        # Enable auto-wrapping of PRE sections
        styles = [
            html_render.style(
                "pre",
                {
                    "overflow-x": "auto",
                    "white-space": "pre-wrap",
                    "word-wrap": "break-word",
                },
            )
        ]
        head = html_render.head(styles)
        body = html_render.body(doc)
        html = html_render.html([head, body])
        # Send it.
        r = html_render.render(html)
        return r

    def naturally_sorted(self, l):
        """
        Sort the given list in a natural way, so that "CPU_10" comes after "CPU_2"
        """
        extract_parts = re.compile("[^0-9]+|[0-9]+")

        def maybe_int(s):
            try:
                return int(s)
            except ValueError:
                return s

        def key(control):
            parts = extract_parts.findall(control._label)
            r = [maybe_int(s) for s in parts]
            return r

        return sorted(l, key=key)

    def _reload_on_server_update(self):
        """
        Returns HTML that instructs the page
        to reload itself if the server restarts.
        This works by the server passing us
        a "reload" instruction with it's PID;
        if that PID is different than the one the
        client is currently displaying, then
        the client will reload to get the current
        server's page (with it's new PID).  See
        "connection()" below.
        """
        return html_render.javascript(
            """
            socket.on("reload", (event) => {
                console.log("event.id=" + event.id);
                if (event.id != %s) {
                    location.reload();
                }
            });
        """
            % os.getpid()
        )

    def request(self, message):
        """
        Handle a UI "request", which reports the control's
        current value.  We broadcast the result to make sure
        all clients show a consistent state.
        """
        control_name = message["control"]
        reply = {
            "control": control_name,
            "enable": True,
        }
        strategy = self._request.get(control_name, self._bad_request)
        value = strategy(control_name)
        reply.update(value)
        flask_socketio.emit(
            "%s-value" % control_name,
            reply,
            broadcast=True,
        )

    def _bad_request(self, control_name):
        print('No request strategy for "%s"' % (control_name,))
        return {
            "control_name": control_name,
            "enable": False,
            "value": "N/A",
        }

    def update(self, message):
        """
        Handle a UI "update", which changes the value of a control.
        We call the given control's update callback, which returns
        a new value to report to the user.  Send that new
        value out in broadcast mode so everyone sees it.
        """
        control_name = message["control"]
        requested_value = message["value"]
        reply = {
            "control": control_name,
            "enable": True,
        }
        strategy = self._update.get(control_name, self._bad_update)
        value = strategy(control_name, requested_value)
        reply.update(value)
        flask_socketio.emit(
            "%s-value" % control_name,
            reply,
            broadcast=True,
        )

    def _bad_update(self, control_name, new_value):
        print('No update strategy for "%s"' % (control_name,))
        return {
            "control_name": control_name,
            "enable": False,
            "value": "N/A",
        }

    def get_meminfo(self):
        """
        Returns a map of name/value pairs,
        where the names and values are read from
        "/proc/meminfo".  We use this to
        e.g. figure out how much RAM is in use.
        """
        r = {}
        kb_match = re.compile("([a-zA-Z0-9_]+):[ ]+([0-9]+) kB")
        with open("/proc/meminfo", "rt") as f:
            for l in f:
                m = kb_match.match(l)
                if m:
                    r[m.group(1)] = 1024 * int(m.group(2))
        return r

    def thermal_zones(self):
        """
        yields the thermal zone's "type" and the filename where that zone's
        temperature can be read.
        """
        thermal = "/sys/class/thermal"
        for zone_name in os.listdir(thermal):
            temp = os.path.join(thermal, zone_name, "temp")
            type_ = os.path.join(thermal, zone_name, "type")
            if not os.path.isfile(temp):
                continue
            if not os.path.isfile(type_):
                continue
            with open(type_, "rt") as f:
                type_name = f.read().strip()
            yield type_name, temp

    def update_proc_stat(self):
        """
        Get a list of name/value pairs from "/proc/stat" and
        save that to self._proc_stat.
        """
        r = {}
        with open("/proc/stat", "rt") as f:
            for l in f:
                s = l.split(" ", 1)
                r[s[0]] = s[1]
        self._proc_stat.update(r)

    def cpus(self):
        """
        Yields "cpu0", "cpu1", ...
        """
        cpu_directory = "/sys/devices/system/cpu"
        cpu_match = re.compile("(cpu[0-9]+)")
        for cpu_file in os.listdir(cpu_directory):
            m = cpu_match.match(cpu_file)
            if not m:
                continue
            yield m.group(1)


app = flask.Flask(__name__)
socketio = flask_socketio.SocketIO(app, cors_allowed_origins="*")
holoscan_test_controls = HoloscanTestControls(app)


@app.route("/")
def index():
    return holoscan_test_controls.index()


@socketio.on("update")
def update(message):
    holoscan_test_controls.update(message)


@socketio.on("request")
def request(message):
    holoscan_test_controls.request(message)


@socketio.on("connect")
def connection():
    """
    Support for telling the client to reload itself when the server
    restarts.  The page itself includes our PID (via
    _reload_on_server_update).  This callback--which we get when the client
    reconnects to us--tells the client to reload itself if the PID they
    have is different than ours.
    """
    flask_socketio.emit("reload", {"id": os.getpid()})


def main():
    socketio.run(app, host="0.0.0.0", port=8767)


if __name__ == "__main__":
    main()
