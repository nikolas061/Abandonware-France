#!/usr/bin/env sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$BASE_DIR"

OUTPUT_DIR=${1:-output/hd_support_bundle}
ARCHIVE=${OUTPUT_DIR%/}.tar.gz

copy_if_exists() {
	src=$1
	dst=$2
	if [ -e "$src" ]; then
		mkdir -p "$(dirname "$dst")"
		cp -R "$src" "$dst"
	fi
}

echo "Collecte du support HD: $OUTPUT_DIR"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/reports" "$OUTPUT_DIR/docs" "$OUTPUT_DIR/scripts" "$OUTPUT_DIR/desktop" "$OUTPUT_DIR/tools"

python3 tools/lolg_hd_resolution_check.py >/dev/null || true
./PACK_HD_RELEASE.sh --skip-check >/dev/null || true
./VERIFY_HD_MANIFEST.sh >/dev/null || true
python3 tools/lolg_hd_status.py -o output/hd_status >/dev/null || true
python3 tools/lolg_vqa_external_sidecar_status.py --critical --json > "$OUTPUT_DIR/reports/sidecar_critical_status.json" 2>/dev/null || true

for report in hd_status hd_release_check hd_release_manifest hd_release_manifest_verify hd_resolution_check hd_graphics_check hd_wine_smoke_test hd_wine_smoke_test_1280x1024; do
	copy_if_exists "output/$report" "$OUTPUT_DIR/reports/$report"
done

copy_if_exists "output/vqa_external_sidecar_index/summary.csv" "$OUTPUT_DIR/reports/vqa_external_sidecar_index/summary.csv"
copy_if_exists "output/vqa_external_sidecar_index/archives.csv" "$OUTPUT_DIR/reports/vqa_external_sidecar_index/archives.csv"
copy_if_exists "output/vqa_external_sidecar_index/entries.csv" "$OUTPUT_DIR/reports/vqa_external_sidecar_index/entries.csv"
copy_if_exists "output/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/result.json" "$OUTPUT_DIR/reports/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/result.json"
copy_if_exists "output/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/result.json" "$OUTPUT_DIR/reports/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/result.json"
for decode_meta in header.json frames.csv rendered_frames.csv; do
	copy_if_exists "output/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/decode/$decode_meta" "$OUTPUT_DIR/reports/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/decode/$decode_meta"
	copy_if_exists "output/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/decode/$decode_meta" "$OUTPUT_DIR/reports/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/decode/$decode_meta"
done

for doc in LANCER_HD.txt Instructions_Lancement.txt README HD_TEXTURES.md MISE_AU_POINT_PROJET.md; do
	copy_if_exists "$doc" "$OUTPUT_DIR/docs/$doc"
done

for script in \
	LOLG_HD.sh RUN_HD_WINE.sh RUN_HD.sh CHECK_HD.sh CHECK_HD_GPU.sh TEST_HD_WINE.sh \
	PACK_HD_RELEASE.sh STOP_HD_WINE.sh REPAIR_HD_WINE.sh RUN_HD_DESKTOP.sh \
	INSTALL_HD_DESKTOP.sh UNINSTALL_HD_DESKTOP.sh COLLECT_HD_SUPPORT.sh VERIFY_HD_MANIFEST.sh
do
	copy_if_exists "$script" "$OUTPUT_DIR/scripts/$script"
done

for support_tool in \
	tools/lolg_hd_status.py \
	tools/lolg_hd_release_check.py \
	tools/lolg_hd_release_manifest.py \
	tools/lolg_hd_manifest_verify.py \
	tools/lolg_hd_support_manifest_verify.py \
	tools/lolg_hd_support_archive_verify.py \
	tools/lolg_hd_resolution_check.py \
	tools/lolg_hd_graphics_check.py \
	tools/lolg_hd_wine_smoke_test.py \
	tools/lolg_vqa_external_sidecar_index.py \
	tools/lolg_vqa_external_sidecar_status.py \
	tools/lolg_vqa_external_sidecar_request.py \
	tools/lolg_vqa_decode.py \
	tools/lolg_vqa_external_sidecar_web.py \
	tools/lolg_vqa_external_sidecar_audit.py
do
	copy_if_exists "$support_tool" "$OUTPUT_DIR/$support_tool"
done

