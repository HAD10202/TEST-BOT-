# Display / debt / Windows checkpoint

Review base: `4a0eced70a869f4ee7a0bafc6594c9ed71343b56`.
Branch: `codex/money-safety-20261006`; PR #1 remains unmerged.

## Scope and behavior

Existing parser and business calculation rules changed: **NONE**.
`calculator.py`, `results.py`, and all seven original test files are unchanged.
Existing accounting totals, matching, money validation, ticket snapshot, duplicate
protection, edit, soft delete and audit methods are unchanged. CI retains their
original AST digests in addition to original parser/test blob hashes. Only the
profile opening-balance schema/method is added to accounting.

New `presentation.py` supplies the Telegram views. The old `accounting.summary`
API remains unchanged for compatibility; Telegram Xem tổng and /tong use the new
renderer. Both views read `stored_entries(row)`, never calculate(raw). Summary
only lists categories with goods > 0. Display cuts round HALF_UP to whole k;
original Decimal cuts remain in the balance. Winning X3/AC show base, factor and
actual payout, while the total uses actual payout. Different snapshotted factors
are kept distinct. A displayed reward mismatch rejects settlement.

Sổ vé replaces the menu label Danh sách tin; an old keyboard message still opens
the new book. Phone-friendly vertical blocks retain ID and six goods columns.
X2 factor belongs to that ticket's config snapshot. Raw remains in database and
audit and is only shown after Xem raw + an active ID in the selected owner,
profile and date. Deleted tickets do not appear.

Nợ cũ is TEXT holding signed Decimal, default 0. THU is positive from the admin's
perspective and TRẢ negative for either side. Setting it replaces the old value;
it does not accumulate and does not edit a ticket. A transaction verifies owner
and records old/new amounts, actor and UTC time in `balance_audit`. Existing DB
migration preserves old data. Summary adds the exact daily admin balance to this
opening balance, then rounds once. Exact components are shown on separate lines
to avoid suggesting arithmetic using independently rounded screen values.
This is a profile opening balance, not a daily settlement/payment ledger; it
persists until the admin replaces/resets it. Results must still match the date
before a daily total is settled.

## Windows setup and credentials

CHAY_BOT_WINDOWS.bat checks Python 3.11+, prepares/uses .venv, verifies PTB 22.5,
tzdata and the existing Vietnam timezone, installs requirements only if needed,
and runs the launcher. First launch uses normal input (Ctrl+V, no getpass), then
saves a local file. Subsequent launches read it without prompting. The change
launcher CAI_DAT_BOT_WINDOWS.bat replaces both token and Admin ID without needing
to locate APPDATA. Token setup does not contact Telegram; the basic format check
cannot prove BotFather has issued or retained that token.

Windows credentials are outside source at `%APPDATA%\TEST-BOT\secrets.env`.
Atomic replace preserves old credentials on write failure; POSIX mode 600 is
used where meaningful. Windows permissions inherit the user's APPDATA ACL; this
is local plaintext, not encrypted storage. It is not committed or packaged.
The launcher can show the token during input as authorized for usable pasting,
but does not print it again or log it. Control characters (including \x16),
newlines and non-ASCII token characters are rejected before constructing the
Telegram client. Errors are generic; log filters redact token URLs and suppress
potential credential-bearing exception tracebacks. No real token used in tests.

BOT ĐANG CHẠY is printed only after real Application initialization succeeds.
Invalid-token and network failures show a short instruction instead of a
traceback. Importing run.py is passive; the runtime harness explicitly invokes
its main with polling mocked. No manual environment setup is needed for normal
Windows use; a complete environment pair remains supported for deployment/CI,
and a partial environment pair is rejected rather than mixed with local data.

## Verification inventory

- OLD: **78** unchanged tests.
- SAFETY: **102** unchanged tests.
- NEW: **89** tests (43 display/debt; 34 local setup; 12 actual UI handlers).
- TOTAL: **269** tests; zero skips or expected failures.
- compileall, frozen parser/tests, protected accounting/storage functions and
  actual passing test-ID inventory are checked.
- CI runs Python 3.11 on both ubuntu-latest and windows-latest. .gitattributes
  preserves source/test LF bytes for the frozen checks and native BAT endings.
- Runtime smoke imports real PTB and bot, builds real handler registration,
  and tests B confirmation, duplicate, snapshots, edit and soft delete offline.
- Timezone test disables the system timezone search to prove tzdata fallback.

Local verification: COMPILE PASS; OLD 78/78; SAFETY 102/102; NEW 89/89; TOTAL
269/269; runtime smoke PASS. GitHub Actions result must be read from the exact
pushed HEAD before final approval; a local pass is not a CI claim.

## Limits and remaining risks

Telegram live polling: **NOT RUN**. AZ24 live: **NOT RUN**. Offline lottery
fixtures verify rendering/matching consistency only, not production results.
Human double-click/Ctrl+V behavior on the user's particular Windows console:
**NOT RUN**; Windows CI tests setup logic, dependencies and timezone.
SOCKS/proxy behavior and machine-specific antivirus/Python installation issues
are not verified. Old unresolved parser/business conflicts remain as in REPORT:
Dàn 48 reject, cặp 88 current behavior, whole-message rejection for partials.
Day locks/unlocks, automatic debt carry/payments and backups are not added.

No known money regression found in this checkpoint's tests. This is review
readiness evidence, not a declaration of production safety. **NOT READY FOR
PRODUCTION** pending real environment/result verification and business review.
No main merge is authorized or performed.
