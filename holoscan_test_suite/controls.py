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
# See README.md for detailed information.

# This module provides support for a few HTML UI elements, using a websocket and
# JS to 1) send UI selections to the server and 2) for the server to provide
# updated data for the UI.  All these controls write their values using
# websocket broadcast requests, so any number of clients can connect and they'll
# always see synchonized state.


import flask_socketio
from . import html_render
import os
import subprocess
import traceback


class Runner:
    """
    Runner manages a subprocess that is invoked by the UI, providing a way
    for the user to start and stop the command and for stdout and stderr
    from the process to appear on the UI.  Once the runner is constructed,
    be sure and call "(runner).set_control(ui_element)" in order for stderr
    and stdout to be displayed as expected.
    """

    def __init__(self, reactor, app, command, env_update={}, cwd=None):
        self._app = app
        self._command = command
        self._process = None
        self._env_update = env_update
        self._cwd = cwd
        self._reactor = reactor

    def set_control(self, control):
        """I don't set self._control in the
        constructor so we're sure to get an
        error if someone doesn't call set_control.
        """
        self._control = control
        self._control_name = control._control_name

    def start(self):
        if self._process is None:
            # Clear the stdout/stderr displayed on the page
            with self._app.test_request_context("/"):
                flask_socketio.emit(
                    "%s-reset" % self._control_name,
                    {"control": self._control_name},
                    broadcast=True,
                    namespace="/",
                )
            self._start()
        else:
            print('Already started "%s" -- ignoring' % (self._command,))

    def _start(self):
        print('Starting "%s"' % (self._command,))
        env = {}
        env.update(os.environ)  # make a copy of the current environment
        env.update(self._env_update)  # update it according to our prefs
        self._stdout_r, self._stdout_w = os.pipe()
        self._stderr_r, self._stderr_w = os.pipe()
        self._reactor.register(self._stdout_r, self.stdout)
        self._reactor.register(self._stderr_r, self.stderr)
        try:
            self._process = subprocess.Popen(
                args=self._command,
                env=env,
                stdout=self._stdout_w,
                stderr=self._stderr_w,
                cwd=self._cwd,
                bufsize=0,
            )
        except Exception as e:
            s = traceback.format_exception(e)
            l = "".join(s)
            os.write(self._stderr_w, l.encode("utf-8"))
            print(l)
        os.close(self._stdout_w)
        self._stdout_w = -1
        os.close(self._stderr_w)
        self._stderr_w = -1

    def stop(self):
        if self._process is not None:
            self._stop()
        else:
            print('Not currently running "%s" -- ignoring' % (self._command,))

    def _stop(self):
        process = self._process
        self._process = None
        print('Stopping "%s"' % (self._command,))
        process.terminate()
        timeout_s = 20
        process.communicate(timeout=timeout_s)
        if self._stdout_w != -1:
            os.close(self._stdout_w)
            self._stdout_w = -1
        if self._stderr_w != -1:
            os.close(self._stderr_w)
            self._stderr_w = -1
        self._control.stopped()

    def update(self, state):
        if state:
            self.start()
        else:
            self.stop()
        return self._process is not None

    def stderr(self, event):
        value = os.read(self._stderr_r, 8192).decode()
        if len(value) == 0:
            print("stderr closed.")
            self._reactor.unregister(self._stderr_r)
            os.close(self._stderr_r)
            if self._process is not None:
                self.stop()
            return
        with self._app.test_request_context("/"):
            flask_socketio.emit(
                "%s-stderr" % self._control_name,
                {"control": self._control_name, "value": value},
                broadcast=True,
                namespace="/",
            )

    def stdout(self, event):
        value = os.read(self._stdout_r, 8192).decode()
        if len(value) == 0:
            print("stdout closed.")
            self._reactor.unregister(self._stdout_r)
            os.close(self._stdout_r)
            if self._process is not None:
                self.stop()
            return
        with self._app.test_request_context("/"):
            flask_socketio.emit(
                "%s-stdout" % self._control_name,
                {"control": self._control_name, "value": value},
                broadcast=True,
                namespace="/",
            )


class Control:
    """
    Superclass for UI elements that have these methods:
    - render: creates the HTML (including the JS),
    - request: callback when the UI requests the current value,
    - update: callback when the UI wishes to change the value
    - stopped: runner calls this when the process terminates
    """

    def __init__(self, app, label, control_name):
        self._app = app
        self._label = label
        self._control_name = control_name

    def render(self, r):
        """
        This method is used to create the HTML that
        renders the control, along with javascript
        support (e.g. so that this control can call
        request() or update()).  The HTML this guy
        generates is to be appended to the list
        given in the parameter 'r'.
        """
        pass

    def request(self, control_name):
        """
        When the UI wants to know what the
        state of this control is, the framework
        generates a call to request.
        @returns a dict with a "value" field
        that controls the state of the item
        in the UI.  For example, a Checkbox
        expects the value to be True or False:
        @code
            return {
                "value": True # or False as appropriate
            }
        @endcode
        Other control types may expect strings or
        other data types.
        """
        pass

    def update(self, control_name, value):
        """
        The framework calls this method
        when the user changes the value
        on the UI.  This method returns
        a dict following the same spec
        as the request method.
        """
        pass

    def stopped(self):
        """
        Runner calls this when it detects the program
        it's supervising has terminated; e.g. Checkbox uses
        this to set the UI value to False (unchecking
        the box on the UI).
        """
        pass


