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

# This program configures the python flask framework to implement a simple web
# application that wraps calls to pytest, possibly with a "-k (test)"
# filter option.  The main program configures a web server that has URLs to
# each of the tests established in the given script, and a special "/test_all"
# URL and the "/" default URL are also added.
#
# The default URL ("/") produces an HTML page with a configuration report and
# links to "/test_all" and each of the tests in the current directory.
#
# The "/test_all" URL results in running pytest on the all tests and accumulate
# the results.  An HTML page is generated that includes the configuration
# report above, a quick list of each test and it's pass/fail/skipped status,
# and detail (stdout and stderr for each test) for each executed test, sorted
# in test-name alphabetic order.
#
# Tests can be specifically marked as appropriate for IGX Orin Devkit or Clara
# AGX devkit only, by prefixing the test with
# "@pytest.mark.igx_orin_devkit_only" or "@pytest.mark.clara_agx_devkit_only":
#
#   import pytest
#   @pytest.mark.clara_agx_devkit_only
#   def test_sata_clara_agx_devkit(script):
#       assert script.run("bringup_sata_clara_agx_devkit.sh") == 0
#
# In this case, when run on an IGX Orin Devkit, this test will be skipped with an
# appropriate message supplied.
#
# To run this program, tell it how to generate a configuration report:
#
#   python3 flask_wrapper.py demo_report
#
# This tells flask_wrapper.py to load demo_report.py.  This module provides an
# "identify()" routine that returns a map of name/value pairs that describes
# the system with sufficient detail to prove repeatability with a validated
# configuration.
#
# Once the test cases are loaded, flask_wrapper sets up a web server on the
# localhost at port 8765.

import argparse
import datetime
from holoscan_test_suite.html_render import *
import flask
import importlib
import os
import pytest
import sys
import time
import yaml

REPORT_CACHE = "/tmp/holoscan-test-suite-reports"


def run_application(configuration, name):
    """Configure flask_wrapper with a server on port 8765."""
    # Get all the tests we know about.
    test_name_accumulator = TestNameAccumulator()
    pytest.main(["--collect-only"], plugins=[test_name_accumulator])
    # Create and configure the flask application.
    app = flask.Flask(name)
    app.add_url_rule(
        "/",
        view_func=lambda: index_page(configuration, test_name_accumulator),
        endpoint="/",
    )
    app.add_url_rule(
        "/test_all",
        view_func=lambda: test_all(configuration, test_name_accumulator),
        endpoint="/test_all",
    )
    # Add /(testscript) pages
    for test_script in test_name_accumulator.names():
        app.add_url_rule(
            "/%s" % test_script,
            view_func=lambda test_script=test_script: run_script(
                configuration, test_script
            ),
            endpoint=test_script,
        )
    app.add_url_rule(
        "/report",
        view_func=get_report,
        endpoint="/report",
    )
    # Allow the report to add pages
    configuration.configure_app(app)
    # Don't cache these pages on the browser side
    app.after_request(disable_cache)
    #
    return app


class TestNameAccumulator:
    """This class listens to pytest for the tests
    it finds.  Get that list of names by calling the
    names() method.
    """

    def __init__(self):
        self._names = []

    def pytest_collection_modifyitems(self, session, config, items):
        """Hooks into pytest to observe all the tests we're aware of."""
        for i in items:
            self._names.append(i.name)
        # we'll always run in a consistent order.
        self._names.sort()

    def names(self):
        """Fetch the list of test names we've found."""
        for name in self._names:
            yield name


def index_page(configuration, test_name_accumulator):
    """Generate the index page."""
    #
    now = time.time()
    timestamp = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
    # Start with the configuration report
    information = configuration.information()
    # Save it.
    configuration_report_name = timestamp.strftime(
        "configuration-report-%Y-%m-%d-%H-%M-%S.yaml"
    )
    s = yaml.dump(information, default_flow_style=False)
    os.makedirs(REPORT_CACHE, exist_ok=True)
    with open(os.path.join(REPORT_CACHE, configuration_report_name), "wt") as f:
        f.write(s)
    # Reports.
    doc = [
        header(3, "Reports"),
        rtable(
            {
                "Configuration report": Link(
                    configuration_report_name,
                    "/report?report_name=%s" % (escape(configuration_report_name),),
                ),
            }
        ),
        horizontal_rule(),
    ]
    # Actions.
    include_timestamp = {
        "onclick": 'now=new Date();this.href+="?iso_time_utc="+now.toISOString()+"&local_time="+now.toLocaleString()+" ("+Intl.DateTimeFormat().resolvedOptions().timeZone+")"'
    }
    doc.append(
        [
            header(3, "Actions"),
            ul([link("Run all tests", "test_all", attributes=include_timestamp)]),
            ul(
                [
                    link("Run %s" % s, s, attributes=include_timestamp)
                    for s in test_name_accumulator.names()
                ]
            ),
            configuration.actions(),  # This configuration may have special controls.
            horizontal_rule(),
        ]
    )
    # Configuration.
    doc.append(
        [
            header(3, "Configuration"),
            rtable(information),
            horizontal_rule(),
        ]
    )
    # Send it.
    r = render(html(body(doc)))
    return r


