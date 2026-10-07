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
    'workspace.py': '9ab8dbbedad393c81012af423c86b87a75bbf894',
    'test_multi_user.py': '92d9dde50515aa1e27798b7f7d32d81cb42e962e',
    'test_checkpoint_ui.py': 'c7ecdc1cc5dd97087cb4d5b37a58014058a8ad3d',
    'test_windows_setup.py': 'd77307121f659053fa5c555724a9e6a5b797a354',
    'presentation.py': 'c825ad0d59363e87feeaf0703b3ef5b9dbe6da43',
    'accounting.py': '09b961af0846148227d7ad241e771c55f3e0e084',
    "CHAY_BOT_MACOS.command": "37fba5f9e41c39622f8be4d9409b0a0d42a6d43f",
    "REPORT.md": "d2f1abd3f5f73f86562846ce88f1d7f925c304d2",
    "calculator.py": "5682f04253213e01cacab2ae78c6498d8ed6ec43",
    "legacy_bot.py": "58c6e35192bd5dc44b383b41e893b49821a7ba79",
    "results.py": "0770083179710abad567c1b4dd3bfd37498ce140",
    "test_accounting.py": "2ee3a73f29571b63f652d9557b5728041142e21c",
    "test_bot_menu.py": "9e4c1305a963185b66d9e6adefde9cd4406dd79d",
    "test_calculator.py": "3bc7d80725d1c93c7bbab177d98315ffe4f517db",
    "test_display_debt.py": "abe67a1fa5fd5a7fd8f9dcefbc376af055a5dcfa",
    "test_safety_accounting.py": "0e6d7839ca19818a34b1603c29072b1515cbae18",
    "test_safety_parser.py": "fb73c52bfa499ece06d95a8545b5171b8ac4db08",
    "test_safety_ui.py": "411b2cba01ff29ba61e024c0f60a476f60d70dd6",
    "test_ui.py": "0eac8c2287694628f6c6e103bbac482108fe472c"
}
PROTECTED_FUNCTIONS = {'accounting.py': {'number': '55550486495fb679940eb4cb6aa8ce62640f8b66099773efdc5def35e137e6cc',
                   'checked_calculation': '69bc38129dfa77475cfd065d8724b9eaed9add8f5708ca81011188d3ccbdf96a',
                   'snapshot': 'd10e4eb3ca55e15e817ca272e492c805b2593ba931b86bc4eef6e8d9494bac49',
                   'stored_entries': '0351c55cedd9d15e2c3494ea6cf6a5d63c1140e94a4fdb26ae08ea72fdfcacf6',
                   'validate_result': '8bea5bbcbf577b04ee915d38469f76d6e354222bee75f8848d5732390bfc7f0b',
                   'validate_config': '0461b31424a44928c25f5952dca9792b94386a96e4f84478328d5475e26f2829',
                   'Ledger.query': '8d324ef6d78c1c865a780ea713cab24024f26ff4a982a0ce25d391017f853843',
                   'Ledger.profiles': '249f7e2a77c9b1a3d6889d3e7781c7101d7d57b4c5011d116109e5dc9613c678',
                   'Ledger.profile': '640ae0c8dd0b6622738a77d7a5bfde48890aec1cb18eece789ec5c543af23dbb',
                   'Ledger.create': 'e10dc70195f6b37223a5e08c1b43fa4489c86446def0d9943e63438731f52829',
                   'Ledger.configure': '7ea920e4f8acb903d464ec98dbcdb9966273dc8b24f9977e5bb89967ce01c560',
                   'Ledger.select_variant': '8238d1d2f9aaf89adcb647e0e11e637fbb0c60827ed299e44cfa40ede9e4580b',
                   'Ledger.add': '08d1d0a5d689b315f6750c35be68cb962ae33cc31dc59837520d06e13ca5f32b',
                   'Ledger.tickets': '69fef88ebe68b3019768c2e41e052912c3dd7aaa85819cb217f1c7d83be86894',
                   'Ledger.delete': '2c139d2373b28cf1d37375c50fedea85d16929a3b6875582509dd25754c2bad5',
                   'Ledger.replace': 'c0dfca74f6de28470eb1d056e1ec2954082cd5e59ca44c9be8a7f317fb3dd406',
                   'Ledger._mutate': '759627111c24bda9d8ea6d23ba399bc11cbc0b76ad9aefab4603d5982b95c1e8',
                   'totals': '028be8e5f01908234570c875928f0644412051f1d2f5c6034fa0f133672ab2be',
                   'summary': 'b4305ef796e6b6d7180ec8ab5020995923599549fb6e5d80c3a03732ec38e592'},
 'bot.py': {'today': '56680460594d463cde5952e372f75d0f26d24cdf738ac3656ad2fbb62b4a297b',
            'card': '2ac6a0ca0187fd86bafcea6e45918f879e2ebdbd9049a6c7f8fde31ba02c8db6'}}

