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
against the demo page https://attest.cristhedev.com/demo/profile.html, the domain
attest.cristhedev.com and this repository (all carry GL_PK0's tag; GL_PK1's does not appear anywhere).
Every check passed. The run was finished in parts: after the github_repo leader timeouts below, that step and the unreachable-source step were sent again on their own.

| Step | Tx | Result | Checked |
|---|---|---|---|
| deploy (packed `build/attest.py`, 5.1 KB) | [`0x2184baa5…`](https://scan.testnet-chain.genlayer.com/tx/0x2184baa5f7b8c4f72e61434f0336053ebf9e4afaf736b5d20481719dc8af8386) | FINISHED_WITH_RETURN | contract `0x0557…223D` |
| `request` web, subject `http://…` | [`0xa4e94e1e…`](https://scan.testnet-chain.genlayer.com/tx/0xa4e94e1e0b044db32e92e1a2bacdbca3dc329ff3651322c01bfbfa8d5f6d6603) | FINISHED_WITH_ERROR | plain http refused |
| `request` web by holder (GL_PK0) on the demo page | [`0x3dbd3171…`](https://scan.testnet-chain.genlayer.com/tx/0x3dbd3171927a5d9081693d8b796dfcf2793b7b4122fc2fb2987ef835ad6245a2) | FINISHED_WITH_RETURN | attestation 3 ACTIVE, the earlier one SUPERSEDED; `is_attested(holder, web)` true |
| `request` web by another address (GL_PK1), same page | [`0x26846ecb…`](https://scan.testnet-chain.genlayer.com/tx/0x26846ecb424298827776f61a1cccc260d4ae1e57948837da82c34f474e380c8d) | FINISHED_WITH_RETURN | attestation 4 REJECTED `ownership_tag_missing`; `is_attested` false |
| `recheck(3)` by GL_PK1 | [`0x8f58f06a…`](https://scan.testnet-chain.genlayer.com/tx/0x8f58f06af18fe89cbadad2b8fc2e8a2dd2218e5711403bee89d5a93ad2a7c00f) | FINISHED_WITH_RETURN | unchanged source, stays ACTIVE |
| `revoke(3)` by GL_PK1 | [`0x4e06faad…`](https://scan.testnet-chain.genlayer.com/tx/0x4e06faadd58c8d6152fb23a1c6f95dc6e47d844c094c468e604da46b282a34e5) | FINISHED_WITH_ERROR | only the holder can revoke |
| `revoke(3)` by holder | [`0xd40d237d…`](https://scan.testnet-chain.genlayer.com/tx/0xd40d237d168b358a90a204a6bd422ac0cf04dfdf5d08b996d4c7fc8853edb30d) | FINISHED_WITH_RETURN | REVOKED; `is_attested` false |
| `request` domain `attest.cristhedev.com` | [`0xf166c840…`](https://scan.testnet-chain.genlayer.com/tx/0xf166c84087031537d2284dbb1a6d4abe26baa703fddbbba602dda1fdae57691e) | FINISHED_WITH_RETURN | attestation 5 ACTIVE (no LLM); `is_attested_subject` true |
| `request` github_repo `cris-the-dev/genlayer-attest` | [`0x84106f75…`](https://scan.testnet-chain.genlayer.com/tx/0x84106f755740301d7a86d04333fc68c4130fef95f043f72c8d987554ea37818b) | FINISHED_WITH_RETURN | attestation 9 ACTIVE: API returns the repo, `.genlayer-attest` holds the tag, validators judge the README; `is_attested(holder, github_repo)` true |
| `request` domain `attest-nowhere.invalid` | [`0xe6765ffb…`](https://scan.testnet-chain.genlayer.com/tx/0xe6765ffb70c17bc1ca8cae61a83329f1da9ac05c1a32a1a12f6056c9410bc5f1) | FINISHED_WITH_ERROR | unreachable source reverts; nothing recorded |

The first two github_repo requests ended `LEADER_TIMEOUT` with no votes (`0x39dca77d…`, `0x93f5954e…`);
nothing was recorded, and the script now sends a call again after a leader timeout. Attestations 6–8
were one-off diagnostics while chasing that timeout, revoked by the holder afterwards.

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