for desktop_file in desktop/lolg-hd.desktop desktop/lolg-hd-status.desktop desktop/lolg-hd-repair.desktop; do
	copy_if_exists "$desktop_file" "$OUTPUT_DIR/$desktop_file"
done

cat > "$OUTPUT_DIR/README_SUPPORT.txt" <<'EOF'
LOLG HD support bundle
======================

Resume rapide:
- SUPPORT_SUMMARY.txt: resume machine court des champs launch-ready, release pass/info/gaps et sidecar critiques.
- reports/hd_status/summary.csv: etat launch-ready, sidecar_critical_full_ready, frames LOCALLNG/MOVIES pretes.
- reports/hd_release_check/summary.csv: resultat du check release.
- reports/vqa_external_sidecar_index/entries.csv: index sidecar VQA HD, dont LOCALLNG/MOVIES critiques.
- reports/sidecar_critical_status.json: etat JSON sidecar critique LOCALLNG/MOVIES.
- reports/vqa_external_sidecar_cache/*/result.json: resultats de decode sidecar critiques.
- reports/vqa_external_sidecar_cache/*/decode/rendered_frames.csv: audit des frames rendues, sans copier les PNG lourds.
- diagnostic.txt: versions Python/Pillow, outils copies, processus actifs et git status.
- BUNDLE_MANIFEST.csv: schema exact path,size,sha256,executable, en-tetes/chemins non dupliques, lignes bien formees et chemins relatifs canoniques sans antislash pointant vers des fichiers.
- VERIFY_SUPPORT.sh: verification locale du bundle sans dependance au projet original.
- output/hd_support_bundle.tar.gz.sha256: checksum externe mono-ligne strict hash+archive, nom d'archive exact sans chemin.
- output/hd_support_bundle.tar.gz.summary: resume machine externe strict de l'archive support.
- output/hd_support_bundle.tar.gz.verify.sh: verification autonome de l'archive support, avec archive non vide, racine unique et nom de racine attendu.
- output/hd_support_bundle.tar.gz.artifacts.csv: manifeste strict des 4 fichiers externes a copier ensemble, avec schema exact, formats, noms portables simples et doublons refuses.
- tools/lolg_hd_support_manifest_verify.py: verification locale de BUNDLE_MANIFEST.csv apres copie.
- tools/lolg_hd_support_archive_verify.py: verification de l'archive tar.gz apres extraction temporaire.
- tools/lolg_vqa_external_sidecar_request.py + tools/lolg_vqa_decode.py: client et decodeur VQA sidecar.

Commandes utiles depuis le projet original:
- ./LOLG_HD.sh status
- ./LOLG_HD.sh check
- ./LOLG_HD.sh verify-support
- ./LOLG_HD.sh verify-support-archive
- ./LOLG_HD.sh sidecar-critical-status --json
- ./LOLG_HD.sh sidecar-critical-warmup
- ./LOLG_HD.sh sidecar-hd

Commande utile depuis ce bundle copie/decompresse:
- ./VERIFY_SUPPORT.sh

Etat attendu pour le chemin recommande:
- Ready to launch: yes
- Release check: pass avec 0 gap; les lignes info sont des diagnostics non bloquants.
- sidecar_critical_ready=1
- sidecar_critical_full_ready=1 apres warmup complet
- LOCALLNG 237/237 frames
- MOVIES 75/75 frames
EOF

cat > "$OUTPUT_DIR/VERIFY_SUPPORT.sh" <<'EOF'
#!/usr/bin/env sh

set -eu

BUNDLE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUTPUT_DIR=${LOLG_HD_SUPPORT_VERIFY_OUTPUT:-/tmp/lolg_hd_support_manifest_verify}

python3 "$BUNDLE_DIR/tools/lolg_hd_support_manifest_verify.py" "$BUNDLE_DIR" -o "$OUTPUT_DIR"
EOF
chmod +x "$OUTPUT_DIR/VERIFY_SUPPORT.sh"

python3 - "$OUTPUT_DIR" > "$OUTPUT_DIR/SUPPORT_SUMMARY.txt" <<'PY'
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


root = Path(sys.argv[1])


def read_csv_first(path: Path) -> dict[str, str]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except FileNotFoundError:
        return {}
    return rows[0] if rows else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError:
        return []


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


