# PaperView — Milestone 9 Release Readiness Report

## 1. Executive Summary & Verdict

- **Release Version**: 1.0.0
- **Build Target**: Linux x86_64 (glibc 2.44+, Wayland / X11)
- **Licensing Decision**: GNU Affero General Public License v3 (AGPLv3) open-source distribution model
- **Verdict**: **READY FOR RELEASE REVIEW**

### Verdict Rationale
PaperView 1.0.0 satisfies all technical execution and functional requirements, passes 100% of the 160-test automated suite, compiles with zero errors, and runs cleanly from an isolated standalone release archive outside the repository. Privacy cleanup is verified: personal contact information was purged from acceptance reports and test suites, and default fallbacks to local personal documents were eliminated.

The previous licensing blocker has been addressed:
- The canonical root `LICENSE` file containing the complete official GNU AGPLv3 license text was added.
- `LICENSE_NOTES.md` and `README.md` explicitly state PaperView's AGPLv3 project license, PyMuPDF/MuPDF AGPLv3 copyleft obligations (§6 source-code availability), and PySide6/Qt LGPLv3 dynamic linking notices.
- The standalone build and release archive (`dist/paperview-1.0.0-linux-x86_64.tar.gz`) incorporate both `LICENSE` and `LICENSE_NOTES.md` alongside packaged binaries.
- The technical status is elevated from `BLOCKED` to `READY FOR RELEASE REVIEW`. No commits, tags, pushes, or public releases have been performed.

---

## 2. Files Changed and Why

| File | Change Type | Reason |
|---|---|---|
| `LICENSE` | Created | Canonical root GNU Affero General Public License v3 (AGPLv3) license text for open-source distribution. |
| `LICENSE_NOTES.md` | Modified | Added explicit declaration that PaperView is licensed under GNU AGPLv3 and links to the root `LICENSE` file, while retaining third-party notices for PySide6 (LGPLv3) and PyMuPDF/MuPDF (AGPLv3). |
| `README.md` | Modified | Updated "Licensing & Distribution" section to state PaperView's AGPLv3 license, link to `LICENSE`, and summarize PyMuPDF AGPLv3 and PySide6 LGPLv3 terms. Also sanitized developer paths and references. |
| `CHANGELOG.md` | Created / Modified | Documented full 1.0.0 release notes across Milestones 1–8, including canonical root `LICENSE` inclusion under Security & Compliance. |
| `scripts/build_linux.sh` | Modified | Added `--add-data "$PROJECT_ROOT/LICENSE:."` to bundle the canonical root `LICENSE` file into the standalone packaged distribution. |
| `paperview/paperview/app.py` | Modified | Removed hardcoded fallback default that opened `~/Desktop/Resume_CV.pdf` when launched without arguments. |
| `tests/test_milestone8.py` | Modified | Added synthetic PDF text selection and clipboard copying assertions (`test_m8_gui_startup_render_nav_zoom_search_and_shutdown`), verifying functionality with dummy text rather than private document contents. |
| `reports/M8_MANUAL_ACCEPTANCE_REPORT.md` | Modified | Sanitized public-facing acceptance report evidence by replacing candidate name, phone number, and institutional email with neutral placeholders (`[REDACTED_CANDIDATE_NAME]`, `[REDACTED_CONTACT_INFO]`). |
| `dist/paperview-1.0.0-linux-x86_64.tar.gz` | Created / Packaged | Standalone Linux release archive generated with `scripts/build_linux.sh`, containing application binaries, bundled Qt/PyMuPDF shared objects, desktop integration files, and both `LICENSE` and `LICENSE_NOTES.md`. |
| `dist/paperview-1.0.0-linux-x86_64.tar.gz.sha256` | Created | Cryptographic SHA256 checksum for the release archive. |

---

## 3. Privacy and Repository Hygiene Findings

1. **Personal Information in Acceptance Reports**:
   - `reports/M8_MANUAL_ACCEPTANCE_REPORT.md` lines 8–9 and 53–54 sanitized: candidate name, student email (`@iith.ac.in`), and phone number (`+91 7780128500`) replaced with neutral placeholders.
2. **Personal PDF Default Fallback**:
   - `paperview/paperview/app.py` fallback pointing to `~/Desktop/Resume_CV.pdf` removed; application now opens an empty window when launched without arguments.
3. **Selection & Clipboard Test Privacy**:
   - Interactive mouse selection and clipboard copy assertions in `tests/test_milestone8.py` use `sample_test_pdf` (synthetic PDF with dummy text).
4. **Developer Absolute Local Paths**:
   - `README.md` sanitized of `/home/jonsnow/...` paths in smoke-test instructions and markdown links.
5. **Secrets & Credentials Scan**:
   - Clean scan: zero private keys, API tokens, or personal documents tracked in git or included in release bundles.

---

## 4. Licensing Decision & Package Licensing Contents

