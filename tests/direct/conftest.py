"""Fixtures for Attest direct-mode tests."""

import json

import pytest

DAY = 86_400
REPO = "acme/widget"
README = "# widget\n\nA tiny rate limiter. Maintained by the Acme team. Used in production by Acme Cloud."
STATEMENT = "maintains acme/widget, a rate limiter used in production by Acme Cloud"
LLM = r"verify a public claim"


def to_hex(addr) -> str:
    if hasattr(addr, "as_hex"):
        return addr.as_hex
    from genlayer.py.types import Address

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
