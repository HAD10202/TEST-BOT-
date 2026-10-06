"""Checkpoint guard: frozen files, exact discovery and actual unittest results."""
import argparse
import ast
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
    "CHAY_BOT_MACOS.command": "37fba5f9e41c39622f8be4d9409b0a0d42a6d43f",
    "REPORT.md": "d2f1abd3f5f73f86562846ce88f1d7f925c304d2",
    "calculator.py": "5682f04253213e01cacab2ae78c6498d8ed6ec43",
    "legacy_bot.py": "58c6e35192bd5dc44b383b41e893b49821a7ba79",
    "results.py": "0770083179710abad567c1b4dd3bfd37498ce140",
    "test_accounting.py": "2ee3a73f29571b63f652d9557b5728041142e21c",
    "test_bot_menu.py": "9e4c1305a963185b66d9e6adefde9cd4406dd79d",
    "test_calculator.py": "3bc7d80725d1c93c7bbab177d98315ffe4f517db",
    "test_safety_accounting.py": "0e6d7839ca19818a34b1603c29072b1515cbae18",
    "test_safety_parser.py": "fb73c52bfa499ece06d95a8545b5171b8ac4db08",
    "test_safety_ui.py": "411b2cba01ff29ba61e024c0f60a476f60d70dd6",
    "test_ui.py": "0eac8c2287694628f6c6e103bbac482108fe472c"
}
PROTECTED_FUNCTIONS = {'accounting.py': {'number': '3f31041ea527d79049742c49252c2b636112ffd34dfd87903a1252065285ac9f',
                   'checked_calculation': '6fd0f289c19be92faac8c05521966f0516d33086206f09e78b8596974ad5fc69',
                   'snapshot': '18964f4435481a744aa40e08195c4672200875a3f5b9064285c88a350099d5e5',
                   'stored_entries': '6790b09a75e8bca5a8dc01d2ba7cd0feae6dcabc016f1a643efd338cdcd89f5d',
                   'validate_result': '1bc3b36e532cd202e53bdb74cffcb2228663e8bb2e620360dad39fcbe856e521',
                   'validate_config': '391dc82256dceba9137ef2758a1f8aa4a72421150b3ee959bdb5a5140dc3bc83',
                   'Ledger.query': '737ede89904564fe83a7d9d9daef7fdbc67fcc0987cdbf5e194bb486f399285f',
                   'Ledger.profiles': '1922741ed59be940fe1ae3c6d58a4158a48f47b44be7c2188b7c4b2dd0d42e63',
                   'Ledger.profile': '55bf4d0ff5502ae0a3b17d9c09000a4295ca6e1ad55a7c49fa6251d99220f048',
                   'Ledger.create': '67849a30d74328a6011f9ff6d48d3808de1e20934213242c11ed4280e07fceb6',
                   'Ledger.configure': 'e8279cf895cc144d3ab4b241cd2071e8733d5759b2c81de996ef41a92d031ad2',
                   'Ledger.select_variant': 'eafb608f925661408590d3f191430fb0e9e42f07c849bac128179dc9315c7cfb',
                   'Ledger.add': 'bac0266ff817a03901e1b4d36f4811bf251a06ef5507ad103db720edb774d29b',
                   'Ledger.tickets': '1b041dfc3f35807cdac4b1f991e12ab6c2e09f94d64d382ca116e7fa9ed7b05d',
                   'Ledger.delete': '704038e3f04ccbe4ff85a937b404c048bbbaf04e9288448539f4e1797157ef91',
                   'Ledger.replace': 'de1a6d011199ba7dee295eec5275f8a6fc7501ff1fbf44efc4a030145b8854e6',
                   'Ledger._mutate': '104f3d96667f43df0fbf02d572b2880504789fe49b75e78a72e13e7cb0ebbcdb',
                   'totals': 'aaaca0405dd9867c3f05f7ab83351b367554eb0135777d50a2b94a4125eb5acb',
                   'summary': '03fed1c406bf1e9b9a03e79cb72a4b42b72f6b202009b94bb246a79ed351e448'},
 'bot.py': {'clear_pending': 'caf53a7e07c2efb9d4947e949af27644459673a85990bb3fd69c02ac3d51c336',
            'allowed': '2d8107f6c917fad6f004d5e54be6545bcd8c169fd1c0664afe554123580ecd7f',
            'today': 'b2e4d176e8125e8a850414afb9b1156e3f13f78801efe21bd640353d083f4912',
            'reply': '33a1dce462229e2d982504b601245ff49df44ff9b65acb1e49b632ceaf079255',
            'save_input': '7463701555562d1c11b0e5cc31ee6ce2f101c8668f784037d0f36ed84a7d4b7c',
            'current': '4e76c8cc24b70d9ea3b0c42695925c7cbb32a20ea7d6600302561f357d7bcdaf',
            'card': 'f61735ba603cf9db3ad457f2cd09d55c932006d89220756cc4b7e4d53014516d',
            'start': '5401a1524d4c867379a7301ad16da43cc7023bcfa0614d606216afda4169b512',
            'choose': '91b0632238fac0078a9192ff04f61f1006b8d576f022a54cb4e9b1d8b379cbea'}}

