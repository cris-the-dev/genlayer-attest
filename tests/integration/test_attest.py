"""Integration test against Testnet Bradbury, on the packed code that is deployed:

    python deploy/shrink.py contracts/attest.py build/attest.py --pack
    cd tests/integration && gltest . -v -s --network testnet_bradbury   # config in this folder

Uses the public demo source at attest.cristhedev.com, which carries the tag
of the first test account; a second account has no tag there.
"""

import pytest
from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_failed, tx_execution_succeeded

URL = "https://attest.cristhedev.com/demo/profile.html"


@pytest.mark.integration
def test_request_recheck_and_guards():
    c = get_contract_factory("Attest").deploy(args=[])
    a0, a1 = get_accounts()[0].address, get_accounts()[1].address
    assert c.ownership_tag(args=[a0]).call() == f"genlayer-attest:{a0.lower()}"
    assert tx_execution_failed(c.request(args=["web", "http://attest.cristhedev.com/x", "statement long enough", 30]).transact())

    assert tx_execution_succeeded(c.request(args=["web", URL, "builds GenLayer intelligent contracts", 30]).transact())
    assert c.get_attestation(args=[0]).call()["status"] == "ACTIVE"
    assert c.is_attested(args=[a0, "web"]).call() is True

    # Same page, other account: its tag is not there.
    other = c.connect(get_accounts()[1])
    assert tx_execution_succeeded(other.request(args=["web", URL, "builds GenLayer intelligent contracts", 30]).transact())
    assert c.get_attestation(args=[1]).call()["reason"].startswith("ownership_tag_missing")
    assert c.is_attested(args=[a1, "web"]).call() is False

    assert tx_execution_succeeded(other.recheck(args=[0]).transact())
    assert c.get_attestation(args=[0]).call()["status"] == "ACTIVE"