EXPECTED = {
    "test_calculator": 67, "test_bot_menu": 5, "test_accounting": 5, "test_ui": 1,
    "test_safety_parser": 62, "test_safety_accounting": 29, "test_safety_ui": 11,
    "test_display_debt": 43, "test_windows_setup": 34, "test_checkpoint_ui": 12, "test_multi_user": 73, "test_quick_input": 32,
}
SAFETY = {"test_safety_parser", "test_safety_accounting", "test_safety_ui"}
OLD = {"test_calculator", "test_bot_menu", "test_accounting", "test_ui"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


# The owner authorized ONLY explicit closing of these two fixture connections.
# Undo exactly those import/wrapper edits before checking the ORIGINAL full-file
# blob. Any changed assertion, ticket, SQL, expected money or unrelated code
# therefore still fails the frozen-source guard (not just an assertion subset).
FIXTURE_CLOSE_PATCHES = {'test_safety_accounting.py': ("        with sqlite3.connect(path) as c:\n            c.execute('CREATE TABLE tickets(id INTEGER PRIMARY KEY, owner INTEGER NOT NULL,profile INTEGER NOT NULL,day TEXT NOT NULL,message INTEGER NOT NULL,raw TEXT NOT NULL,config TEXT NOT NULL,UNIQUE(owner,message))')\n            cfg=json.dumps(self.db.profile(1,self.pid)['config'])\n            c.execute('INSERT INTO tickets VALUES(1,1,1,?,1,?,?)',(DAY,'Đề 12=1tr5',cfg))\n", "        with closing(sqlite3.connect(path)) as c:\n            with c:\n                c.execute('CREATE TABLE tickets(id INTEGER PRIMARY KEY, owner INTEGER NOT NULL,profile INTEGER NOT NULL,day TEXT NOT NULL,message INTEGER NOT NULL,raw TEXT NOT NULL,config TEXT NOT NULL,UNIQUE(owner,message))')\n                cfg=json.dumps(self.db.profile(1,self.pid)['config'])\n                c.execute('INSERT INTO tickets VALUES(1,1,1,?,1,?,?)',(DAY,'Đề 12=1tr5',cfg))\n"), 'test_display_debt.py': ("        with sqlite3.connect(path) as c:\n            c.execute('CREATE TABLE profiles(id INTEGER PRIMARY KEY,owner INTEGER,side TEXT,name TEXT,config TEXT)')\n            c.execute('INSERT INTO profiles VALUES(1,1,?,?,?)',('Khách','Legacy',cfg))\n", "        with closing(sqlite3.connect(path)) as c:\n            with c:\n                c.execute('CREATE TABLE profiles(id INTEGER PRIMARY KEY,owner INTEGER,side TEXT,name TEXT,config TEXT)')\n                c.execute('INSERT INTO profiles VALUES(1,1,?,?,?)',('Khách','Legacy',cfg))\n")}


def original_fixture_bytes(path, data):
    if path not in FIXTURE_CLOSE_PATCHES:
        return data
    old, new = FIXTURE_CLOSE_PATCHES[path]
    text = data.decode('utf-8')
    import_line = 'from contextlib import closing\n'
    require(text.count(import_line) == 1 and text.count(new) == 1,
            'Fixture edit differs from authorized close-only patch: ' + path)
    return text.replace(import_line, '', 1).replace(new, old, 1).encode('utf-8')


def function_digest(node):
    # Python 3.12 adds empty type_params to function/class AST nodes. Remove
    # only that empty metadata so original 3.11 source hashes identically.
    # Nonempty generic declarations are never ignored by this guard.
    for child in ast.walk(node):
        if hasattr(child, 'type_params'):
            require(not child.type_params, 'Unexpected generic declaration in protected source')
            child._fields = tuple(field for field in child._fields if field != 'type_params')
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


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
        data = original_fixture_bytes(path, (ROOT / path).read_bytes())
        digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(digest == expected, f"Frozen checkpoint file changed: {path}")
    for path, expected in PROTECTED_FUNCTIONS.items():
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
        actual_functions = {}
        def collect(nodes, prefix=''):
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    actual_functions[prefix + node.name] = function_digest(node)
                elif isinstance(node, ast.ClassDef):
                    collect(node.body, node.name + '.')
        collect(tree.body)
        require(all(actual_functions.get(name) == digest for name, digest in expected.items()),
                'Protected money/storage function changed: ' + path)
    # Debt input validation is inherited semantically unchanged even though
    # its write transaction now records the real actor in the workspace layer.
    money_tree = ast.parse((ROOT / 'accounting.py').read_text(encoding='utf-8'))
    workspace_tree = ast.parse((ROOT / 'workspace.py').read_text(encoding='utf-8'))
    def method(tree, cls, name):
        return next(m for c in tree.body if isinstance(c, ast.ClassDef) and c.name == cls
                    for m in c.body if isinstance(m, ast.FunctionDef) and m.name == name)
    old_debt = method(money_tree, 'Ledger', 'set_old_balance')
    new_debt = method(workspace_tree, 'WorkspaceLedger', 'set_old_balance')
    require([ast.dump(n, include_attributes=False) for n in old_debt.body[:2]] ==
            [ast.dump(n, include_attributes=False) for n in new_debt.body[:2]],
            'Debt input/sign/Decimal semantics changed in workspace layer')
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
    require(sum(actual[m] for m in OLD) == 78 and sum(actual[m] for m in SAFETY) == 102 and len(ids) == 374,
            "Expected 78 old + 102 safety + 89 UI/debt/Windows + 73 multi-user + 32 quick input = 374")
    print("FROZEN SOURCE/TEST FILES: PASS (base " + BASE_COMMIT + ")")
    print("FIXTURE ASSERTIONS / BUSINESS DATA: PASS (original full-file blobs after close-only normalization)")
    print("DISCOVERY: OLD 78 / SAFETY 102 / CHECKPOINT 89 / MULTI USER 73 / QUICK INPUT 32 / TOTAL 374; no skips or expected failures")
    if args.results:
        log = args.results.read_text(encoding="utf-8")
        passed = re.findall(r"^\S+ \(([^)]+)\) \.\.\. ok$", log, re.M)
        require(len(passed) == 374 and set(passed) == set(ids),
                "Actual passing unittest IDs differ from the 374 discovered IDs")
        require(re.search(r"^Ran 374 tests in ", log, re.M), "Missing 374-test execution summary")
        require(re.search(r"^OK\s*$", log, re.M), "Missing clean OK summary")
        require(not re.search(r"\.\.\. (?:skipped|expected failure|unexpected success)", log),
                "Tests skipped or expected-failed during execution")
        old_pass = sum(test.split(".", 1)[0] in OLD for test in passed)
        require(old_pass == 78, f"Wrong old-test execution count: {old_pass}")
        summary = ("| Check | Result |\n|---|---|\n"
                   "| OLD TESTS | PASS 78 / FAIL 0 |\n"
                   "| SAFETY TESTS | PASS 102 / FAIL 0 |\n"
                   "| NEW UI/DEBT/WINDOWS TESTS | PASS 89 / FAIL 0 |\n"
                   "| MULTI USER TESTS | PASS 73 / FAIL 0 |\n"
                   "| QUICK INPUT TESTS | PASS 32 / FAIL 0 |\n"
                   "| TOTAL | PASS 374 / FAIL 0; skipped 0 |\n"
                   "| BUSINESS RULE CHANGED | NONE (frozen parser/tests and protected calculation/storage AST checks) |\n")
        print(summary)
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
                output.write(summary)


if __name__ == "__main__":
    main()