status = read_csv_first(root / "reports/hd_status/summary.csv")
release = read_csv_first(root / "reports/hd_release_check/summary.csv")
manifest = read_csv_first(root / "reports/hd_release_manifest/summary.csv")
manifest_verify = read_csv_first(root / "reports/hd_release_manifest_verify/summary.csv")
resolution = read_csv_first(root / "reports/hd_resolution_check/summary.csv")
sidecar = read_json(root / "reports/sidecar_critical_status.json")
entries = read_csv_rows(root / "reports/vqa_external_sidecar_index/entries.csv")
locallng_rendered = read_csv_rows(
    root / "reports/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/decode/rendered_frames.csv"
)
movies_rendered = read_csv_rows(
    root / "reports/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/decode/rendered_frames.csv"
)
locallng_index = [
    row
    for row in entries
    if row.get("archive") == "LOCALLNG.MIX"
    and row.get("file_id") == "fca4e133"
    and row.get("width") == "1920"
    and row.get("height") == "1080"
]
movies_index_ids = {
    row.get("file_id", "")
    for row in entries
    if row.get("archive") == "MOVIES.MIX"
    and row.get("width") == "1920"
    and row.get("height") == "1080"
}
support_issues = []
if release.get("status") != "pass":
    support_issues.append("release_check")
if manifest.get("status") != "pass":
    support_issues.append("manifest")
if manifest_verify.get("status") != "pass":
    support_issues.append("manifest_verify")
if resolution.get("status") != "pass":
    support_issues.append("resolution_check")
if str(sidecar.get("critical_ready", "")).lower() != "true":
    support_issues.append("sidecar_critical")
if len(locallng_index) < 1:
    support_issues.append("locallng_index")
if len(movies_index_ids) != 28:
    support_issues.append("movies_index")
if len(locallng_rendered) != 237:
    support_issues.append("locallng_rendered")
if len(movies_rendered) != 75:
    support_issues.append("movies_rendered")
ready_to_launch = not support_issues

print("support_summary_version=1")
print(f"status={'pass' if ready_to_launch else 'gap'}")
print(f"ready_to_launch={1 if ready_to_launch else 0}")
print(f"status_report={status.get('status', '')}")
print(f"status_report_ready_to_launch={status.get('ready_to_launch', '')}")
print(f"release_check={release.get('status', '')}")
print(f"release_passed={release.get('passed', '')}/{release.get('checks', '')}")
print(f"release_pass_count={release.get('passed', '')}")
print(f"release_checks={release.get('checks', '')}")
print(f"release_info={release.get('info', '')}")
print(f"release_display={release.get('passed', '')} pass + {release.get('info', '')} info / {release.get('checks', '')}")
print(f"release_gaps={release.get('gaps', '')}")
print(f"manifest={manifest.get('status', '')}")
print(f"manifest_verify={manifest_verify.get('status', '')}")
print(f"manifest_verify_gaps={manifest_verify.get('gaps', '')}")
print(f"resolution={resolution.get('status', '')}")
print(f"resolution_gaps={resolution.get('gaps', '')}")
print(f"sidecar_critical_ready={status.get('sidecar_critical_ready', '')}")
print(f"sidecar_critical_full_ready={status.get('sidecar_critical_full_ready', '')}")
print(f"locallng_ready={status.get('sidecar_locallng_ready_frames', '')}/{status.get('sidecar_locallng_frames', '')}")
print(f"movies_ready={status.get('sidecar_movies_ready_frames', '')}/{status.get('sidecar_movies_frames', '')}")
print(f"locallng_rendered_rows={len(locallng_rendered)}")
print(f"movies_rendered_rows={len(movies_rendered)}")
print(f"index_locallng_1920={len(locallng_index)}")
print(f"index_movies_1920={len(movies_index_ids)}")
print(f"sidecar_json_critical_ready={str(sidecar.get('critical_ready', '')).lower()}")
print(f"support_summary_issues={';'.join(support_issues)}")
PY

