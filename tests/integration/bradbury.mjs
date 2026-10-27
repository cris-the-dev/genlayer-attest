// End-to-end on Testnet Bradbury (Phase 2), on the packed code that is deployed:
//
//   python deploy/shrink.py contracts/attest.py build/attest.py --pack
//   npm i genlayer-js@2.0.0-rc.2   # plus the estimateTransactionFees patch in app/README.md
//   GL_PK0=0x... GL_PK1=0x... node tests/integration/bradbury.mjs build/attest.py [contract]
//
// Every transaction carries a fee deposit from estimateTransactionFees. Uses the public
// demo page at attest.cristhedev.com, which carries GL_PK0's tag; GL_PK1 has none there.
// Prints each tx hash and its result; exits non-zero on the first failed expectation.
import { readFileSync } from "node:fs";
import { createAccount, createClient } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";

const URL = "https://attest.cristhedev.com/demo/profile.html";
const STATEMENT = "builds GenLayer intelligent contracts";
// rpc.testnet-chain.genlayer.com (the chain default) does not serve gen_call; this one serves the same chain.
const endpoint = "https://rpc-bradbury.genlayer.com";
const a0 = createAccount(process.env.GL_PK0);
const a1 = createAccount(process.env.GL_PK1);
const c0 = createClient({ chain: testnetBradbury, endpoint, account: a0 });
const c1 = createClient({ chain: testnetBradbury, endpoint, account: a1 });

const fees = async (c) => {
  const e = await c.estimateTransactionFees({});
  return { distribution: e.distribution, feeValue: e.feeValue };
};
const wait = (c, hash) => c.waitForTransactionReceipt({ hash, waitUntil: "decided", interval: 5000, retries: 240 });
const check = (ok, what) => {
  console.log(ok ? "  ok  " : "  FAIL", what);
  if (!ok) process.exit(1);
};
async function tx(c, label, address, functionName, args) {
  const hash = await c.writeContract({ address, functionName, args, value: 0n, fees: await fees(c) });
  const r = await wait(c, hash);
  console.log(`${label}: ${hash} ${r.txExecutionResultName}`);
  return r;
}
const read = (functionName, args) => c0.readContract({ address, functionName, args });

let address = process.argv[3];
if (!address) {
  const hash = await c0.deployContract({ code: readFileSync(process.argv[2], "utf8"), args: [], fees: await fees(c0) });
  const r = await wait(c0, hash);
  address = r.txDataDecoded?.contractAddress;
  console.log(`deploy: ${hash} ${r.txExecutionResultName} -> ${address}`);
  check(r.txExecutionResultName === "FINISHED_WITH_RETURN", "deployed");
}
const me = a0.address.toLowerCase();
check((await read("ownership_tag", [a0.address])) === `genlayer-attest:${me}`, "ownership_tag is lowercase address");

let r = await tx(c0, "request http", address, "request", ["web", "http://attest.cristhedev.com/x", STATEMENT, 30]);
check(r.txExecutionResultName === "FINISHED_WITH_ERROR", "plain http subject reverts");

const n = Number(await read("get_count", []));
r = await tx(c0, "request web (holder)", address, "request", ["web", URL, STATEMENT, 30]);
check(r.txExecutionResultName === "FINISHED_WITH_RETURN", "request succeeds");
const att = await read("get_attestation", [n]);
check(att.get?.("status") === "ACTIVE" || att.status === "ACTIVE", `attestation ${n} ACTIVE`);
check((await read("is_attested", [a0.address, "web"])) === true, "is_attested(holder, web)");

r = await tx(c1, "request web (other)", address, "request", ["web", URL, STATEMENT, 30]);
check(r.txExecutionResultName === "FINISHED_WITH_RETURN", "other's request is recorded");
const other = await read("get_attestation", [n + 1]);
const reason = other.get?.("reason") ?? other.reason;
check(String(reason).startsWith("ownership_tag_missing"), `attestation ${n + 1} rejected: ${reason}`);
check((await read("is_attested", [a1.address, "web"])) === false, "is_attested(other, web) is false");

r = await tx(c1, "recheck by anyone", address, "recheck", [n]);
check(r.txExecutionResultName === "FINISHED_WITH_RETURN", "recheck succeeds");
const again = await read("get_attestation", [n]);
check((again.get?.("status") ?? again.status) === "ACTIVE", "unchanged source keeps it ACTIVE");

r = await tx(c1, "revoke by other", address, "revoke", [n]);
check(r.txExecutionResultName === "FINISHED_WITH_ERROR", "only the holder can revoke");
r = await tx(c0, "revoke by holder", address, "revoke", [n]);
check(r.txExecutionResultName === "FINISHED_WITH_RETURN", "holder revokes");
check((await read("is_attested", [a0.address, "web"])) === false, "is_attested false after revoke");
console.log("contract", address);
