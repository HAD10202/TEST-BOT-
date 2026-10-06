"""Checkpoint guard: frozen files, exact discovery and actual unittest results."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE_COMMIT = "8369ba4dff6bbd8fc1facc75bdb189cf725e8020"
FROZEN_BLOBS = {
    ".gitignore": "ab88ce2306b97f60f025574fea9c6fc3b86663bb",
    "CHAY_BOT_MACOS.command": "37fba5f9e41c39622f8be4d9409b0a0d42a6d43f",
    "CHAY_BOT_WINDOWS.bat": "b42eefe18867f33f28ab25b421e7d753e93fe9aa",
    "README.md": "ea8c1a6b397c293b00fccb84cd7823c861914141",
    "REPORT.md": "d2f1abd3f5f73f86562846ce88f1d7f925c304d2",
    "accounting.py": "99d5e89286b5eb8fd630182a9f651673708749c9",
    "bot.py": "b6a42efcfc06171383a3acc6dc8b776424123a48",
    "calculator.py": "5682f04253213e01cacab2ae78c6498d8ed6ec43",
    "legacy_bot.py": "58c6e35192bd5dc44b383b41e893b49821a7ba79",
    "requirements.txt": "969e4d3e05a8c37c2a4de11004cd548186cdd608",
    "results.py": "0770083179710abad567c1b4dd3bfd37498ce140",
    "run.py": "0aa9eafcb599b6b845e32d0283dd298c98bc5aea",
    "test_accounting.py": "2ee3a73f29571b63f652d9557b5728041142e21c",
    "test_bot_menu.py": "9e4c1305a963185b66d9e6adefde9cd4406dd79d",
    "test_calculator.py": "3bc7d80725d1c93c7bbab177d98315ffe4f517db",
    "test_safety_accounting.py": "0e6d7839ca19818a34b1603c29072b1515cbae18",
    "test_safety_parser.py": "fb73c52bfa499ece06d95a8545b5171b8ac4db08",
    "test_safety_ui.py": "411b2cba01ff29ba61e024c0f60a476f60d70dd6",
    "test_ui.py": "0eac8c2287694628f6c6e103bbac482108fe472c"
}
EXPECTED = {
    "test_calculator": 67, "test_bot_menu": 5, "test_accounting": 5, "test_ui": 1,
    "test_safety_parser": 62, "test_safety_accounting": 29, "test_safety_ui": 11,
}
OLD = {"test_calculator", "test_bot_menu", "test_accounting", "test_ui"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path)
    args = parser.parse_args()
    os.chdir(ROOT)
    for path, expected in FROZEN_BLOBS.items():
        data = (ROOT / path).read_bytes()
        digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(digest == expected, f"Frozen checkpoint file changed: {path}")
    tests = list(flatten(unittest.defaultTestLoader.discover(str(ROOT))))
    ids = [test.id() for test in tests]
    require(len(ids) == len(set(ids)), "Duplicate discovered test IDs")
    actual = {}
    for test in tests:
        module = test.__class__.__module__
        actual[module] = actual.get(module, 0) + 1
        require(not getattr(test, "__unittest_skip__", False), f"Skipped class: {test.id()}")
        method = getattr(test, test._testMethodName)
        require(not getattr(method, "__unittest_skip__", False), f"Skipped method: {test.id()}")
        require(not getattr(method, "__unittest_expecting_failure__", False),
                f"Expected-failure test: {test.id()}")
    require(actual == EXPECTED, f"Test inventory changed: {actual}, expected {EXPECTED}")
    require(sum(actual[m] for m in OLD) == 78 and len(ids) == 180,
            "Expected 78 old + 102 new = 180")
    print("FROZEN SOURCE/TEST FILES: PASS (base " + BASE_COMMIT + ")")
    print("DISCOVERY: OLD 78 / NEW 102 / TOTAL 180; no skips or expected failures")
    if args.results:
        log = args.results.read_text(encoding="utf-8")
        passed = re.findall(r"^\S+ \(([^)]+)\) \.\.\. ok$", log, re.M)
        require(len(passed) == 180 and set(passed) == set(ids),
                "Actual passing unittest IDs differ from the 180 discovered IDs")
        require(re.search(r"^Ran 180 tests in ", log, re.M), "Missing 180-test execution summary")
        require(re.search(r"^OK\s*$", log, re.M), "Missing clean OK summary")
        require(not re.search(r"\.\.\. (?:skipped|expected failure|unexpected success)", log),
                "Tests skipped or expected-failed during execution")
        old_pass = sum(test.split(".", 1)[0] in OLD for test in passed)
        require(old_pass == 78, f"Wrong old-test execution count: {old_pass}")
        summary = ("| Check | Result |\n|---|---|\n"
                   "| OLD TESTS | PASS 78 / FAIL 0 |\n"
                   "| NEW TESTS | PASS 102 / FAIL 0 |\n"
                   "| TOTAL | PASS 180 / FAIL 0; skipped 0 |\n"
                   "| BUSINESS RULE CHANGED | NONE (frozen blob checks) |\n")
        print(summary)
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
                output.write(summary)


if __name__ == "__main__":
    main()