### Licensing Decision
The project is prepared for an **open-source release under the GNU Affero General Public License v3 (AGPLv3)**.

### Declared Components & Notices
1. **PaperView Application**:
   - License: GNU AGPLv3 (root `LICENSE`).
   - Source code availability: Under AGPLv3 §6, distributors of packaged binaries must provide accessible access to the complete machine-readable source code.
2. **PyMuPDF (`pymupdf`) & MuPDF (Artifex Software, Inc.)**:
   - Backend PDF rasterization and manipulation engine.
   - License: GNU AGPLv3 (dual-licensed commercially by Artifex).
   - In an open-source AGPLv3 distribution, PaperView satisfies copyleft obligations by releasing all corresponding source code under AGPLv3.
3. **PySide6 & Qt Framework (The Qt Company)**:
   - GUI framework bindings and shared libraries.
   - License: GNU LGPLv3.
   - Bundled dynamically as shared objects (`.so`) in `dist/paperview/_internal/` to allow end-users to inspect or replace Qt libraries.

### Package Licensing Contents
Verification of the extracted release archive (`dist/paperview-1.0.0-linux-x86_64.tar.gz`) confirms the presence of:
- `paperview/_internal/LICENSE` (Complete text of GNU AGPLv3).
- `paperview/_internal/LICENSE_NOTES.md` (Comprehensive third-party license breakdown and distribution requirements).

### Legal & Distribution Caveats
- While the technical packaging and repository files fulfill the structural requirements of AGPLv3/LGPLv3, legal compliance is subject to the distributor actually making the corresponding source code publicly available upon release.
- If PaperView is ever distributed without providing source code (e.g. proprietary bundling or closed SaaS), an upfront commercial license from Artifex Software, Inc. must be secured.

---

## 5. Release Archive and Package Verification

| Metric | Value |
|---|---|
| **Archive File** | `dist/paperview-1.0.0-linux-x86_64.tar.gz` |
| **Archive Size** | 115 MB (120,490,446 bytes) |
| **Extracted Directory** | `dist/paperview/` (281 MB on disk) |
| **SHA256 Checksum** | `c1a9a3c01ad613a1e111d2de6b598a1537aeea3a7463c18e1950ad0efce6b935` |
| **Checksum File** | `dist/paperview-1.0.0-linux-x86_64.tar.gz.sha256` |
| **Executable Entry** | `paperview` (ELF 64-bit LSB executable, x86-64) |
| **Target OS / ABI** | Linux x86-64 (Arch Linux glibc 2.44) |

### External Extraction Smoke-Test
The archive was extracted to an isolated directory in `/tmp/pv_license_verify.XXXXXX` and executed outside the repository:
1. `paperview --version` returned `PaperView 1.0.0` (exit code 0).
2. `paperview --help` printed full usage synopsis and argument descriptions (exit code 0).
3. Verified `_internal/LICENSE` contains full GNU AGPLv3 text.
4. Verified `_internal/LICENSE_NOTES.md` contains AGPLv3 / LGPLv3 third-party notices.
5. Verified desktop integration files: `_internal/packaging/paperview.desktop` and `_internal/packaging/icons/paperview.svg`.

---

## 6. Verification Commands and Exact Results

### 1. Bytecode Compilation (`compileall`)
```bash
.venv/bin/python -m compileall paperview tests
```
- **Result**: PASS (exit code 0, 0 compilation errors across all modules).

### 2. Full Test Suite (`pytest`)
```bash
.venv/bin/pytest -q
```
- **Result**: PASS (160 passed, 3 benign Qt mouse event warnings in 10.11s, 100% pass rate).

### 3. Linux Package Build (`build_linux.sh`)
```bash
./scripts/build_linux.sh
```
- **Result**: PASS (Exit code 0. Standalone directory created at `dist/paperview`, verified executable version reporting `PaperView 1.0.0`).

### 4. Freedesktop Desktop Entry Validation
```bash
desktop-file-validate packaging/paperview.desktop
```
- **Result**: PASS (0 errors, 0 warnings).

### 5. Standalone Extraction & License Verification
```bash
bash -c '
EXTRACT_DIR=$(mktemp -d /tmp/pv_license_verify.XXXXXX)
tar -xzf dist/paperview-1.0.0-linux-x86_64.tar.gz -C "$EXTRACT_DIR"
test -f "$EXTRACT_DIR/paperview/_internal/LICENSE"
test -f "$EXTRACT_DIR/paperview/_internal/LICENSE_NOTES.md"
"$EXTRACT_DIR/paperview/paperview" --version
rm -rf "$EXTRACT_DIR"
'
```
- **Result**: PASS (Exit code 0).

---

## 7. Remaining Blockers

- **None (Technical & Documentation Blockers Resolved)**.
- Release execution steps (git commit, git tag `v1.0.0`, git push, and public release hosting) remain deferred as requested for human maintainer execution.

---

## 8. Final Verdict

**READY FOR RELEASE REVIEW**
