# Product Notes

These notes are for thinking clearly about the product before spending serious money.

## Core hypothesis

Many vision AI systems do not need every pixel of every frame at full resolution.

The product idea is to send an eye-like version of the full scene:

1. highest detail near the focus point,
2. medium detail around that focus area, and
3. lower detail in the far periphery.

This keeps the whole scene visible to the downstream AI, while spending the most resolution where detail is most likely to matter. If this preserves useful understanding while reducing the amount of visual detail processed, the system may become cheaper, faster, or both.

## First prototype goal

The first Python prototype should prove the smallest useful loop:

```text
input image
  -> low-resolution overview
  -> focus-region selection
  -> high-resolution crop
  -> foveated full-frame image
  -> debug image showing what was selected
```

## What must be tested later

- Does the method reduce input size enough to matter?
- Does it improve latency or frames per second?
- Does it preserve accuracy for the target task?
- What important things does it miss?
- Does it work better with one crop or multiple crops?
- Does a foveated full-frame image perform better than separate overview-plus-crop input?
- What resolution falloff best matches useful human-like clarity?
- Should focus be based on saliency, motion, objects, model uncertainty, or task-specific rules?

## Patent-sensitive thinking

Do not publish the most specific technical details before deciding whether to file a provisional patent application.

Ideas to document privately:

- how focus regions are selected
- how focus changes over time in video
- how the system handles uncertainty
- how many high-resolution regions are selected
- how the method changes for different industries
- how cost, latency, and accuracy are measured

This file is not legal advice. It is a product planning document.
