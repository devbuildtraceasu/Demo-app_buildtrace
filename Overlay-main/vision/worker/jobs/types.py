"""Job type constants for the vision worker."""


class JobType:
    # Drawing processing
    DRAWING_PREPROCESS = "vision.drawing.preprocess"
    SHEET_PREPROCESS = "vision.sheet.preprocess"

    # Overlay generation
    DRAWING_OVERLAY_GENERATE = "vision.drawing.overlay.generate"
    SHEET_OVERLAY_GENERATE = "vision.sheet.overlay.generate"
    BLOCK_OVERLAY_GENERATE = "vision.block.overlay.generate"
    MANUAL_ALIGN = "vision.block.overlay.manual_align"

    # Analysis
    CHANGE_DETECT = "vision.overlay.change.detect"
    CLASH_DETECT = "vision.overlay.clash.detect"
    COST_ANALYSIS = "vision.overlay.cost.analysis"
    SHEET_ANALYSIS = "vision.sheet.analysis"

    # Legacy aliases
    OVERLAY_CHANGE_DETECT = CHANGE_DETECT
    OVERLAY_CLASH_DETECT = CLASH_DETECT


__all__ = ["JobType"]
