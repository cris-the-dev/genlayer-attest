// Asserts which Attest app controls appear per role and status (run: node app/check-actions.mjs app/index.html).
import { readFileSync } from "node:fs";
const html = readFileSync(process.argv[2], "utf8");
const js = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
const body = js.slice(js.indexOf("function actions"), js.indexOf("async function show"));
const make = new Function("ctx", `let me = ctx.me; ${body}; return actions;`);
const H = "0xHolder", O = "0xother";
const run = (me, a = {}) => make({ me })({ holder: H, status: "ACTIVE", ...a });
const check = (name, ok) => { console.log(ok ? "ok  " : "FAIL", name); if (!ok) process.exitCode = 1; };

check("no wallet: prompt only", run(null).includes("Connect a wallet") && !run(null).includes("data-act"));
check("anyone can recheck an active attestation", run(O).includes('data-act="recheck"') && !run(O).includes('data-act="revoke"'));
check("holder can also revoke (case-insensitive)", run("0xholder").includes('data-act="revoke"'));
for (const s of ["REJECTED", "REVOKED", "SUPERSEDED", "EXPIRED"]) check(`${s.toLowerCase()}: no actions`, run(H, { status: s }) === "");
