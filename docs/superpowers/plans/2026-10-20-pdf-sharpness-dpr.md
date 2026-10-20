# PDF Sharpness & DPR-Aware 1:1 Physical-Pixel Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide razor-sharp PDF page rendering using native device-pixel-ratio (DPR) aware rendering and 1:1 physical-pixel mapping without bilinear/bicubic scaling distortion, while keeping all overlays and interactive features perfectly aligned across zoom levels, window resizes, and scrolling.

**Architecture:** PyMuPDF renders pages at native device physical resolution (`zoom * dpr`). The rendered `QImage` is assigned its device pixel ratio (`setDevicePixelRatio(dpr)`). In `PageWidget`, the `QImage` is blitted directly with `painter.drawImage(QPoint(8, 8), self.qimage)` instead of forcing resampling into an integer-truncated `QRect`, providing exact 1:1 physical-pixel mapping. All interaction coordinates and overlay elements (text selection, hyperlinks, annotations, form fields, redaction previews, ink, stamps/signatures) align with the 1:1 mapped page content. Debounced viewport and scroll triggers ensure newly visible pages are requested at native DPR resolution.

**Tech Stack:** Python 3.10+, PySide6 (Qt 6), PyMuPDF (fitz), pytest.

**Spec:** Concrete cases specified by user:
1. Zoom 1.0, DPR 1.0: logical page ≈ 595x842, physical render ≈ 595x842, QImage.devicePixelRatio() = 1.0
2. Zoom 1.0, DPR 2.0: logical page ≈ 595x842, physical render ≈ 1190x1684, QImage.devicePixelRatio() = 2.0
3. Zoom 2.0, DPR 2.0: physical render ≈ 2380x3368, QImage.devicePixelRatio() = 2.0
Do NOT use SmoothPixmapTransform as the primary fix; do not enlarge a low-resolution bitmap.
Maintain alignment of Resume_CV.pdf at 100%, 150%, 200%, window resize, scrolling, text selection, hyperlinks, annotations, form fields, redaction rectangles, stamps/signatures.

## Global Constraints
- Only modify files in `/home/jonsnow/Desktop/pdf_viewer`.
- Do not touch `/home/jonsnow/Desktop/paperview`, `/home/jonsnow/Desktop/paperview_BACKUP_20261018`, `/home/jonsnow/Desktop/pdf_viewer_RECOVERY_SOURCE`.
- Do not run git reset, git clean, reclone, force checkout, delete backups, or commit/push automatically.
- Run complete test suite before and after changes and report actual test count.

## Review Focus
1. 1:1 physical pixel mapping must never resample or blur the native pixmap on high-DPI screens.
2. Coordinate transforms for text selection, links, form fields, redactions, annotations, stamps, and signatures must match the image offset exactly.
3. Window resizing and viewport scrolling must trigger debounced rendering for newly visible pages.
4. RenderWorker must unconditionally set `QImage.devicePixelRatio(float(task.dpr))`.
5. Page geometry and borders must match the logical size of the rendered page without 1-pixel bleed or gap.

---

### Task 1: RenderWorker & Renderer DPR Guarantees

**Files:**
- Modify: `paperview/renderer.py`
- Test: `tests/test_milestone6.py`

- [ ] **Step 1: Write test for concrete DPR and physical pixel render cases**
- [ ] **Step 2: Run test to check current behavior**
- [ ] **Step 3: Update `RenderWorker` in `paperview/renderer.py` to ensure explicit DPR assignment and floating-point highlight rendering**
- [ ] **Step 4: Verify test passes**

---

### Task 2: PageWidget 1:1 Physical-Pixel Mapping & Dynamic Geometry

**Files:**
- Modify: `paperview/viewer.py`
- Test: `tests/test_milestone6.py`

- [ ] **Step 1: Write test for 1:1 physical pixel blitting without resampling distortion**
- [ ] **Step 2: Run test to observe baseline**
- [ ] **Step 3: Update `PageWidget` in `paperview/viewer.py` to draw native DPR images with `painter.drawImage(QPoint(8, 8), self.qimage)` and align geometry**
- [ ] **Step 4: Verify test passes**

---

### Task 3: Viewport Scrolling, Resizing, and Screen DPR Change Handlers

**Files:**
- Modify: `paperview/viewer.py`
- Modify: `paperview/main_window.py`
- Test: `tests/test_milestone6.py`

- [ ] **Step 1: Write tests for scroll and resize trigger rendering**
- [ ] **Step 2: Run test to check current behavior**
- [ ] **Step 3: Connect scroll and resize events to `render_timer`**
- [ ] **Step 4: Verify test passes**

---

### Task 4: Alignment Verification for All Interactive Features

**Files:**
- Test: `tests/test_milestone6.py`
- Script: verification script for `Resume_CV.pdf`

- [ ] **Step 1: Write automated alignment tests for Resume_CV.pdf at 100%, 150%, 200% across all 10 features (text selection, hyperlinks, annotations, form fields, redaction rectangles, stamps, signatures, window resize, scrolling)**
- [ ] **Step 2: Execute alignment verification test**
- [ ] **Step 3: Verify zero pixel discrepancy**

---

### Task 5: Full Test Suite Execution & Reporting

- [ ] **Step 1: Run complete pytest suite**
- [ ] **Step 2: Report exact test count before and after**
