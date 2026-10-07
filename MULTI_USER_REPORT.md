# Shared workspace / multi-user checkpoint

Review base: bab80cc8df7e4e4e51e1e10e9a62f316f9e11879.
Branch codex/money-safety-20261006, PR #1; no merge to main.

## Existing money behavior preserved

accounting.py, calculator.py, results.py and presentation.py are byte-for-byte
unchanged. All original 269 test files remain unchanged, including the previously
authorized explicit closing fixture patches. CI now freezes the full accounting
and presentation blobs and all baseline UI/setup test files as well as the prior
parser/test guards. The allowed bot UI/authorization functions are updated;
original card formatting and timezone helper remain guarded.

WorkspaceLedger subclasses Ledger in a new module. It delegates profile creation,
percentage/reward configuration and variant selection to the original methods
inside an authorized transaction, and calls original checked_calculation,
snapshot, validate_config and totals/matching helpers for tickets. Ticket edits
keep the old config snapshot. No number grammar, rate, payout, result matching,
rounding or stored Entry representation is changed. Debt validation/sign/Decimal
statements are checked by AST against the original Ledger implementation in CI.

## Authorization and shared state

TELEGRAM_ADMIN_ID is the implicit OWNER. authorized_users stores grants in the
same existing SQLite; owner is never removable. Only OWNER can list/grant/revoke.
Batch IDs accept ASCII positive integers that fit SQLite's signed integer range,
separated by whitespace/newline/comma. Any invalid ID rejects the whole batch
before writes. Distinct IDs are processed once; existing IDs are reported.
Revocation requires the exact XÓA QUYỀN response in the staged UI flow. Missing
IDs are reported without affecting OWNER. Grants/revokes are transaction-audited.
No real authorized IDs or tokens are committed; test IDs are synthetic fixtures.

All business queries use configured OWNER as workspace owner and the real sender
as actor. Staff see the same profiles/tickets/config/debt/totals. Their PTB
context.user_data keeps separate profile selection, drafts and confirmations.
The current date is shared in workspace_state, persisted across restarts. A date
change clears stale staged actions on another user's next interaction and warns
before saving text intended for the old date. It does not automatically roll
forward or settle a date. This checkpoint adds no day lock or payment ledger.

allowed() checks current SQLite grants for each private-chat interaction. Group
chats and ungranted users are blocked before business reads/writes. Responses
recheck authorization, including after asynchronous result fetch. Writes check
authorization again under BEGIN IMMEDIATE so revocation and writes serialize.
Staff cannot manage users, change OWNER/token or read secrets through bot menus.
Permission state persists in SQLite, not source or an environment ID list.

## Audit and concurrent storage

Existing ticket_audit and balance_audit record the actual Telegram actor for new
staff changes. workspace_audit also records owner, actor, action, UTC time, target
and old/new values for profile creation, configuration, variant, date, ticket
add/edit/delete, debt and permission changes. Historical audit rows are retained.

Telegram message IDs are scoped to the sender's private chat. Existing OWNER
message keys/unique(owner,message) protection are retained. New telegram_messages
identifies (workspace_owner, actor, actual Telegram message ID). Staff tickets use
unique negative internal tickets.message keys to avoid collisions with positive
OWNER message IDs, with the original sender/message mapping preserved. Tombstones
and mappings survive soft delete/revocation, preventing duplicate resurrection.
Entries/config snapshots and visible ticket IDs are unaffected.

Migration only creates authorization/state/audit/message mapping tables and adds
tickets.revision default 0. Existing rows, original message keys, raw, snapshots,
soft-delete markers, audits and balances are not rewritten. Initialization is
idempotent. Existing OWNER duplicates remain blocked even without a new mapping.

UI edits remember ticket revisions when Sửa tin opens. Delete captures the
revision when an ID is selected, before confirmation. A write transaction compares
revision and increments it; two stale edits/deletes cannot both succeed, even if
the first edit kept identical raw. Staff mutation APIs require a revision; OWNER's
legacy direct API retains its optional revision for compatibility, while all
Telegram OWNER/staff edits use revisions. SQLite write locking serializes actual
changes; conflicts return a reopen-and-review message rather than overwrite.

New-ticket input also compares the profile config shown to that user and warns if
another user changed %/variant. Config is checked again inside the insert
transaction. The admin must resend after seeing the new card; no amount is guessed.

## Test inventory and limits

OLD 78 + SAFETY 102 + UI/DEBT/WINDOWS 89 + MULTI USER 73 = 342 tests.
No baseline test edits, skips or expected failures. Multi-user tests cover owner,
atomic grant/revoke, invalid batches, immediate revocation, private chats, shared
workspace/date/debt/config/totals, separate sessions, real actor audit, legacy
duplicate migration, snapshot/payout equivalence and simultaneous edit/delete or
duplicate insertion. Runtime smoke uses actual PTB registered handlers and adds
batch grant, staff shared tickets, cross-chat ID collisions, staff edit/actor audit,
confirmed revoke and revoked read denial with live polling/network disabled.

Local: compile PASS, all 342 tests PASS, runtime smoke PASS. CI must be inspected
on the exact pushed HEAD for both Windows and Linux before the final report.
Telegram live and AZ24 live: NOT RUN. These synthetic result fixtures are not
production result verification. Manual double-click/Ctrl+V on the user's Windows
machine remains unverified. Backups, result immutability/day locks, long-running
load, server deployment and external DB tools/legacy writers are not validated.
Use the current bot entry point; external writers do not participate in the new
revision/actor protocol. No production-readiness declaration is made.
