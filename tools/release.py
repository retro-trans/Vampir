"""Publish a verified Vampir release with the shared Retro Trans release builder.

Install the shared tool once (Python 3.8+):
    python -m pip install git+https://github.com/retro-trans/retro-trans-tools.git@v0.5.18
Usage: python tools/release.py 0.6.0 --config ../Vampir-release/release-local.json
Use --dry to inspect the intended release without building or publishing.

The private configuration (see docs/STANDARD_RELEASES.md) names the original Track 1 .bin and
the built English Track 1 for each patch; the patch covers Track 1 only, Track 2 and the CUE
sheet are unchanged.  Release notes come from docs/release-notes/vX.Y.Z.md.  The helper builds
and round-trips every patch, adds the SRW-Z style text assets (README-vX.Y.Z.txt with source and
output hashes, CHANGELOG-vX.Y.Z.txt, SHA1SUMS-vX.Y.Z.txt, SHA256SUMS-vX.Y.Z.txt), uploads
everything to a draft release, checks the uploaded assets, and only then publishes.  It never
overwrites assets.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import datetime
import hashlib
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent / "Vampir-release"


def run(command, check=True):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


def _hash(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


NL = "\n"


def release_docs(directory, tag, date=None):
    """Write the SRW-Z style text assets into the release directory; return the release notes."""
    directory = Path(directory)
    notes = (ROOT / "docs" / "release-notes" / (tag + ".md")).read_text(encoding="utf-8").strip() + NL
    manifest = json.loads((directory / "BUILD-MANIFEST.json").read_text(encoding="utf-8"))
    date = date or datetime.date.today().isoformat()
    blocks = []
    for p in manifest["patches"]:
        blocks.append(NL.join([p["patch"], "Source version: " + p["source_version"],
                               "Source size: %d" % p["source_bytes"], "Source SHA256: " + p["source_sha256"],
                               "Output size: %d" % p["target_bytes"], "Output SHA256: " + p["target_sha256"]]))
    readme = NL.join(["Vampir English " + tag, "Japanese edition (SLPS-01932)", "Release date: " + date + ".",
                      "", notes, "SOURCE AND OUTPUT HASHES", "", (NL + NL).join(blocks), ""])
    previous = sorted({p["source_version"] for p in manifest["patches"] if p["source_version"] != "original"})
    subtitle = "Changes since published v" + previous[-1] if previous else "First public release"
    # changelog: from the first "### What" section after Apply up to "### What's included"
    start = notes.index("### What", notes.index("### Apply") + 1)
    body = notes[start:notes.index("### What's included")]
    lines = [l for l in body.splitlines() if not l.startswith("### ")]
    changelog = NL.join(["Vampir English " + tag, subtitle, "", NL.join(lines).strip(), ""])
    (directory / ("README-" + tag + ".txt")).write_text(readme, encoding="utf-8")
    (directory / ("CHANGELOG-" + tag + ".txt")).write_text(changelog, encoding="utf-8")
    sha1 = directory / ("SHA1SUMS-" + tag + ".txt")
    sha256 = directory / ("SHA256SUMS-" + tag + ".txt")
    files = sorted(p for p in directory.iterdir() if p.is_file() and p not in (sha1, sha256))
    sha1.write_text("".join(_hash(p, "sha1") + "  " + p.name + NL for p in files), encoding="utf-8")
    files = sorted(p for p in directory.iterdir() if p.is_file() and p != sha256)
    sha256.write_text("".join(_hash(p, "sha256") + "  " + p.name + NL for p in files), encoding="utf-8")
    return notes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--repo", default="retro-trans/Vampir")
    parser.add_argument("--config", type=Path, default=WORK / "release-local.json")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    version, tag = args.version.lstrip("v"), "v" + args.version.lstrip("v")
    if args.dry:
        print("Would build and round-trip every patch in", args.config)
        print("Would publish immutable release", args.repo, tag, "with notes from docs/release-notes/" + tag + ".md")
        return 0
    from retro_trans.release import build_release, validate_directory
    from retro_trans.core import sha256_file
    dirty = run(["git", "status", "--porcelain"]).stdout.strip()
    if dirty:
        raise RuntimeError("Commit your source changes before cutting a release.")
    commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config["version"].lstrip("v") != version:
        raise RuntimeError("Requested version and release configuration disagree.")
    configured_commit = config.get("source_commit")
    if configured_commit and configured_commit != commit:
        raise RuntimeError("source_commit does not match the checked-out release source.")
    config["source_commit"] = commit
    for entry in config["patches"]:
        for side in ("source", "target"):
            entry[side] = str((args.config.resolve().parent / entry[side]).resolve())
    gh = shutil.which("gh")
    if not gh and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "GitHub CLI" / "gh.exe"
        if candidate.is_file():
            gh = str(candidate)
    if not gh:
        raise RuntimeError("GitHub CLI is required to publish a release.")
    run([gh, "repo", "view", args.repo, "--json", "name"])
    existing = run([gh, "release", "view", tag, "--repo", args.repo], check=False)
    if existing.returncode == 0:
        raise RuntimeError("Release already exists. Publish a new version; assets are never overwritten.")
    if "not found" not in existing.stderr.lower():
        raise RuntimeError(existing.stderr.strip())
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-build-", dir=WORK) as scratch:
        scratch = Path(scratch)
        local_config = scratch / "private-config.json"
        local_config.write_text(json.dumps(config), encoding="utf-8")
        directory = scratch / "publish"
        build_release(local_config, directory)
        validate_directory(directory)
        notes_body = release_docs(directory, tag)
        validate_directory(directory)
        # Verify existing refs or create them without force updates.
        for ref, command in (("release/" + tag, "branch"), (tag, "tag")):
            resolved = run(["git", "rev-parse", "--verify", ref], check=False)
            if resolved.returncode == 0 and resolved.stdout.strip() != commit:
                raise RuntimeError("Existing release ref points at different source: " + ref)
            if resolved.returncode != 0:
                run(["git", command, ref, commit])
            run(["git", "push", "origin", ref])
        notes = scratch / "notes.md"
        notes.write_text(notes_body, encoding="utf-8")
        assets = [str(p) for p in directory.iterdir() if p.is_file()]
        run([gh, "release", "create", tag, *assets, "--repo", args.repo, "--verify-tag", "--draft",
             "--title", "Vampir English — " + tag, "--notes-file", str(notes)])
        # releases/tags/<tag> does not return drafts: find the draft in the release list
        releases = json.loads(run([gh, "api", "repos/" + args.repo + "/releases?per_page=100"]).stdout)
        uploaded = next((r for r in releases if r["tag_name"] == tag and r["draft"]), None)
        if uploaded is None:
            raise RuntimeError("Draft release not found after upload: " + tag)
        by_name = {a["name"]: a for a in uploaded["assets"]}
        validate_directory(directory)
        for path in directory.iterdir():
            asset = by_name.get(path.name)
            if not asset or asset["size"] != path.stat().st_size or (asset.get("digest") and asset["digest"] != "sha256:" + sha256_file(path)):
                raise RuntimeError("Uploaded asset failed verification; release remains a draft: " + path.name)
        run([gh, "release", "edit", tag, "--repo", args.repo, "--draft=false"])
    print("Published", args.repo, tag)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        raise SystemExit(str(exc))
