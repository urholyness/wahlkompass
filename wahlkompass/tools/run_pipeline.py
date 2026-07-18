"""
End-to-end pipeline runner (backend -> compute -> release -> verify -> frontend).

One command reproduces the whole chain from live sources to a verified,
deployable static site:

    python tools/run_pipeline.py

Stages (each idempotent; immutable sources are cached in pipeline/data/raw/):
  1. ingest   Bundestag roll-call XLSX, abgeordnetenwatch polls, DIP Vorgaenge, dawum seats
  2. link     rebuild vote<->statement candidates (coded links.json is hand/panel-maintained)
  3. evidence assemble evidence_db.json + cells.json from coded links + T2 quotes
  4. release  aggregate (v1.2) + sign (held Ed25519 key) -> data-releases/<tag>/
  5. verify   reproduce.py byte-exact re-derivation
  6. tests    §9 bias suite + all pipeline unit tests
  7. frontend build the static site with the signed bundle + in-browser verify

Exit non-zero if verify or tests fail (a red suite blocks a release).
"""
import os
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
PY = sys.executable
PIPELINE = os.path.join(ROOT, "pipeline")
TAG = "2026.11.1-preview"


def run(desc, args, cwd, env_extra=None, check=True):
    print(f"\n=== {desc} ===", flush=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = PIPELINE + os.pathsep + ROOT
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([PY, *args], cwd=cwd, env=env)
    if check and r.returncode != 0:
        print(f"FAILED: {desc} (exit {r.returncode})", flush=True)
        sys.exit(r.returncode)
    return r.returncode


def main():
    # 1. ingest (cached; safe to re-run nightly)
    run("1a ingest: Bundestag roll-call votes", ["-m", "src.ingest.bundestag_votes"], PIPELINE)
    run("1b ingest: abgeordnetenwatch polls", ["-m", "src.ingest.abgeordnetenwatch"], PIPELINE)
    run("1c ingest: DIP Vorgaenge", ["-m", "src.ingest.dip"], PIPELINE)
    run("1d ingest: dawum seat projection", ["-m", "src.ingest.dawum"], PIPELINE)
    # 2. link candidates (recall-oriented; coded links.json maintained separately)
    run("2  link: vote<->statement candidates", ["-m", "src.ingest.link_candidates"], PIPELINE)
    # 3. T2 quote verification (re-confirm each programme quote against the PDF)
    run("3  T2: verify programme quotes vs PDF", ["-m", "src.ingest.t2_verify"], PIPELINE)
    # 4. evidence assembly (coded links + verified T2 quotes)
    run("4  evidence: assemble evidence_db + cells", ["-m", "src.ingest.build_evidence"], PIPELINE)
    # 5. release build + sign
    run("5  release: aggregate + sign", ["tools/release_builder.py"], ROOT)
    # 6. reproduce (byte-exact)
    run("6  verify: reproduce.py", ["tools/reproduce.py", f"data-releases/{TAG}"], ROOT)
    # 7. tests (bias suite + units)
    run("7  tests: §9 bias suite + units", ["-m", "unittest", "discover", "-s", "tests", "-q"], PIPELINE)
    # 8. frontend
    run("8  frontend: build static site", ["tools/build_frontend.py"], ROOT)

    print("\n" + "=" * 60)
    print("PIPELINE GREEN — deployable site at frontend/dist/")
    print("Deliver:  npx wrangler pages deploy frontend/dist --project-name wahlkompass")
    print("=" * 60)


if __name__ == "__main__":
    main()
