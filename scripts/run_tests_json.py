#!/usr/bin/env python3
"""Run unittest tests and output structured JSON results.

Usage:
    python scripts/run_tests_json.py --output test_results.json

Produces verbose text output on stderr (for CI logs) and writes
structured JSON to the specified output file.
"""

import argparse
import json
import os
import sys
import time
import traceback
import unittest
from datetime import datetime, timezone


class JSONTestResult(unittest.TestResult):
    """Captures per-test results with timing and status."""

    def __init__(self, stream, verbosity):
        super().__init__(stream, verbosity)
        self.test_results = []
        self._test_start_times = {}
        self.stream = stream
        self.verbosity = verbosity

    def startTest(self, test):
        super().startTest(test)
        self._test_start_times[test] = time.monotonic()
        if self.verbosity >= 2:
            self.stream.write(f"{test} ... ")
            self.stream.flush()

    def _record(self, test, status, message=None):
        duration = time.monotonic() - self._test_start_times.get(test, time.monotonic())
        self.test_results.append({
            "name": test._testMethodName,
            "class": test.__class__.__name__,
            "module": test.__class__.__module__,
            "description": test._testMethodDoc or "",
            "status": status,
            "duration_s": round(duration, 3),
            "message": message,
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "pass")
        if self.verbosity >= 2:
            self.stream.write("ok\n")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        msg = "".join(traceback.format_exception(*err))
        self._record(test, "fail", msg)
        if self.verbosity >= 2:
            self.stream.write("FAIL\n")

    def addError(self, test, err):
        super().addError(test, err)
        msg = "".join(traceback.format_exception(*err))
        self._record(test, "error", msg)
        if self.verbosity >= 2:
            self.stream.write("ERROR\n")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skip", reason)
        if self.verbosity >= 2:
            self.stream.write(f"skipped '{reason}'\n")


class JSONTestRunner:
    """Test runner that produces both text and JSON output."""

    def __init__(self, stream=None, verbosity=2):
        self.stream = stream or sys.stderr
        self.verbosity = verbosity

    def run(self, test):
        result = JSONTestResult(self.stream, self.verbosity)
        start_time = time.monotonic()
        test(result)
        duration = time.monotonic() - start_time

        # Print summary to stderr
        self.stream.write(f"\n{'='*70}\n")
        self.stream.write(f"Ran {result.testsRun} tests in {duration:.3f}s\n\n")

        if result.wasSuccessful():
            self.stream.write("OK")
        else:
            self.stream.write("FAILED")

        infos = []
        if result.failures:
            infos.append(f"failures={len(result.failures)}")
        if result.errors:
            infos.append(f"errors={len(result.errors)}")
        if result.skipped:
            infos.append(f"skipped={len(result.skipped)}")
        if infos:
            self.stream.write(f" ({', '.join(infos)})")
        self.stream.write("\n")

        # Print failure/error details
        for test_case, tb in result.failures:
            self.stream.write(f"\nFAIL: {test_case}\n")
            self.stream.write(f"{'-'*70}\n")
            self.stream.write(f"{tb}\n")

        for test_case, tb in result.errors:
            self.stream.write(f"\nERROR: {test_case}\n")
            self.stream.write(f"{'-'*70}\n")
            self.stream.write(f"{tb}\n")

        return result


def build_run_metadata():
    """Build run metadata from GitHub Actions environment variables."""
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "ImagingDataCommons/idc-health-monitor")
    run_id = os.environ.get("GITHUB_RUN_ID", "")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "run_id": int(run_id) if run_id else None,
        "run_url": f"{server}/{repo}/actions/runs/{run_id}" if run_id else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Run tests and output JSON results")
    parser.add_argument("--output", required=True, help="Path to write JSON results")
    parser.add_argument("--label", default=None, help="Label to tag test results (e.g., 'whitelisted')")
    parser.add_argument("tests", nargs="*", help="Specific test names to run (e.g., tests.test_dicomweb.TestDICOMwebGHC). Runs all if omitted.")
    args = parser.parse_args()

    # Load tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if args.tests:
        suite.addTests(loader.loadTestsFromNames(args.tests))
    else:
        import tests.idc_tests
        import tests.test_dicomweb
        suite.addTests(loader.loadTestsFromModule(tests.idc_tests))
        suite.addTests(loader.loadTestsFromModule(tests.test_dicomweb))

    # Run tests
    runner = JSONTestRunner(stream=sys.stderr, verbosity=2)
    result = runner.run(suite)

    # Build JSON output
    passed = len([t for t in result.test_results if t["status"] == "pass"])
    failed = len([t for t in result.test_results if t["status"] == "fail"])
    errors = len([t for t in result.test_results if t["status"] == "error"])
    skipped = len([t for t in result.test_results if t["status"] == "skip"])

    # Tag each test result with the label
    if args.label:
        for t in result.test_results:
            t["label"] = args.label

    output = {
        **build_run_metadata(),
        "label": args.label,
        "summary": {
            "total": result.testsRun,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
        },
        "tests": result.test_results,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    # Exit with failure if any tests failed
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
