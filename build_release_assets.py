from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
WEBSITE_URL = "https://code2video.vercel.app"
REPO_URL = "https://github.com/mechreaper007x/code2video-renderer"

PUBLIC_ARTIFACTS = [
    "CODE2VIDEO-Setup.exe",
    "CODE2VIDEO-windows.zip",
    "CODE2VIDEO-macos.zip",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{num_bytes} B"


def collect_artifacts() -> list[dict]:
    artifacts: list[dict] = []
    for name in PUBLIC_ARTIFACTS:
        path = DIST / name
        if not path.exists():
            continue
        artifacts.append(
            {
                "name": name,
                "path": path,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return artifacts


def write_sha256sums(artifacts: list[dict]) -> Path:
    output = DIST / "SHA256SUMS.txt"
    lines = [f"{artifact['sha256']}  {artifact['name']}" for artifact in artifacts]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def write_release_notes(artifacts: list[dict], version: str) -> Path:
    release_url = f"{REPO_URL}/releases/tag/{version}"
    notes = DIST / "RELEASE_NOTES.md"

    asset_lines = []
    checksum_lines = []
    for artifact in artifacts:
        asset_lines.append(f"- `{artifact['name']}` ({format_size(artifact['size'])})")
        checksum_lines.append(f"- `{artifact['name']}`: `{artifact['sha256']}`")

    content = f"""# CODE2VIDEO {version}

Website: {WEBSITE_URL}

Release page: {release_url}

## Assets

{chr(10).join(asset_lines) if asset_lines else '- No public artifacts found in `dist/`.'}

## Trust Notes

- Windows builds are currently unsigned and may trigger SmartScreen or Defender reputation warnings.
- Download only from the official GitHub Releases page.
- Verify the downloaded files against `SHA256SUMS.txt`.

## SHA256 Checksums

{chr(10).join(checksum_lines) if checksum_lines else '- No checksums generated.'}
"""
    notes.write_text(content, encoding="utf-8")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release checksum and notes files from dist/ artifacts.")
    parser.add_argument("--version", default="v1.0.0", help="Release tag used in generated notes. Default: v1.0.0")
    args = parser.parse_args()

    DIST.mkdir(parents=True, exist_ok=True)
    artifacts = collect_artifacts()
    sha_path = write_sha256sums(artifacts)
    notes_path = write_release_notes(artifacts, args.version)

    print(f"Wrote {sha_path}")
    print(f"Wrote {notes_path}")
    for artifact in artifacts:
        print(f"{artifact['name']}: {artifact['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
