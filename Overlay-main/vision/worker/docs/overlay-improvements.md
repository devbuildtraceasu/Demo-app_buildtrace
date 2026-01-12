# Overlay Pipeline Improvements

This document tracks the overlay pipeline improvement plan. Each item includes the
idea, value, implementation approach, and expected files touched. Use the
checkboxes to track completion.

## Pairing + Matching
- [x] Block pairing by metadata name.
  - Value: stable pairing for blocks with consistent titles.
  - Implementation: match `Block.metadata_.name` within type groups before other heuristics.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py

- [x] Block pairing by normalized text signature.
  - Value: pairs blocks even when names differ but OCR/description matches.
  - Implementation: normalize `Block.description` or `Block.ocr` and match exact signature.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py

- [x] Bounds-based pairing with compatibility filtering.
  - Value: avoids pairing blocks with wildly different size/aspect.
  - Implementation: compute bounds signature, filter by size/aspect ratio range before scoring.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py

- [x] Skip mismatched block types in fallback pairing.
  - Value: avoids cross-type matches during order fallback.
  - Implementation: when falling back to order, skip if both types are set and differ.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py

- [ ] Fuzzy OCR/description similarity (token overlap or cosine similarity).
  - Value: improves pairing when text is similar but not identical.
  - Implementation: add a similarity scorer (e.g., token set ratio) and select best candidate.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py

- [ ] Store pairing metadata on Overlay records.
  - Value: audit which method produced a pairing and track confidence over time.
  - Implementation: add fields in overlay summary/metadata and write pairingMethod + score.
  - Files: apps/vision/worker/models.py, apps/vision/worker/jobs/sheet_overlay_generate.py

- [ ] Use title block metadata for pairing where available.
  - Value: improves matching for drawings with strong title block data.
  - Implementation: extract normalized title block fields and integrate into matching.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py

## Sheet Pairing (Drawing Overlay)
- [x] Pair sheets by normalized sheet number.
  - Value: handles differences in spacing/punctuation (e.g., "A-101" vs "A101").
  - Implementation: strip to alphanumeric and match sheet_number keys.
  - Files: apps/vision/worker/jobs/drawing_overlay_generate.py

- [x] Pair sheets by title.
  - Value: recovers matches when sheet numbers are missing.
  - Implementation: lowercased title matching after sheet number pass.
  - Files: apps/vision/worker/jobs/drawing_overlay_generate.py

- [x] Pair sheets by discipline.
  - Value: reduces mismatches when drawings include multiple disciplines.
  - Implementation: group by discipline, pick closest by sort order.
  - Files: apps/vision/worker/jobs/drawing_overlay_generate.py

- [x] Skip mismatched disciplines in fallback pairing.
  - Value: prevents cross-discipline pairings in order fallback.
  - Implementation: skip if both disciplines are set and differ.
  - Files: apps/vision/worker/jobs/drawing_overlay_generate.py

- [ ] Fuzzy title matching for sheets.
  - Value: handles minor title differences (e.g., "Level 1 Plan" vs "Level 01 Plan").
  - Implementation: add token overlap or edit-distance matching for titles.
  - Files: apps/vision/worker/jobs/drawing_overlay_generate.py

## Alignment + Scoring
- [x] Alignment + overlay score for block overlays.
  - Value: improves quality and exposes confidence.
  - Implementation: SIFT + RANSAC alignment; compute inlier ratio as score.
  - Files: apps/vision/worker/jobs/block_overlay_generate.py

- [x] Flag low-confidence overlays.
  - Value: allows UI or ops to surface questionable results.
  - Implementation: add `overlayLowConfidence` flag to job metadata when score below threshold.
  - Files: apps/vision/worker/jobs/block_overlay_generate.py

- [x] Log alignment stats and missing alignment warnings.
  - Value: improves debugging and monitoring.
  - Implementation: include inlier/match counts, warn when no matches.
  - Files: apps/vision/worker/jobs/block_overlay_generate.py