EXPECTED = {
    "test_calculator": 67, "test_bot_menu": 5, "test_accounting": 5, "test_ui": 1,
    "test_safety_parser": 62, "test_safety_accounting": 29, "test_safety_ui": 11,
    "test_display_debt": 43, "test_windows_setup": 34, "test_checkpoint_ui": 12,
}
SAFETY = {"test_safety_parser", "test_safety_accounting", "test_safety_ui"}
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
    for path, expected in PROTECTED_FUNCTIONS.items():
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
        actual_functions = {}
        def collect(nodes, prefix=''):
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    actual_functions[prefix + node.name] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                elif isinstance(node, ast.ClassDef):
                    collect(node.body, node.name + '.')
        collect(tree.body)
        require(all(actual_functions.get(name) == digest for name, digest in expected.items()),
                'Protected money/storage function changed: ' + path)
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
    require(sum(actual[m] for m in OLD) == 78 and sum(actual[m] for m in SAFETY) == 102 and len(ids) == 269,
            "Expected 78 old + 102 safety + 89 approved checkpoint = 269")
    print("FROZEN SOURCE/TEST FILES: PASS (base " + BASE_COMMIT + ")")
    print("DISCOVERY: OLD 78 / SAFETY 102 / CHECKPOINT 89 / TOTAL 269; no skips or expected failures")
    if args.results:
        log = args.results.read_text(encoding="utf-8")
        passed = re.findall(r"^\S+ \(([^)]+)\) \.\.\. ok$", log, re.M)
        require(len(passed) == 269 and set(passed) == set(ids),
                "Actual passing unittest IDs differ from the 269 discovered IDs")
        require(re.search(r"^Ran 269 tests in ", log, re.M), "Missing 269-test execution summary")
        require(re.search(r"^OK\s*$", log, re.M), "Missing clean OK summary")
        require(not re.search(r"\.\.\. (?:skipped|expected failure|unexpected success)", log),
                "Tests skipped or expected-failed during execution")
        old_pass = sum(test.split(".", 1)[0] in OLD for test in passed)
        require(old_pass == 78, f"Wrong old-test execution count: {old_pass}")
        summary = ("| Check | Result |\n|---|---|\n"
                   "| OLD TESTS | PASS 78 / FAIL 0 |\n"
                   "| SAFETY TESTS | PASS 102 / FAIL 0 |\n"
                   "| NEW UI/DEBT/WINDOWS TESTS | PASS 89 / FAIL 0 |\n"
                   "| TOTAL | PASS 269 / FAIL 0; skipped 0 |\n"
                   "| BUSINESS RULE CHANGED | NONE (frozen parser/tests and protected calculation/storage AST checks) |\n")
        print(summary)
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
                output.write(summary)


if __name__ == "__main__":
    main()