{
	echo "date_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
	echo "project=$BASE_DIR"
	echo "archive=$ARCHIVE"
	echo
	echo "[du]"
	du -sh output/hd_status output/hd_release_check output/hd_release_manifest output/hd_release_manifest_verify output/hd_resolution_check output/hd_graphics_check output/hd_wine_smoke_test output/hd_wine_smoke_test_1280x1024 2>/dev/null || true
	du -sh output/vqa_external_sidecar_index output/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133 output/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e 2>/dev/null || true
	echo
	echo "[sidecar_critical_status]"
	cat "$OUTPUT_DIR/reports/sidecar_critical_status.json" 2>/dev/null || true
	echo
	echo "[support_tools]"
	find "$OUTPUT_DIR/tools" -maxdepth 1 -type f -name '*.py' 2>/dev/null | sed "s#^$OUTPUT_DIR/##" | sort || true
	echo
	echo "[python_dependencies]"
	python3 -c 'import sys; print("python=" + sys.version.split()[0]); import PIL; print("pillow=present"); print("pillow_version=" + getattr(PIL, "__version__", "unknown"))' 2>/dev/null || echo "pillow=missing"
	echo
	echo "[processes]"
	pgrep -af 'LOLG95|wine|wineserver|explorer.exe|RUN_HD_WINE' 2>/dev/null || true
	echo
	echo "[git_status_short]"
	git status --short 2>/dev/null || true
} > "$OUTPUT_DIR/diagnostic.txt"

python3 - "$OUTPUT_DIR" > "$OUTPUT_DIR/BUNDLE_MANIFEST.csv" <<'PY'
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path


root = Path(sys.argv[1])
rows = []
for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
    if path.name == "BUNDLE_MANIFEST.csv":
        continue
    relative = path.relative_to(root).as_posix()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    rows.append(
        {
            "path": relative,
            "size": str(path.stat().st_size),
            "sha256": digest.hexdigest(),
            "executable": "1" if path.stat().st_mode & 0o111 else "0",
        }
    )

writer = csv.DictWriter(sys.stdout, fieldnames=["path", "size", "sha256", "executable"])
writer.writeheader()
writer.writerows(rows)
PY

tar -czf "$ARCHIVE" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")"
python3 - "$ARCHIVE" "$OUTPUT_DIR" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import sys
from pathlib import Path


archive = Path(sys.argv[1])
bundle_dir = Path(sys.argv[2])
digest = hashlib.sha256()
with archive.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
sha256 = digest.hexdigest()
(Path(str(archive) + ".sha256")).write_text(f"{sha256}  {archive.name}\n", encoding="utf-8")
(Path(str(archive) + ".summary")).write_text(
    "\n".join(
        [
            "support_archive_summary_version=1",
            f"generated_utc={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"archive={archive.name}",
            f"archive_size={archive.stat().st_size}",
            f"sha256={sha256}",
            f"sha256_file={archive.name}.sha256",
            f"bundle_dir={bundle_dir.name}",
            "",
        ]
    ),
    encoding="utf-8",
)
PY
cat > "$ARCHIVE.verify.sh" <<'EOF'
#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SCRIPT_NAME=$(basename -- "$0")
if [ "$#" -gt 0 ]; then
	ARCHIVE=$1
else
	case "$SCRIPT_NAME" in
		*.verify.sh) ARCHIVE=$SCRIPT_DIR/${SCRIPT_NAME%.verify.sh} ;;
		*) ARCHIVE=$SCRIPT_DIR/hd_support_bundle.tar.gz ;;
	esac
fi

python3 - "$ARCHIVE" <<'PY'
from __future__ import annotations

import hashlib
import csv
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


archive = Path(sys.argv[1])
checksum = Path(str(archive) + ".sha256")
summary_path = Path(str(archive) + ".summary")
artifacts_path = Path(str(archive) + ".artifacts.csv")
sha256_re = re.compile(r"^[0-9a-fA-F]{64}$")
utc_timestamp_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
artifact_name_re = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
summary_required_keys = {
    "support_archive_summary_version",
    "generated_utc",
    "archive",
    "archive_size",
    "sha256",
    "sha256_file",
    "bundle_dir",
}