class HoloscanTestSuitePlugin:
    def __init__(self):
        self._start = time.time()
        self._information = {}

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        # get the test report object; this is called
        # after each test is run.
        outcome = yield
        report = outcome.get_result()
        script = item.funcargs.get("script", None)
        capsys = item.funcargs.get("capsys", None)
        #
        passed_style = {}
        failed_style = {"color": "red"}
        if (report.when == "setup") and report.skipped:
            r = {
                "passed": report.passed,
                "outcome": report.outcome,
                "skipped": report.skipped,
                "reason": call.excinfo.value.msg,
                "pytest_output": report.longreprtext,
                "stdout": "",
                "stderr": "",
            }
            self._information[item.name] = r
            return
        if report.when == "call":
            r = {
                "passed": report.passed,
                "outcome": report.outcome,
                "skipped": report.skipped,
                "duration": report.duration,
                "pytest_output": report.longreprtext,
            }
            # script._result is the output from the shell scripts.
            if script is not None:
                result = script._result
                r.update(
                    {
                        "stdout": result.stdout.decode("utf-8"),
                        "stderr": result.stderr.decode("utf-8"),
                    }
                )
            elif capsys is not None:
                outerr = capsys.readouterr()
                r.update(
                    {
                        "stdout": outerr.out,
                        "stderr": outerr.err,
                    }
                )
            else:
                r.update(
                    {
                        "stdout": "N/A",
                        "stderr": "N/A",
                    }
                )
            #
            self._information[item.name] = r
            return
        # we ignore any other reports.

    def information(self):
        return self._information


_passed_style = {}
_failed_style = {"color": "red"}


def _test_status(status):
    if status["skipped"]:
        return div("SKIPPED")
    if status["passed"]:
        return div("Passed", style=_passed_style)
    return div("FAILED", style=_failed_style)


def html_results(results):
    document = []
    passed_style = {}
    failed_style = {"color": "red"}
    output_style = {
        "margin-left": "40px",
        "background-color": "#EEEEEE",
    }
    na_style = {
        "margin-left": "40px",
    }
    # Include specific test data
    items = []
    for test_name, status in results.items():
        #
        detail = header(4, test_name, attributes={"id": test_name})
        t = [("passed", _test_status(status))]
        if "duration" in status:
            t.append(("duration", "%.2fs" % status["duration"]))
        if "reason" in status:
            t.append(("reason", status["reason"]))
        detail.append(table(t))
        pytest_output = status["pytest_output"]
        detail.append(paragraph("pytest output"))
        if len(pytest_output):
            detail.append(pre(pytest_output, style=output_style))
        else:
            detail.append(na("No pytest output generated", style=na_style))
        #
        standard_output = status["stdout"]
        detail.append(paragraph("Standard output"))
        if len(standard_output):
            detail.append(pre(standard_output, style=output_style))
        else:
            detail.append(na("No standard output captured.", style=na_style))
        #
        standard_error = status["stderr"]
        detail.append(paragraph("Standard error"))
        if len(standard_error):
            detail.append(pre(standard_error, style=output_style))
        else:
            detail.append(na("No standard error captured.", style=na_style))
        detail.append(horizontal_rule())
        items.append(detail)
    document.append(ul(items))
    return document


