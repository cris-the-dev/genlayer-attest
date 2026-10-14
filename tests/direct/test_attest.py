"""Attestation lifecycle: issue, reject, recheck, revoke, expire."""

import pytest

from tests.direct.conftest import REPO, README, domain, github, request_repo, tag, to_hex, web


def test_github_repo_issued(att, direct_vm, direct_alice):
    r = request_repo(direct_vm, att, direct_alice)
    assert r["status"] == "ACTIVE"
    a = att.get_attestation(0)
    assert a["holder"].lower() == to_hex(direct_alice).lower() and a["kind"] == "github_repo"
    assert a["expires_at"] - a["issued_at"] == 30 * 86_400 and len(a["source_sha256"]) == 64
    assert att.is_attested(to_hex(direct_alice), "github_repo") is True
    assert att.is_attested_subject(to_hex(direct_alice), "github_repo", "ACME/Widget") is True
    assert att.is_attested(to_hex(direct_alice), "domain") is False
    assert att.ownership_tag(to_hex(direct_alice)) == tag(direct_alice)


@pytest.mark.parametrize(
    "kw, code",
    [
        ({"proof": "genlayer-attest:0x000000000000000000000000000000000000dead"}, "ownership_tag_missing"),
        ({"proof_status": 404}, "ownership_tag_missing"),
        ({"repo_status": 404}, "repo_not_found"),
        ({"full_name": "someone/else"}, "repo_not_found"),
        ({"supported": False}, "not_supported"),
    ],
)
def test_github_repo_rejected(att, direct_vm, direct_alice, kw, code):
    r = request_repo(direct_vm, att, direct_alice, **kw)
    assert r["status"] == "REJECTED" and r["reason"].startswith(code)
    a = att.get_attestation(0)
    assert a["expires_at"] == 0
    assert att.is_attested(to_hex(direct_alice), "github_repo") is False
    assert att.get_holder(to_hex(direct_alice)) == [0]


def test_someone_elses_tag_does_not_count(att, direct_vm, direct_alice, direct_bob):
    # The repo carries Alice's tag; Bob cannot claim it.
    github(direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    assert att.request("github_repo", REPO, "maintains acme/widget for Acme", 30)["status"] == "REJECTED"


def test_domain_needs_no_llm(att, direct_vm, direct_alice):
    domain(direct_vm, direct_alice)  # no LLM mock: an LLM call would fail
    direct_vm.sender = direct_alice
    r = att.request("domain", "Acme.Example", "ignored for domains", 90)
    assert r["status"] == "ACTIVE"
    a = att.get_attestation(0)
    assert a["subject"] == "acme.example" and a["statement"] == "controls the domain acme.example"
    domain(direct_vm, direct_alice, body="nothing here")
    assert att.request("domain", "acme.example", "x" * 10, 90)["status"] == "REJECTED"


def test_web_page(att, direct_vm, direct_alice):
    web(direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    assert att.request("web", "https://blog.acme.example/about", "is the CTO of Acme", 30)["status"] == "ACTIVE"
    web(direct_vm, direct_alice, page="<html>I am the Acme CTO.</html>")
    r = att.request("web", "https://blog.acme.example/about", "is the CTO of Acme", 30)
    assert r["reason"].startswith("ownership_tag_missing")


@pytest.mark.parametrize(
    "kind, subject, statement, days, msg",
    [
        ("twitter", "x", "statement long enough", 30, "kind must be"),
        ("github_repo", "https://github.com/acme/widget", "statement long enough", 30, "owner/repo"),
        ("domain", "http://acme.example", "statement long enough", 30, "domain name"),
        ("web", "http://blog.acme.example/x", "statement long enough", 30, "https URL"),
        ("github_repo", REPO, "short", 30, "10-500"),
        ("github_repo", REPO, "statement long enough", 0, "1-365"),
        ("github_repo", REPO, "statement long enough", 366, "1-365"),
    ],
)
def test_request_validation(att, direct_vm, direct_alice, kind, subject, statement, days, msg):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert(msg):
        att.request(kind, subject, statement, days)


def test_recheck_unchanged_source_skips_llm(att, direct_vm, direct_alice, direct_bob):
    request_repo(direct_vm, att, direct_alice)
    github(direct_vm, direct_alice, supported=False)  # an LLM call would now say no
    direct_vm.warp("2030-01-10T10:00:00Z")
    direct_vm.sender = direct_bob  # anyone can recheck
    r = att.recheck(0)
    assert r["status"] == "ACTIVE" and r["code"] == "unchanged"
    assert att.get_attestation(0)["checks"] == 2


def test_recheck_changed_source_rejudged(att, direct_vm, direct_alice):
    request_repo(direct_vm, att, direct_alice)
    old = att.get_attestation(0)["source_sha256"]
    github(direct_vm, direct_alice, readme=README + "\nNow also used by Beta Corp.")
    assert att.recheck(0)["code"] == "supported"
    assert att.get_attestation(0)["source_sha256"] != old
    github(direct_vm, direct_alice, readme="# widget\nArchived. Acme Cloud moved away.", supported=False)
    r = att.recheck(0)
    assert r["status"] == "REVOKED" and r["reason"].startswith("not_supported")
    assert att.is_attested(to_hex(direct_alice), "github_repo") is False


@pytest.mark.parametrize("kw", [{"proof_status": 404}, {"proof": "removed"}, {"repo_status": 404}])
def test_recheck_revokes_when_ownership_gone(att, direct_vm, direct_alice, kw):
    request_repo(direct_vm, att, direct_alice)
    github(direct_vm, direct_alice, **kw)
    assert att.recheck(0)["status"] == "REVOKED"
    with direct_vm.expect_revert("not active"):
        att.recheck(0)


@pytest.mark.parametrize("status", [503, 403, 429])
def test_outage_never_revokes(att, direct_vm, direct_alice, status):
    request_repo(direct_vm, att, direct_alice)
    github(direct_vm, direct_alice, proof_status=status)
    with direct_vm.expect_revert(f"[EXTERNAL] source returned HTTP {status}"):
        att.recheck(0)
    assert att.get_attestation(0)["status"] == "ACTIVE"


def test_expiry(att, direct_vm, direct_alice):
    request_repo(direct_vm, att, direct_alice, days=1)
    direct_vm.warp("2030-01-02T10:00:01Z")
    assert att.get_attestation(0)["status"] == "EXPIRED"
    assert att.is_attested(to_hex(direct_alice), "github_repo") is False
    with direct_vm.expect_revert("not active"):
        att.recheck(0)


def test_new_request_supersedes(att, direct_vm, direct_alice):
    request_repo(direct_vm, att, direct_alice)
    request_repo(direct_vm, att, direct_alice, days=90)
    assert att.get_attestation(0)["status"] == "SUPERSEDED"
    assert att.get_attestation(1)["status"] == "ACTIVE"
    assert att.get_holder(to_hex(direct_alice)) == [0, 1]
    # A rejected re-request leaves the active one alone.
    request_repo(direct_vm, att, direct_alice, supported=False)
    assert att.get_attestation(1)["status"] == "ACTIVE"
    assert att.is_attested_subject(to_hex(direct_alice), "github_repo", REPO) is True


def test_holder_revokes(att, direct_vm, direct_alice, direct_bob):
    request_repo(direct_vm, att, direct_alice)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("not authorised"):
        att.revoke(0)
    direct_vm.sender = direct_alice
    att.revoke(0)
    assert att.get_attestation(0)["status"] == "REVOKED"
    assert att.get_attestation(0)["reason"] == "revoked by holder"
    with direct_vm.expect_revert("attestation not found"):
        att.get_attestation(5)
