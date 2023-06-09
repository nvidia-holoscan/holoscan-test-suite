
holoscan-test-suite provides a very simple web server that runs test scripts and
publishes the results as HTML back to the calling browser.

holoscan-test-suite-controls leverages tools in holoscan-test-suite to provide an
interactive web UI to enable various runtime behaviors on demand.  This is
useful in the context of, say, EMR or thermal characterization: you can start
with a quiet system, measure RF emissions, then gradually turn on features, and
easily observe the differences with specific functionality running.

Requirements for this interface include:

- Provide device and configuration identification sufficient for complete
  reproduction of the configuration under test.
- Provide a record of when the test was run.
- Provide evidence of test execution with a summary of pass/fail status.
- Provide a record of the stdout/stderr generated by tests for debugging.
- Provide proper configuration for use with Yocto and Bitbake.

holoscan-test-suite works by configuring a simple python flask webserver to
wrap calls to pytest.  Pytest is used to invoke specific tests, where each test
can (for example) call a bringup shell script.  The entire test passes if all
the specific tests pass.  A bringup script can exit with a nonzero exit code to
indicate a test failure.  holoscan-test-suite accumulates the pass/fail status,
standard output, and standard error for each test and generates an HTML page
with these detailed results.

In the src directory, you'll find

- bringup\_(component)\_(configuration).sh

  These shell scripts follow the design of the L4T bringup framework, and
  return a 0 exit code on successful completion.

- test\_(configuration).py

  This script adapts pytest to create test cases for each bringup script it
  plans to execute.  Any pytest-compliant test can be added here.

- (configuration)\_report.py

  This module contains an "identify()" routine that returns a multi-level map
  of name/value pairs with a complete list of the components found on the
  system.

- flask\_wrapper.py

  Serves to configure flask with all the test cases found in
  test\_(configuration).py and displays appropriate pages with the
  configuration report and test results (as appropriate).  This script takes
  two command-line parameters: the name of the module with the identify()
  routine and the name of the pytest module (without the .py suffix):

        python3 flask_wrapper (configuration)_report test_(configuration)

    The web server is configured to listen on any local network interface on
    TCP port 8765.  Press control/C to terminate this application.

- run\_(configuration).sh

  Runs flask\_wrapper with the approriate test and report scripts for the
  given configuartion.

It's expected that run\_(configuration).sh would be started on boot
from a specially configured testing boot image.

Adding a new test is easy:

- Create a new bringup\_(component)\_(configuration).sh script, per the
  L4T bringup framework guidelines.
- Add that script to test\_(configuration).py
- Kill and restart the run\_(configuration).sh script.

For systems running the Holoscan Deployment stack using
[meta-tegra-holoscan](https://github.com/nvidia-holoscan/meta-tegra-holoscan),
you can include testing by adding
`CORE_IMAGE_EXTRA_INSTALL:append = " holoscan-test-suite"` to
build/conf/local.conf (don't forget the space after the double quote:
" holoscan-test-suite").

To add holoscan-test-suite-controls, add
`CORE_IMAGE_EXTRA_INSTALL:append = " holoscan-test-suite-controls"` to
build/conf/local.conf (don't forget the space after the double quote:
" holoscan-test-suite-controls").

Then use your usual commands to build your image (e.g. bitbake.sh) and flash
your system (e.g. flash.sh).

With this, the server will start at boot; you can use your browser to run
holoscan-test-suite by going to `http://<ip>:8765`; if you've enabled
holoscan-test-suite-controls, that is accessable by `http://<ip>:8767`.  You can
observe the console for holoscan-test-suite by running the command "screen -d -r
holoscan-test-suite", which may be useful when developing new tests.  If you're
developing new tests, you may want to "systemctl stop holoscan-test-suite", then
you can directly execute "run\_(configuration).sh" in your shell.  The console
for holoscan-test-suite-controls is available by "screen -d -r
holoscan-test-suite-controls".

