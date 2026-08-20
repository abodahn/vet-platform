/*
 * Prove static/tools/codes/index.html computes exactly what models/licensing.py does.
 *
 * WHY THIS EXISTS
 *
 * The same algorithm is written twice - once in Python for the laptop, once in
 * JavaScript for the phone. If they ever drift, the failure is silent and
 * expensive: you read a code to a clinic, they type it, it is refused, and
 * neither of you can tell which side is wrong. The clinic concludes the product
 * is broken.
 *
 * This does NOT reimplement the algorithm. It reads the functions out of the
 * real HTML file and runs those, so it tests the code that actually ships.
 *
 *     node scripts/verify_phone_tool.js
 *
 * It compares against vectors produced by the Python; regenerate them with
 *     python scripts/verify_phone_tool.py
 */
const fs = require("fs");
const path = require("path");

const HTML = path.join(__dirname, "..", "static", "tools", "codes", "index.html");
const VECTORS = path.join(__dirname, "license_vectors.json");

// Pull the crypto functions out of the shipped page rather than copying them.
const src = fs.readFileSync(HTML, "utf8");
const wanted = ["hmac", "hex", "clinicSecret", "digits", "makeCode", "plusYears"];
const bodies = [];
for (const name of wanted) {
  const re = new RegExp(
    "(?:^|\\n)(?:async\\s+)?(?:function\\s+" + name +
    "\\s*\\([\\s\\S]*?\\n\\}|const\\s+" + name + "\\s*=[^;]+;)", "m");
  const m = src.match(re);
  if (!m) {
    console.error("FAIL: could not find %s() in static/tools/codes/index.html", name);
    process.exit(1);
  }
  bodies.push(m[0]);
}

const enc = new TextEncoder();
const run = new Function("enc", "crypto",
  bodies.join("\n") + "\nreturn {makeCode, clinicSecret, digits, plusYears};");
const F = run(enc, globalThis.crypto);

(async () => {
  if (!fs.existsSync(VECTORS)) {
    console.error("No vectors file. Run:  python scripts/verify_phone_tool.py");
    process.exit(1);
  }
  const vectors = JSON.parse(fs.readFileSync(VECTORS, "utf8"));

  let bad = 0;
  for (const v of vectors.codes) {
    const [y, m] = v.expiry.split("-").map(Number);
    const got = await F.makeCode(v.master, v.clinic, v.machine, new Date(y, m, 0));
    const ok = got === v.code;
    if (!ok) bad++;
    console.log("  %s  clinic=%s machine=%s exp=%s  py=%s js=%s",
                ok ? "ok  " : "FAIL", v.clinic, v.machine, v.expiry, v.code, got);
  }

  // The derived secret must match too, or a clinic's .env holds the wrong key.
  for (const v of vectors.secrets) {
    const got = await F.clinicSecret(v.master, v.clinic);
    const ok = got === v.secret;
    if (!ok) bad++;
    console.log("  %s  derive(%s)  %s", ok ? "ok  " : "FAIL", v.clinic,
                ok ? "matches" : "py=" + v.secret.slice(0,16) + " js=" + got.slice(0,16));
  }

  // And "1 year from today" must land on the same day on both sides.
  const jsY1 = F.plusYears(1);
  const jsIso = jsY1.getFullYear() + "-" +
                String(jsY1.getMonth()+1).padStart(2,"0") + "-" +
                String(jsY1.getDate()).padStart(2,"0");
  const ok = jsIso === vectors.plus_one_year;
  if (!ok) bad++;
  console.log("  %s  +1 year  py=%s js=%s",
              ok ? "ok  " : "FAIL", vectors.plus_one_year, jsIso);

  console.log("");
  if (bad) {
    console.error("%d MISMATCH(ES). The phone would issue codes the app rejects.", bad);
    process.exit(1);
  }
  console.log("All match. The phone and the laptop issue identical codes.");
})();