- [ ] Persist alignment metadata on Overlay.
  - Value: enables downstream analysis and model tuning.
  - Implementation: store inlier/match counts and a transform hash in `Overlay.summary`.
  - Files: apps/vision/worker/models.py, apps/vision/worker/jobs/block_overlay_generate.py

- [ ] Retry alignment with relaxed params on failure.
  - Value: improves success rate on low-feature blocks.
  - Implementation: attempt with higher n_features or relaxed thresholds when initial fails.
  - Files: apps/vision/worker/jobs/block_overlay_generate.py

## Job Orchestration
- [x] Fanout sheet/drawing overlay jobs.
  - Value: enables end-to-end pipeline for sheets/drawings.
  - Implementation: pair sheets/blocks, enqueue child jobs, publish to Pub/Sub.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py, apps/vision/worker/jobs/drawing_overlay_generate.py

- [x] Deduplicate in-flight fanout jobs.
  - Value: avoids duplicate overlays on retries.
  - Implementation: skip when existing job for same parent/target is queued/started/completed.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py, apps/vision/worker/jobs/drawing_overlay_generate.py

- [x] Track fanout stats and pairing method counts in job metadata.
  - Value: visibility into pairing quality and skipped reasons.
  - Implementation: include counts for queued/paired/skipped by method.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py, apps/vision/worker/jobs/drawing_overlay_generate.py

- [ ] Add publish batching/limits.
  - Value: prevents Pub/Sub spikes on large drawings.
  - Implementation: publish in chunks with sleep or use batch APIs.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py, apps/vision/worker/jobs/drawing_overlay_generate.py

- [ ] Add maximum overlays per sheet/drawing.
  - Value: prevents runaway fanout.
  - Implementation: cap the number of block pairs and log truncation.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py, apps/vision/worker/jobs/drawing_overlay_generate.py

- [ ] Track parent job completion based on child status.
  - Value: clearer pipeline semantics than "fanout complete".
  - Implementation: add a coordination job or periodic check to mark parent completed.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py, apps/vision/worker/jobs/drawing_overlay_generate.py, apps/vision/worker/utils/job_events.py

## Observability + Debugging
- [x] Emit warnings when pairing produces no matches.
  - Value: highlights data gaps or pairing issues early.
  - Implementation: log warning when no pairs are produced.
  - Files: apps/vision/worker/jobs/sheet_overlay_generate.py, apps/vision/worker/jobs/drawing_overlay_generate.py

- [x] Enrich block overlay job metadata with sheet/drawing context.
  - Value: ties overlay results back to parent entities.
  - Implementation: add optional sheet/drawing IDs to event metadata.
  - Files: apps/vision/worker/jobs/block_overlay_generate.py

- [ ] Add structured metrics for alignment time + memory.
  - Value: helps tune performance and detect regressions.
  - Implementation: measure durations and memory via `log_utils` helpers.
  - Files: apps/vision/worker/jobs/block_overlay_generate.py, apps/vision/worker/utils/log_utils.py

- [ ] Add sampling for overlay image inspection.
  - Value: quick sanity checks without full tracing.
  - Implementation: optional debug mode to write sample URIs or thumbnails.
  - Files: apps/vision/worker/jobs/block_overlay_generate.py

## Tests + Tooling
- [ ] Unit tests for block pairing strategies.
  - Value: guards against regression in pairing logic.
  - Implementation: test name/text/bounds/order matching cases.
  - Files: apps/vision/worker/tests/unit/*

- [ ] Unit tests for sheet pairing strategies.
  - Value: validates sheet pairing behavior for number/title/discipline.
  - Implementation: add fixture sheets and assert pair ordering.
  - Files: apps/vision/worker/tests/unit/*

- [ ] Integration test for block overlay generation.
  - Value: validates alignment fallback and output URIs.
  - Implementation: stub storage client and ensure overlay URIs set.
  - Files: apps/vision/worker/tests/integration/*

- [ ] CLI script to run a single overlay job end-to-end.
  - Value: fast manual debugging.
  - Implementation: simple script that loads a job payload and runs handler.
  - Files: apps/vision/worker/scripts/*