class Checkbox(Control):
    """
    Provides a Control which is rendered as a checkbox
    and the value is "True" or "False"
    """

    def __init__(
        self, app, label, control_name, value=False, update=lambda value: value
    ):
        super(Checkbox, self).__init__(app, label, control_name)
        self._value = value
        self._update = update

    def render(self, r):
        """
        Provide the HTML that implements the checkbox, including
        the Checkbox control and Javascript support code to keep
        the value shown in the browser up to date.

        """
        r.append(
            [
                # Render the input element itself in a disabled (grayed out) mode;
                # we'll enable it when we get the current value from the server via js.
                html_render.checkbox(
                    self._label,
                    attributes={
                        "disabled": None,
                        "id": self._control_name,
                    },
                ),
                # Render a table--which is normally hidden--where we'll put the
                # stdout and stderr generated when this control is activated.
                html_render.table(
                    [
                        [
                            "stdout",
                            html_render.pre(
                                html_render.div(
                                    "",
                                    attributes={"id": "%s_stdout" % self._control_name},
                                ),
                            ),
                        ],
                        [
                            "stderr",
                            html_render.pre(
                                html_render.div(
                                    "",
                                    attributes={"id": "%s_stderr" % self._control_name},
                                ),
                            ),
                        ],
                    ],
                    attributes={"id": f"{self._control_name}_output", "hidden": None},
                ),
                # Javascript support
                html_render.javascript(
                    f"""
                // Make js variables that point to the checkbox and it's stdout/stderr fields.
                const {self._control_name} = document.getElementById("{self._control_name}");
                const {self._control_name}_stdout = document.getElementById("{self._control_name}_stdout");
                const {self._control_name}_stderr = document.getElementById("{self._control_name}_stderr");
                const {self._control_name}_output = document.getElementById("{self._control_name}_output");
                // Request the initial value from the server.
                socket.on("connect", (event) => {{
                    console.log("Requesting status: {self._control_name}");
                    socket.emit("request", {{control: "{self._control_name}"}});
                }});
                // Handle updates (incl the initial value) from the server;
                // update the control per the value and enable the control.
                socket.on("{self._control_name}-value", (event) => {{
                    value = event.value;
                    console.log("Value received, {self._control_name}=" + value);
                    {self._control_name}.checked = value;
                    {self._control_name}.disabled = !event.enable;
                }});
                // When the user clicks this thing, send the new value to the server.
                {self._control_name}.onclick = function() {{
                    socket.emit("update", {{value: this.checked, control: "{self._control_name}"}});
                }};
                // When the websocket closes, gray this thing out.
                socket.on("disconnect", (event) => {{
                    console.log("Closing {self._control_name}");
                    {self._control_name}.disabled = true;
                }});
                // add to stdout
                socket.on("{self._control_name}-stdout", (event) => {{
                    value = event.value;
                    console.log("stdout received, {self._control_name}=" + value);
                    {self._control_name}_stdout.append(value);
                    {self._control_name}_output.hidden = false;
                }});
                // add to stderr
                socket.on("{self._control_name}-stderr", (event) => {{
                    value = event.value;
                    console.log("stderr received, {self._control_name}=" + value);
                    {self._control_name}_stderr.append(value);
                    {self._control_name}_output.hidden = false;
                }});
                // clear both stdout and stderr
                socket.on("{self._control_name}-reset", (event) => {{
                    {self._control_name}_stdout.innerHTML = "";
                    {self._control_name}_stderr.innerHTML = "";
                    {self._control_name}_output.hidden = true;
                }});
            """
                ),
            ]
        )

    def update(self, control_name, value):
        r = self._update(value)
        self._value = r
        return {
            "control": control_name,
            "value": self._value,
            "enable": True,
        }

    def request(self, control_name):
        return {
            "control": control_name,
            "value": self._value,
            "enable": True,
        }

    def stopped(self):
        reply = self.update(self._control_name, False)
        with self._app.test_request_context("/"):
            flask_socketio.emit(
                "%s-value" % self._control_name,
                reply,
                broadcast=True,
                namespace="/",
            )


class Status(Control):
    """
    Renders as a static <div> where a value can be displayed.
    Calling "publish" on this object will update the UI.
    @code
        value = "whatever new value you want to display"
        status_object.publish({"value": value})
    @endcode

    """

    def __init__(self, app, label, control_name):
        super(Status, self).__init__(app, label, control_name)

    def render(self, r):
        attributes = {
            "id": self._control_name,
            "disabled": None,
        }
        r.append(
            [
                self._label,
                [
                    html_render.pre(html_render.div("", attributes=attributes)),
                    # Javascript support
                    html_render.javascript(
                        f"""
                    // Make a js variable that points to the checkbox.
                    const {self._control_name} = document.getElementById("{self._control_name}");
                    // Request the initial value from the server.
                    socket.on("connect", (event) => {{
                        console.log("Requesting status: {self._control_name}");
                        socket.emit("request", {{control: "{self._control_name}"}});
                    }});
                    // Handle updates (incl the initial value) from the server;
                    // update the control per the value and enable the control.
                    socket.on("{self._control_name}-value", (event) => {{
                        value = event.value;
                        console.log("Value received, {self._control_name}=" + value);
                        {self._control_name}.innerHTML = value;
                        {self._control_name}.disabled = false;
                    }});
                    // When the websocket closes, gray this thing out.
                    socket.on("disconnect", (event) => {{
                        console.log("Closing {self._control_name}");
                        {self._control_name}.disabled = true;
                    }});
                """
                    ),
                ],
            ]
        )

    def publish(self, value):
        reply = {
            "control": self._control_name,
            "enable": True,
        }
        reply.update(value)
        with self._app.test_request_context("/"):
            flask_socketio.emit(
                "%s-value" % self._control_name,
                reply,
                broadcast=True,
                namespace="/",
            )

    def stopped(self):
        pass
