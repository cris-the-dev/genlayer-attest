# Attest — attestations backed by a public source, judged by consensus

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

On-chain reputation today is either self-declared ("I maintain X") or issued
by a trusted signer. **Attest** checks the claim against the public source
itself. An address says something about itself and points at a source; the
claim is accepted only if the source **belongs to the claimant** (it carries
their tag) and **supports the claim** (GenLayer validators read it and agree).
Attestations are non-transferable, expire, and anyone can recheck them: when
the source changes or the tag disappears, they are revoked.

```
holder ── puts genlayer-attest:<address> in the source (repo file, domain file or page)
holder ── request(kind, subject, statement, days) ─▶ Attest
          deterministic: source exists and carries the holder's tag?
          validators:   does the source support the statement?  ─▶ ACTIVE / REJECTED
anyone ── recheck(id): unchanged bytes stay active; tag gone or unsupported ─▶ REVOKED
other contracts ── is_attested(address, kind) / is_attested_subject(address, kind, subject)
```

## Live deployment

App: https://attest.cristhedev.com (look up any address, request, recheck, revoke; source in [`app/`](app/))  
Testnet Bradbury Phase 2 (chainId 4221): [`0xf8699aD2C9B815bC546c22ca8f3a7bff9c3AeF11`](https://scan.testnet-chain.genlayer.com/address/0xf8699aD2C9B815bC546c22ca8f3a7bff9c3AeF11)

The contract targets GenVM v0.3 (`# v0.3.0` header, runner `py-genlayer:babwp9t3…`),
and every transaction carries a fee deposit (`estimateTransactionFees`; the unused part is refunded).

This deployment (2026-10-28) carries the stricter validator: validators re-derive the source hash
and the stored reason is fixed text per code. The previous one (`0x0557…223D`) let a leader keep the
right verdict and code while supplying its own hash and note; it is no longer used by the app.

## Bradbury evidence

`node tests/integration/bradbury.mjs build/attest.py` on Testnet Bradbury (Phase 2), 2026-10-28,
against the demo page https://attest.cristhedev.com/demo/profile.html, the domain
attest.cristhedev.com and this repository (all carry GL_PK0's tag; GL_PK1's does not appear anywhere).
Every check passed in one run.

| Step | Tx | Result | Checked |
|---|---|---|---|
| deploy (packed `build/attest.py`, 5.0 KB) | [`0xaf1fca84…`](https://scan.testnet-chain.genlayer.com/tx/0xaf1fca849092fdb36b55bc345f47d1f5fe7b70810c2fb26160f72aac113943bc) | FINISHED_WITH_RETURN | contract `0xf869…AeF11` |
| `request` web, subject `http://…` | [`0x81ff4607…`](https://scan.testnet-chain.genlayer.com/tx/0x81ff460758c255c9708d51f5d6be2adbb76e7fe118a3c0dd9cc46e4a37790389) | FINISHED_WITH_ERROR | plain http refused |
| `request` web by holder (GL_PK0) on the demo page | [`0x25ceb33b…`](https://scan.testnet-chain.genlayer.com/tx/0x25ceb33b107135e559e36b0c37d3b1d24ecff2e43015e589757b6f166dbc45c2) | FINISHED_WITH_RETURN | attestation 0 ACTIVE, reason `source supports the statement` (fixed text, not model prose); `is_attested(holder, web)` true |
| `request` web by another address (GL_PK1), same page | [`0x359d3574…`](https://scan.testnet-chain.genlayer.com/tx/0x359d35748d3a9ff140a31dba9d3bb6524f92fc917fee5ff6e44a0b1b18a71108) | FINISHED_WITH_RETURN | attestation 1 REJECTED `ownership_tag_missing`; `is_attested` false |
| `recheck(0)` by GL_PK1 | [`0x6a688c1d…`](https://scan.testnet-chain.genlayer.com/tx/0x6a688c1d2c90f20f397f4cdfd2956589d78448bff0e7653913bccc0b1a8f892d) | FINISHED_WITH_RETURN | validators agreed on `unchanged` with the stored hash; stays ACTIVE |
| `revoke(0)` by GL_PK1 | [`0xd4dc9847…`](https://scan.testnet-chain.genlayer.com/tx/0xd4dc9847f57c3ab426194cf51e5a9cf186c80e8549782334aa53c7573cf63467) | FINISHED_WITH_ERROR | only the holder can revoke |
| `revoke(0)` by holder | [`0xd73aa53b…`](https://scan.testnet-chain.genlayer.com/tx/0xd73aa53bb35cb972fd90dcaba025296ac8384462c7c16f80c0d5abe1269819c9) | FINISHED_WITH_RETURN | REVOKED; `is_attested` false |
| `request` domain `attest.cristhedev.com` | [`0x44bfca67…`](https://scan.testnet-chain.genlayer.com/tx/0x44bfca6727b7281aa52733d44019bdc28ef3fe28974a23c0e45b9cb0743b8d05) | FINISHED_WITH_RETURN | attestation 2 ACTIVE (no LLM); `is_attested_subject` true |
| `request` github_repo `cris-the-dev/genlayer-attest` | [`0x19c485fc…`](https://scan.testnet-chain.genlayer.com/tx/0x19c485fc339ccf4bae2aa9bdcd745dc439a010d66b2893300cbbab3db7f0f4f9) | FINISHED_WITH_RETURN | attestation 3 ACTIVE: API returns the repo, `.genlayer-attest` holds the tag, validators judge the README; `is_attested(holder, github_repo)` true |
| `request` domain `attest-nowhere.invalid` | [`0x08283181…`](https://scan.testnet-chain.genlayer.com/tx/0x082831818559727b48a1c1e76f5804f1d39db72e4212933ed04f0982c8ab6b11) | FINISHED_WITH_ERROR | unreachable source reverts; nothing recorded |

## Kinds

| Kind | Subject | Ownership proof | Judged by validators |
|---|---|---|---|
| `github_repo` | `owner/repo` | GitHub API returns that repo, and `.genlayer-attest` in it contains the tag (only someone with write access can commit it) | the README supports the statement |
| `domain` | `example.com` | `https://example.com/.well-known/genlayer-attest.txt` contains the tag | nothing: the claim *is* control of the domain |
| `web` | an `https` URL | the page contains the tag | the page supports the statement |

The tag is `genlayer-attest:<address, lowercase>` (`ownership_tag(address)`
returns it). Someone else's tag in the same source does not count, so a page
or repo cannot be claimed by a stranger.

## Consensus design

- **Deterministic gates first.** Repo existence, the tag and the domain file
  are checked in code; the LLM is only asked "does this source support this
  statement" and only after ownership is proven. A leader that skips the
  ownership check is rejected by every validator that does it.
- **Validators re-derive everything that is stored.** The leader's result is
  exactly `{ok, code, sha256}`, and a validator accepts it only if its own
  check produced the same three values: the verdict, the reason code
  (`supported`, `not_supported`, `unchanged`, `ownership_tag_missing`,
  `repo_not_found`, …) and the SHA-256 of the bytes it fetched itself. A
  leader cannot keep the right verdict and code while planting another hash
  (e.g. one of a README it plans to publish later), and any extra field is
  rejected.
- **No leader prose in state.** The model's one-sentence reason is not
  stored. `reason` is fixed text for the agreed code (`source supports the
  statement`, `not_supported: source does not support the statement`, …), so
  nothing on-chain is presented as validator-agreed unless validators
  derived it.
- **Rechecks are cheap when nothing changed.** Each attestation stores the
  SHA-256 of the judged bytes (tag file + README for repos). If the source is
  byte-identical, the recheck keeps it active without an LLM call. Validators
  verify the shortcut: `unchanged` is only reachable when the hash they
  computed equals the stored one, so a leader cannot claim it for a changed
  source or with a different hash. Trade-off: a source that differs per
  request (dynamic bytes) cannot reach agreement; GitHub raw files and static
  pages are byte-stable.
- **An outage never revokes.** 404/410 means the source is gone (the tag is
  missing → rejected or revoked). Any other failure — timeout, 5xx, 403, 429
  — reverts with `[EXTERNAL]`, so a GitHub rate limit cannot strip anyone's
  attestation. Validators agree on an error only if they see the same one.
- **Prompt injection.** The statement and the source are fenced between
  `<<<` and `>>>`, markers inside them are neutralised, and the prompt says
  the fenced text is data. Covered by a test. Truncated sources say so, and
  the prompt asks for `false` if the missing part could decide it.

## Rules that need no LLM

- One active attestation per holder, kind and subject: a new accepted one
  supersedes the old; a rejected re-request leaves the active one alone.
- `valid_days` 1–365. Expired attestations read as `EXPIRED` and cannot be
  rechecked. The holder can revoke at any time.
- Nothing moves value: no fees, no payouts, nothing to reconcile.

## API

| Method | Who | Notes |
|---|---|---|
| `request(kind, subject, statement, valid_days)` | holder | consensus check; stores ACTIVE or REJECTED with a reason |
| `recheck(id)` | anyone | active only; may revoke |
| `revoke(id)` | holder | |
| `is_attested(holder, kind)`, `is_attested_subject(holder, kind, subject)` | view | for other contracts |
| `get_attestation(id)`, `get_holder(holder)`, `get_count()`, `ownership_tag(holder)` | view | |

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
genvm-lint check contracts/attest.py           # also caches the v0.3 runner bundle
pytest tests/direct -v                         # 35 tests
# end-to-end on Bradbury Phase 2, against the packed code (keys in GL_PK0, GL_PK1)
python deploy/shrink.py contracts/attest.py build/attest.py --pack
npm i genlayer-js@2.0.0-rc.2                   # plus the fee-estimate patch in app/README.md
node tests/integration/bradbury.mjs build/attest.py
```

`genlayer-test` 0.29 drives only the pre-v0.3 SDK; `tests/direct/conftest.py`
bridges its direct mode to the runner the contract header names (taken from
the `genvm-lint` cache). Its network mode still targets the Phase 1 contracts,
so the end-to-end run uses `genlayer-js` instead.

Bradbury rejects deploys above ~20 KB of code; deploy the output of
`deploy/shrink.py` (AST-checked, 16.1 KB → 5.0 KB packed). CI re-runs all
direct tests against the packed code.

`demo/profile.html` is the demo `web` source (served from
`attest.cristhedev.com/demo/`, `__TAG__` replaced with the demo account's tag).

## Tests (38 direct)

- **Lifecycle** — github_repo issued; rejected for a missing or foreign tag, missing tag file, missing repo, renamed repo and unsupported statement; someone else's tag does not count; domain issued without any LLM call; web page with and without the tag; input validation; recheck of unchanged bytes skips the LLM; changed source re-judged and revoked; tag removed or repo gone revokes; 503/403/429 revert and leave it active; expiry; supersede; holder revoke.
- **Consensus (validator replay)** — agrees with an honest leader; rejects a different verdict, a leader that skipped the ownership check, forged payloads or extra fields; correct verdict and code with a forged future hash (request, recheck after a change, and the `unchanged` shortcut); correct verdict and code with a plausible-length forged note; `unchanged` claimed for a changed source; stored reason is fixed text; errors agree only when identical; malformed LLM output reverts; statement and source are fenced.

## License

MIT