def fail(message: str) -> None:
    print(f"support archive companion verify: gap {message}")
    raise SystemExit(1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_fieldnames(handle: csv.DictReader[str]) -> set[str]:
    return {field if field is not None else "<extra>" for field in (handle.fieldnames or [])}


def csv_duplicate_fieldnames(fieldnames: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for field in fieldnames:
        if field in seen and field not in duplicates:
            duplicates.append(field)
        seen.add(field)
    return duplicates


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def read_kv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def duplicate_kv_keys(path: Path) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)
    return duplicates


def malformed_kv_lines(path: Path) -> list[str]:
    malformed: list[str] = []
    for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            malformed.append(str(index))
    return malformed


def safe_tar_name(name: str) -> bool:
    if not name or name.startswith("/") or "\\" in name:
        return False
    parts = PurePosixPath(name).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def safe_artifact_name(name: str) -> bool:
    if not name or name.startswith("/") or "\\" in name or "/" in name:
        return False
    return name not in {".", ".."} and artifact_name_re.match(name) is not None


if not archive.is_file():
    fail(f"archive_missing={archive}")
if not checksum.is_file():
    fail(f"checksum_missing={checksum}")
if not summary_path.is_file():
    fail(f"summary_missing={summary_path}")
if not artifacts_path.is_file():
    fail(f"artifacts_missing={artifacts_path}")

actual_sha = sha256_file(archive)
checksum_lines = checksum.read_text(encoding="utf-8", errors="replace").strip().splitlines()
if len(checksum_lines) != 1:
    fail("checksum_line_count_mismatch")
checksum_parts = checksum_lines[0].split()
if len(checksum_parts) != 2 or not sha256_re.match(checksum_parts[0]):
    fail("checksum_format_invalid")
expected_sha = checksum_parts[0].lower()
checksum_archive_name = checksum_parts[1].lstrip("*")
if checksum_archive_name != archive.name:
    fail("checksum_archive_name_mismatch")
if actual_sha.lower() != expected_sha:
    fail("archive_sha256_mismatch")

summary = read_kv(summary_path)
summary_malformed_lines = malformed_kv_lines(summary_path)
if summary_malformed_lines:
    fail("summary_malformed_lines:" + ",".join(summary_malformed_lines))
summary_duplicate_keys = duplicate_kv_keys(summary_path)
if summary_duplicate_keys:
    fail("summary_duplicate_keys:" + ",".join(summary_duplicate_keys))
if set(summary) != summary_required_keys:
    fail("summary_schema_mismatch")
summary_checks = {
    "support_archive_summary_version": "1",
    "archive": archive.name,
    "archive_size": str(archive.stat().st_size),
    "sha256": actual_sha,
    "sha256_file": checksum.name,
    "bundle_dir": archive.stem.removesuffix(".tar"),
}
for key, expected in summary_checks.items():
    if summary.get(key) != expected:
        fail(f"summary_{key}_mismatch")
if not utc_timestamp_re.match(summary.get("generated_utc", "")):
    fail("summary_generated_utc_invalid")

with artifacts_path.open(newline="", encoding="utf-8") as handle:
    artifact_reader = csv.DictReader(handle)
    artifact_rows = list(artifact_reader)
artifact_duplicate_fields = csv_duplicate_fieldnames([
    field if field is not None else "<extra>" for field in (artifact_reader.fieldnames or [])
])
artifact_fields = csv_fieldnames(artifact_reader)
required_fields = {"path", "size", "sha256", "executable"}
if artifact_duplicate_fields:
    fail("artifacts_duplicate_fields:" + ",".join(artifact_duplicate_fields))
if artifact_fields != required_fields:
    fail("artifacts_schema_mismatch")
if any(None in row for row in artifact_rows):
    fail("artifacts_row_width_mismatch")
artifact_field_format_issues = []
for row in artifact_rows:
    row_path = row.get("path", "")
    if not row.get("size", "").isdigit():
        artifact_field_format_issues.append(f"size:{row_path}")
    if not sha256_re.match(row.get("sha256", "")):
        artifact_field_format_issues.append(f"sha256:{row_path}")
    if row.get("executable") not in {"0", "1"}:
        artifact_field_format_issues.append(f"executable:{row_path}")
if artifact_field_format_issues:
    fail("artifacts_field_format_mismatch:" + ",".join(artifact_field_format_issues[:5]))
unsafe_artifact_paths = [
    row.get("path", "") for row in artifact_rows if not safe_artifact_name(row.get("path", ""))
]
if unsafe_artifact_paths:
    fail("artifacts_unsafe_paths:" + ",".join(unsafe_artifact_paths[:5]))
expected_artifacts = {
    archive.name: archive,
    checksum.name: checksum,
    summary_path.name: summary_path,
    Path(str(archive) + ".verify.sh").name: Path(str(archive) + ".verify.sh"),
}
artifact_duplicate_paths = duplicate_values([row.get("path", "") for row in artifact_rows])
if artifact_duplicate_paths:
    fail("artifacts_duplicate_paths:" + ",".join(artifact_duplicate_paths))
if len(artifact_rows) != len(expected_artifacts):
    fail("artifacts_count_mismatch")
if {row.get("path", "") for row in artifact_rows} != set(expected_artifacts):
    fail("artifacts_paths_mismatch")
for row in artifact_rows:
    path = expected_artifacts[row["path"]]
    if not path.is_file():
        fail(f"artifact_missing={row['path']}")
    if row.get("size") != str(path.stat().st_size):
        fail(f"artifact_size_mismatch={row['path']}")
    if row.get("sha256", "").lower() != sha256_file(path).lower():
        fail(f"artifact_sha256_mismatch={row['path']}")
    executable = "1" if path.stat().st_mode & 0o111 else "0"
    if row.get("executable") != executable:
        fail(f"artifact_executable_mismatch={row['path']}")

with tarfile.open(archive, "r:gz") as tar:
    members = tar.getmembers()
    if not members:
        fail("archive_empty")
    unsafe = [member.name for member in members if not safe_tar_name(member.name)]
    if unsafe:
        fail("unsafe_tar_paths")
    unsupported = [member.name for member in members if not (member.isfile() or member.isdir())]
    if unsupported:
        fail("unsupported_tar_members")
    top_levels = sorted({PurePosixPath(member.name).parts[0] for member in members})
    if len(top_levels) != 1:
        fail("top_level_mismatch")
    top_level = top_levels[0]
    expected_top_level = archive.stem.removesuffix(".tar")
    if top_level != expected_top_level:
        fail("top_level_name_mismatch")
    verify_member = next(
        (
            member
            for member in members
            if PurePosixPath(member.name).parts == (top_level, "VERIFY_SUPPORT.sh")
        ),
        None,
    )
    if verify_member is None:
        fail("verify_script_missing")
    if not (verify_member.mode & 0o111):
        fail("verify_script_not_executable")
    with tempfile.TemporaryDirectory(prefix="lolg_hd_support_companion_") as tmp:
        tmp_path = Path(tmp)
        tar.extractall(tmp_path, filter="data")
        extracted_root = tmp_path / top_level
        verify_script = extracted_root / "VERIFY_SUPPORT.sh"
        if not verify_script.is_file():
            fail("verify_script_missing_after_extract")
        env = os.environ.copy()
        env["LOLG_HD_SUPPORT_VERIFY_OUTPUT"] = str(tmp_path / "verify")
        result = subprocess.run(
            [str(verify_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            env=env,
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip().replace("\n", " | ")
            fail(f"verify_script_failed={detail}")

print(
    "support archive companion verify: pass "
    f"sha256={actual_sha} files={sum(1 for member in members if member.isfile())} "
    f"top={top_level} summary=pass manifest=pass artifacts=pass "
    "artifact_duplicate_paths=pass artifact_field_format=pass artifact_safe_paths=pass "
    "archive_not_empty=pass single_top_level=pass top_level_name=pass"
)
PY
EOF
chmod +x "$ARCHIVE.verify.sh"
python3 - "$ARCHIVE" "$ARCHIVE.sha256" "$ARCHIVE.summary" "$ARCHIVE.verify.sh" > "$ARCHIVE.artifacts.csv" <<'PY'
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


rows = []
for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    rows.append(
        {
            "path": path.name,
            "size": str(path.stat().st_size),
            "sha256": sha256_file(path),
            "executable": "1" if path.stat().st_mode & 0o111 else "0",
        }
    )

writer = csv.DictWriter(sys.stdout, fieldnames=["path", "size", "sha256", "executable"])
writer.writeheader()
writer.writerows(rows)
PY

echo "Support HD collecte:"
echo "  Dossier: $OUTPUT_DIR"
echo "  Archive: $ARCHIVE"
echo "  SHA256: $ARCHIVE.sha256"
echo "  Summary: $ARCHIVE.summary"
echo "  Verify: $ARCHIVE.verify.sh"
echo "  Artifacts: $ARCHIVE.artifacts.csv"
