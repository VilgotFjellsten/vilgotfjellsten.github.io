# Product Notes

These notes are for thinking clearly about the product before spending serious money.

## Core hypothesis

Many vision AI systems do not need every pixel of every frame at full resolution.

The product idea is to send:

1. a low-resolution view of the whole scene, and
2. one or more high-resolution focus regions that likely contain the most useful detail.

If this keeps the useful information while reducing the amount of visual data sent to the main AI model, the system may become cheaper, faster, or both.

## First prototype goal

The first Python prototype should prove the smallest useful loop:

```text
input image
  -> low-resolution overview
  -> focus-region selection
  -> high-resolution crop
  -> debug image showing what was selected
```

## What must be tested later

- Does the method reduce input size enough to matter?
- Does it improve latency or frames per second?
- Does it preserve accuracy for the target task?
- What important things does it miss?
- Does it work better with one crop or multiple crops?
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
