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
Testnet Bradbury Phase 2 (chainId 4221): [`0x0557bFe72D1007b2b2e1A4b1695EA95BBB4F223D`](https://scan.testnet-chain.genlayer.com/address/0x0557bFe72D1007b2b2e1A4b1695EA95BBB4F223D)

Bradbury was reset for Phase 2; the earlier deployment (`0xBaF5…962c`) is gone.
The contract targets GenVM v0.3 (`# v0.3.0` header, runner `py-genlayer:babwp9t3…`),
and every transaction carries a fee deposit (`estimateTransactionFees`; the unused part is refunded).

## Bradbury evidence

`node tests/integration/bradbury.mjs build/attest.py` on Testnet Bradbury (Phase 2), 2026-10-27,
against https://attest.cristhedev.com/demo/profile.html (carries GL_PK0's tag). All 16 checks passed.

| Step | Tx | Result | Checked |
|---|---|---|---|
| deploy (packed `build/attest.py`, 5.1 KB) | [`0x2184baa5…`](https://scan.testnet-chain.genlayer.com/tx/0x2184baa5f7b8c4f72e61434f0336053ebf9e4afaf736b5d20481719dc8af8386) | FINISHED_WITH_RETURN | contract `0x0557…223D` |
| `request` web, subject `http://…` | [`0x94a18ae5…`](https://scan.testnet-chain.genlayer.com/tx/0x94a18ae5fb2a85c0750ef85c4349b3e1fe037deee35b3db211afc76df9ab6f1e) | FINISHED_WITH_ERROR | plain http refused |
| `request` web by holder (GL_PK0) on the demo page | [`0xe7f16ba2…`](https://scan.testnet-chain.genlayer.com/tx/0xe7f16ba2c021bc6ad66dee670a463325c96be18d6dd853843b69962f36fa1839) | FINISHED_WITH_RETURN | attestation 0 ACTIVE; `is_attested(holder, web)` true |
| `request` web by another address (GL_PK1), same page | [`0xfc0728cf…`](https://scan.testnet-chain.genlayer.com/tx/0xfc0728cf469ee9ac7fe397706ee75c245cea693d794ded1a908d3c07abe75281) | FINISHED_WITH_RETURN | attestation 1 REJECTED `ownership_tag_missing`; `is_attested` false |
| `recheck(0)` by GL_PK1 | [`0xaa1a03d1…`](https://scan.testnet-chain.genlayer.com/tx/0xaa1a03d1e34a76d9c43e1563b70f5999c44be5b2473db2ff76c03e167a3aa4b2) | FINISHED_WITH_RETURN | unchanged source, stays ACTIVE |
| `revoke(0)` by GL_PK1 | [`0x3b19cec4…`](https://scan.testnet-chain.genlayer.com/tx/0x3b19cec4e8f78a7c7807615371d08f321f056f0b111bc3eac51f01271e882749) | FINISHED_WITH_ERROR | only the holder can revoke |
| `revoke(0)` by holder | [`0x1a97ba0f…`](https://scan.testnet-chain.genlayer.com/tx/0x1a97ba0f956672768cba3a0593226f9a177c9d37c42ef35e471104d53be76252) | FINISHED_WITH_RETURN | REVOKED; `is_attested` false |

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
- **Validators agree on the verdict and the reason code** (`supported`,
  `not_supported`, `ownership_tag_missing`, `repo_not_found`, …), not on the
  prose. `unchanged` and `supported` count as the same answer, so a validator
  whose copy of a page differs by a byte re-judges and can still agree.
- **Rechecks are cheap when nothing changed.** Each attestation stores the
  SHA-256 of the judged bytes (tag file + README for repos). If the source is
  byte-identical, the recheck keeps it active without an LLM call.
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
`deploy/shrink.py` (AST-checked, 15.8 KB → 5.1 KB packed). CI re-runs all
direct tests against the packed code.

`demo/profile.html` is the demo `web` source (served from
`attest.cristhedev.com/demo/`, `__TAG__` replaced with the demo account's tag).

## Tests (35 direct)

- **Lifecycle** — github_repo issued; rejected for a missing or foreign tag, missing tag file, missing repo, renamed repo and unsupported statement; someone else's tag does not count; domain issued without any LLM call; web page with and without the tag; input validation; recheck of unchanged bytes skips the LLM; changed source re-judged and revoked; tag removed or repo gone revokes; 503/403/429 revert and leave it active; expiry; supersede; holder revoke.
- **Consensus (validator replay)** — agrees with an honest leader; rejects a different verdict, a leader that skipped the ownership check, forged or oversized payloads; `unchanged` vs `supported` agree; errors agree only when identical; malformed LLM output reverts; statement and source are fenced.

## License

MIT
