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
Testnet Bradbury (chainId 4221): _not deployed yet_

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
genvm-lint check contracts/attest.py
pytest tests/direct -v                         # 35 tests
# integration, on Bradbury, against the packed code (keys in GL_PK0..2 env vars)
python deploy/shrink.py contracts/attest.py build/attest.py --pack
cd tests/integration && gltest . -v -s --network testnet_bradbury
```

Bradbury rejects deploys above ~20 KB of code; deploy the output of
`deploy/shrink.py` (AST-checked, 15.7 KB → 5.0 KB packed). CI re-runs all
direct tests against the packed code.

`demo/profile.html` is the demo `web` source (served from
`attest.cristhedev.com/demo/`, `__TAG__` replaced with the demo account's tag).

## Tests (35 direct)

- **Lifecycle** — github_repo issued; rejected for a missing or foreign tag, missing tag file, missing repo, renamed repo and unsupported statement; someone else's tag does not count; domain issued without any LLM call; web page with and without the tag; input validation; recheck of unchanged bytes skips the LLM; changed source re-judged and revoked; tag removed or repo gone revokes; 503/403/429 revert and leave it active; expiry; supersede; holder revoke.
- **Consensus (validator replay)** — agrees with an honest leader; rejects a different verdict, a leader that skipped the ownership check, forged or oversized payloads; `unchanged` vs `supported` agree; errors agree only when identical; malformed LLM output reverts; statement and source are fenced.

## License

MIT