def _run_tests(configuration, test_names):
    def generate(args):
        now = time.time()
        timestamp = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
        # Generate the output we can
        information = configuration.information()
        information["test"]["browser_iso_time_utc"] = args["iso_time_utc"]
        information["test"]["browser_local_time"] = args["local_time"]
        # Save the configuration report.
        configuration_report_name = timestamp.strftime(
            "configuration-report-%Y-%m-%d-%H-%M-%S.yaml"
        )
        report_name = timestamp.strftime("test-report-%Y-%m-%d-%H-%M-%S.yaml")
        s = yaml.dump(information, default_flow_style=False)
        os.makedirs(REPORT_CACHE, exist_ok=True)
        with open(os.path.join(REPORT_CACHE, configuration_report_name), "wt") as f:
            f.write(s)
        #
        summary_rows = []
        for test_name in test_names:
            attributes = {"id": "status_%s" % test_name}
            summary_rows.append(
                [
                    link(test_name, url="#%s" % test_name),
                    div("UNTESTED", attributes=attributes),
                ]
            )
        document_part = [
            header(3, "Testing Summary"),
            table(summary_rows),
            horizontal_rule(),
            header(3, "Reports"),
            rtable(
                {
                    "Configuration report": Link(
                        configuration_report_name,
                        "/report?report_name=%s" % (escape(configuration_report_name),),
                    ),
                    "Test results report": Link(
                        report_name, "/report?report_name=%s" % (escape(report_name),)
                    ),
                }
            ),
            horizontal_rule(),
            header(3, "Configuration"),
            rtable(information),
            horizontal_rule(),
            header(3, "Testing Detail"),
        ]
        html_out = render([html_start(), body_start(), document_part])
        yield html_out
        #
        # Run it.
        accumulated_results = {}
        for test_name in test_names:
            # We're underway
            document_part = [
                script(
                    'document.getElementById("status_%s").innerText = "UNDERWAY"'
                    % test_name
                ),
            ]
            html_out = render(document_part)
            yield html_out
            holoscan_test_suite_plugin = HoloscanTestSuitePlugin()
            pytest_command_line = [
                "-p",
                "no:cacheprovider",
                "-k",
                test_name,
            ]
            pytest.main(
                pytest_command_line,
                plugins=[
                    holoscan_test_suite_plugin,
                ],
            )
            # Report it.
            results = holoscan_test_suite_plugin.information()
            accumulated_results.update(results)
            # YAML
            yaml_result = {
                "identification": information,
                "results": accumulated_results,
            }
            s = yaml.dump(yaml_result, default_flow_style=False)
            os.makedirs(REPORT_CACHE, exist_ok=True)
            with open(os.path.join(REPORT_CACHE, report_name), "wt") as f:
                f.write(s)
            # HTML
            document_part = [html_results(results)]
            for result_test_name, result_status in results.items():
                if result_status["skipped"]:
                    s = "SKIPPED"
                elif result_status["passed"]:
                    s = "PASSED"
                else:
                    s = "FAILED"
                document_part.append(
                    [
                        script(
                            'document.getElementById("status_%s").innerText = "%s"'
                            % (result_test_name, s)
                        )
                    ],
                )
            html_out = render(document_part)
            yield html_out
        document_part = [body_end(), html_end()]
        html_out = render(document_part)
        yield html_out

    args = flask.request.args
    return flask.Response(generate(args), mimetype="text/html")


def test_all(configuration, test_name_accumulator):
    """Runs all the tests that test_name_accumulator knows about."""
    return _run_tests(configuration, list(test_name_accumulator.names()))


def run_script(configuration, test_script):
    return _run_tests(configuration, [test_script])


def get_report():
    args = flask.request.args
    report_name = args["report_name"]
    print("REPORT_CACHE=%s report_name=%s" % (REPORT_CACHE, report_name))
    return flask.send_from_directory(REPORT_CACHE, report_name, as_attachment=True)


def disable_cache(response):
    """This hook ("app.after_request") allows us to tell
    flask to include the html header that disables the
    client browser cache.
    """
    response.cache_control.no_cache = True
    return response


def main():
    #
    parser = argparse.ArgumentParser(
        description="Run a test application with the given configuration",
    )
    parser.add_argument("configuration", help="Name of configuration module")
    parser.add_argument(
        "factory", help="Name of method that returns a Configuration object"
    )
    args = parser.parse_args()
    #
    configuration_module = importlib.import_module(args.configuration)
    factory = getattr(configuration_module, args.factory)
    configuration = factory()
    app = run_application(configuration, __name__)
    app.run(host="0.0.0.0", port=8765)
    return 0


if __name__ == "__main__":
    sys.exit(main())
