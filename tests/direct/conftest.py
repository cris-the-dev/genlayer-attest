"""Fixtures for Attest direct-mode tests."""

import json

import pytest

DAY = 86_400
REPO = "acme/widget"
README = "# widget\n\nA tiny rate limiter. Maintained by the Acme team. Used in production by Acme Cloud."
STATEMENT = "maintains acme/widget, a rate limiter used in production by Acme Cloud"
LLM = r"verify a public claim"

# gltest 0.29 targets the pre-v0.3 SDK (`genlayer.py`, `genlayer.gl`). Bridge it to the
# v0.3 runner this contract declares: alias the moved modules, and replace the four
# hooks that reach into removed internals (storage allocation, run_nondet, message, validator).
import os
import sys
import types

import gltest.direct.loader as _loader
import gltest.direct.sdk_loader as _sdk
from gltest.direct.vm import VMContext

def _v03_runner():
    """Extract the runner the contract header names (via genvm-lint's bundle cache) into
    gltest's cache layout; returns the runner's cloudpickle source dir."""
    from pathlib import Path

    from genvm_linter.validate import artifacts as A

    runner = _sdk.parse_contract_header(Path(__file__).parents[2] / "contracts/attest.py")["py-genlayer"]
    version = A.resolve_version()
    bundle = A.download_artifacts(version)
    rdir = A.extract_runner(bundle, "py-genlayer", runner)
    deps = A.parse_runner_manifest(rdir)
    A.extract_runner(bundle, "py-lib-genlayer-std", deps["py-lib-genlayer-std"])
    pickle_dir = A.extract_runner(bundle, "py-lib-cloudpickle", deps["py-lib-cloudpickle"])
    tag = "glint-" + version.rsplit("-v", 1)[-1]
    (_sdk.CACHE_DIR / "extracted").mkdir(parents=True, exist_ok=True)
    for link, target in ((_sdk.CACHE_DIR / f"genvm-universal-{tag}.tar.xz", bundle), (_sdk.CACHE_DIR / "extracted" / tag, rdir.parents[1])):
        if not link.exists():
            link.symlink_to(target)
    os.environ.setdefault("GENVM_VERSION", tag)
    return pickle_dir / "src"

# run_nondet pickles its blocks; the v0.3 runner ships cloudpickle as its own library.
sys.path.append(str(_v03_runner()))

_setup_paths = _sdk.setup_sdk_paths

def _setup_and_alias(*a, **kw):
    added = _setup_paths(*a, **kw)
    import genlayer.calldata
    import genlayer.types

    py = types.ModuleType("genlayer.py")
    py.calldata, py.types = genlayer.calldata, genlayer.types
    sys.modules.update({"genlayer.py": py, "genlayer.py.calldata": py.calldata, "genlayer.py.types": py.types})
    return added

_sdk.setup_sdk_paths = _setup_and_alias

def _allocate(cls, vm, *args, **kwargs):
    from genlayer.storage import ROOT_SLOT_ID
    from genlayer.storage._internal.generate import ORIGINAL_INIT_ATTR, _BuilderCtx, _storage_build

    td = _storage_build(_BuilderCtx.empty(), cls)
    instance = td.get(vm._storage.get_store_slot(ROOT_SLOT_ID), 0)
    init = getattr(getattr(td, "cls", cls), "__init__")
    getattr(init, ORIGINAL_INIT_ATTR, init)(instance, *args, **kwargs)
    return instance

def _patch_run_nondet():
    import genlayer.vm as gl_vm
    from genlayer.types import Lazy
    from gltest.direct import wasi_mock

    def run_nondet(leader_fn, validator_fn, /, **_):
        vm = wasi_mock.get_vm()
        vm._in_nondet = True
        try:
            result = leader_fn()
        finally:
            vm._in_nondet = False
        vm._captured_validators.append((result, leader_fn, validator_fn))
        return result

    run_nondet.lazy = lambda l, v, /, **kw: Lazy(lambda: run_nondet(l, v, **kw))
    gl_vm.run_nondet = run_nondet

def _refresh_message(self):
    msg = sys.modules.get("genlayer.message")
    if msg is None:
        return
    from genlayer.types import Address

    a = lambda x: Address(x) if isinstance(x, bytes) else x
    upd = {"sender_address": a(self.sender), "origin_address": a(self.origin), "datetime": self._datetime, "value": self._value}
    msg.raw.update(upd)
    vars(msg).update(upd)

_run_validator = VMContext.run_validator

def _validator(self, *, leader_result=_loader.__dict__.get("_sentinel", ...), leader_error=None, index=-1):
    import genlayer.vm as gl_vm

    stored, _, validator_fn = self._captured_validators[index]
    if leader_error is not None:
        return validator_fn(gl_vm.UserError(str(leader_error)))
    return validator_fn(gl_vm.Return(stored if leader_result is ... else leader_result))

import json as _json

from gltest.direct import wasi_mock as _wasi

_llm = _wasi._handle_llm_request

def _llm_text(vm, data):
    # v0.3 exec_prompt parses JSON itself and expects the raw model text.
    r = _llm(vm, data)
    if isinstance(r, dict) and "ok" in r and not isinstance(r["ok"], str):
        return {"ok": _json.dumps(r["ok"])}
    return r

_wasi._handle_llm_request = _llm_text
_loader._allocate_contract = _allocate
_loader._patch_run_nondet_for_direct_mode = _patch_run_nondet
VMContext._refresh_gl_message = _refresh_message
VMContext.run_validator = _validator

def to_hex(addr) -> str:
    if hasattr(addr, "as_hex"):
        return addr.as_hex
    from genlayer.types import Address

    return Address(addr).as_hex


def tag(addr) -> str:
    return f"genlayer-attest:{to_hex(addr).lower()}"


@pytest.fixture
def att(direct_vm, direct_deploy):
    direct_vm.warp("2030-01-01T10:00:00Z")
    return direct_deploy("contracts/attest.py")


def github(vm, holder, *, repo_status=200, full_name=REPO, proof=None, readme=README, supported=True, proof_status=200):
    vm.clear_mocks()
    body = json.dumps({"full_name": full_name, "description": "rate limiter"}) if repo_status == 200 else ""
    vm.mock_web(r"api\.github\.com/repos/", {"status": repo_status, "body": body})
    vm.mock_web(r"/HEAD/\.genlayer-attest", {"status": proof_status, "body": tag(holder) if proof is None else proof})
    vm.mock_web(r"/HEAD/README\.md", {"status": 200, "body": readme})
    vm.mock_llm(LLM, json.dumps({"supported": supported, "reason": "README says so." if supported else "Not in README."}))


def domain(vm, holder, *, status=200, body=None):
    vm.clear_mocks()
    vm.mock_web(r"well-known/genlayer-attest\.txt", {"status": status, "body": tag(holder) if body is None else body})


def web(vm, holder, *, page=None, supported=True, status=200):
    vm.clear_mocks()
    vm.mock_web(r"blog\.acme\.example", {"status": status, "body": f"<html><p>I am the Acme CTO.</p><p>{tag(holder)}</p></html>" if page is None else page})
    vm.mock_llm(LLM, json.dumps({"supported": supported, "reason": "ok" if supported else "no"}))


def request_repo(vm, c, who, days=30, statement=STATEMENT, **kw):
    github(vm, who, **kw)
    vm.sender = who
    return c.request("github_repo", REPO, statement, days)
