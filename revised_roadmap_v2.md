# A5 Revised Roadmap v2: AgMultida Alignment

## Critical Misalignment Fix
Current repo state: 'water stress binary'.
Target state: 3 rice targets (Blast, BPH, N-Def).

## Architecture & Data
*   **Stack:** Keep EfficientNetB3 + GRU + CrossAttn.
*   **Model Head:** Switch from binary to multi-task head (3 classes).
*   **Labeling Strategy:** Multi-label expert-aligned.
*   **Green Ag Goals:** Align metrics with Water + IPM (Integrated Pest Management) optimization.

## Fast-Track 14-Day Timeline

### Phase 0: Triage & Config (Days 1-2)
*   Purge binary classification logic.
*   Update config files for 3-class target.

### Phase 1: Data Strategy (Days 3-5)
*   Implement multi-label expert-aligned pipelines.
*   Ingest Blast, BPH, and N-Def datasets.

### Phase 2: Model Adaptation (Days 6-8)
*   Retain EfficientNetB3+GRU+CrossAttn backbone.
*   Attach and initialize 3-class multi-task head.

### Phase 3: Green Ag Integration (Days 9-10)
*   Embed Water and IPM constraint metrics into loss/evaluation.
*   Tune for resource efficiency.

### Phase 4: Training & Validation (Days 11-12)
*   Execute training loop on 3-target data.
*   Validate multi-class performance metrics.

### Phase 5: Handoff & Freeze (Days 13-14)
*   Finalize model weights.
*   Verify 14-day completion gates.