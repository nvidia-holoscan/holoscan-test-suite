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

# Reactor provides a runtime environment for event handlers; where
# events typically come from file descriptors that are ready to read.
# Reactors also call handlers based on single-shot or periodic alarms.

import collections
import os
import select
import threading
import time
import traceback

# Reactor has a list of alarms that are
# instances of this.
ReactorAlarm = collections.namedtuple(
    "ReactorAlarm", ["deadline", "period_s", "callback"]
)


class Reactor:
    """
    Reactor provides a runtime environment for
    handlers that are called when either a file
    descriptor has data to read or if a timeout
    expires.  Any number of file descriptors or
    alarms can be connected to a reactor instance.
    Handlers should not block; all reactor activity
    is serialized, so the next handler will wait
    until the currently executing handler is done.

    @code
        reactor = Reactor()
        # Start the reactor in a daemon thread
        reactor.start()
        # Example usage
        r_fd, w_fd = os.pipe()
        def pipe_handler():
            value = os.read(r_fd, 8192)
        reactor.register(r_fd, pipe_handler)
        # So now when someone calls
        os.write(w_fd, b"HELLO")
        # the reactor will call pipe_handler in its
        # background thread; pipe_handler's call
        # to os.read will complete immediately
        # because there is data to be read.
    @endcode

    Reactor also supports alarms, with a deadline
    that is compared to "time.monotonic()".
    @code
        def alarm():
            print("Alarm expired!")
        timeout_s = 5
        reactor.alarm(time.monotonic() + timeout_s, alarm)
    @endcode
    In (at least) 5 seconds from now, the background thread will
    call alarm().
    """

    ALARM_UPDATE = b"ALARM_UPDATE"
    DONE = b"DONE"

    def __init__(self):
        self._alarms = []  # [ReactorAlarm, ...]; sorted earliest deadline first
        self._alarms_lock = threading.Lock()
        self._control_r, self._control_w = os.pipe()
        self._epoll = select.epoll()
        self._epoll_map = {}
        self._done = False
        self.register(self._control_r, self._control_ready)

    def start(self):
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self._thread.start()

    def _run(self):
        while not self._done:
            # Call all expired timeouts.
            timeout_s = None
            while True:
                with self._alarms_lock:
                    if len(self._alarms) < 1:
                        break
                    # self._alarms is always sorted, earliest deadline first
                    reactor_alarm = self._alarms[0]
                    now = time.monotonic()
                    if reactor_alarm.deadline > now:
                        timeout_s = reactor_alarm.deadline - now
                        break
                    # So this deadline has been reached.
                    if reactor_alarm.period_s is None:
                        self._alarms.pop(0)
                    else:
                        # Update the deadline and reorder
                        self._alarms[0] = ReactorAlarm(
                            deadline=reactor_alarm.deadline + reactor_alarm.period_s,
                            period_s=reactor_alarm.period_s,
                            callback=reactor_alarm.callback,
                        )
                        self._alarms.sort()
                # Now self._alarms isn't locked anymore.
                try:
                    reactor_alarm.callback()
                except Exception as e:
                    print("Ignoring %s (%s)" % (e, type(e)))
                    traceback.print_exception(e)
            # We've handled all our timeouts; timeout_s will
            # either be None (because the alarms list was empty)
            # or be the number of seconds until the next deadline.
            events = self._epoll.poll(timeout=timeout_s)
            for fileno, event in events:
                try:
                    handler = self._epoll_map[fileno]
                    handler(event)
                except Exception as e:
                    print("Ignoring %s (%s)" % (e, type(e)))
                    traceback.print_exception(e)

    def register(self, fd, handler, event=select.EPOLLIN | select.EPOLLHUP):
        """Set a callback on a ready filedescriptor."""
        self._epoll_map[fd] = handler
        self._epoll.register(fd, event)

    def unregister(self, fd):
        """Remove a previously registered handler."""
        self._epoll.unregister(fd)
        del self._epoll_map[fd]

    def alarm(self, deadline, callback):
        """Queue up a callback to execute once the
        given deadline has passed.
        """
        reactor_alarm = ReactorAlarm(deadline, None, callback)
        with self._alarms_lock:
            self._alarms.append(reactor_alarm)
            self._alarms.sort()
        # wake up the polling thread
        self._signal(self.ALARM_UPDATE)
        return reactor_alarm

    def periodic_alarm(self, period_s, callback):
        """Queue up a callback to be executed periodically."""
        now = time.monotonic()
        deadline = now + period_s
        reactor_alarm = ReactorAlarm(deadline, period_s, callback)
        with self._alarms_lock:
            self._alarms.append(reactor_alarm)
            self._alarms.sort()
        # wake up the polling thread
        self._signal(self.ALARM_UPDATE)
        return reactor_alarm

    def _control_ready(self, event):
        """
        Callback when _control_r has data to read.
        For now, we don't actually use the values
        sent over the control pipe; it's really just
        to bump the thread and reevaluate timeouts or
        termination flags.
        """
        value = os.read(self._control_r, 8192)

    def _signal(self, message):
        """Send a message to the reactor, causing it
        to wake up and reevaluate its alarm list.
        """
        os.write(self._control_w, message)

    def close(self):
        """Initiate shutdown of the reactor thread.
        We don't actually wait for that here--
        this way you can close the reactor
        from within a handler itself.
        """
        self._done = True
        self._signal(self.DONE)
