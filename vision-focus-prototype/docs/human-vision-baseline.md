# Human Vision Baseline

This document gives the prototype a first science-based starting point for foveated resolution.

## Important idea

The eye does not see the whole visual field at one constant resolution.

The sharpest detail is at the gaze point. Resolution then falls off with eccentricity, which means the visual angle away from the gaze point.

## Useful starting numbers

| Area | Approximate eccentricity | Practical meaning |
| --- | ---: | --- |
| Foveal center | 0 to about 1 degree radius | Highest detail |
| Foveal vision | about 1.5 to 2 degrees diameter | Sharp central vision, often around 20/20 or better |
| Around 2 degrees away | about 2 degrees radius | About half foveal acuity |
| Around 4 degrees away | about 4 degrees radius | About one third foveal acuity |
| Around 6 degrees away | about 6 degrees radius | About one fourth foveal acuity |
| Around 30 degrees away | about 30 degrees radius | About one sixteenth foveal acuity |

## Pixels per degree

Visual resolution is usually easier to describe as pixels per degree instead of "1080p" or "1000p".

Common reference points:

- 20/20 vision is often approximated as 60 pixels per degree.
- Newer display/vision research reports foveal achromatic limits around 94 pixels per degree, with some people higher.

For this prototype, a reasonable starting target is:

```text
foveal center: about 94 pixels per degree
```

Then resolution falls away from the gaze point.

## Starting falloff model

A simple acuity falloff approximation is:

```text
relative_acuity = 2 / (2 + eccentricity_degrees)
```

Examples:

| Eccentricity | Relative acuity | If center is 94 ppd |
| ---: | ---: | ---: |
| 0 degrees | 1.00x | 94 ppd |
| 2 degrees | 0.50x | 47 ppd |
| 4 degrees | 0.33x | 31 ppd |
| 6 degrees | 0.25x | 24 ppd |
| 10 degrees | 0.17x | 16 ppd |
| 20 degrees | 0.09x | 9 ppd |
| 30 degrees | 0.06x | 6 ppd |

## Why this matters for the product

The prototype should not think in fixed percentages of the image first.

Instead, it should ask:

1. What is the camera field of view?
2. Where is the focus point?
3. How many visual degrees away is each part of the image?
4. What resolution is useful at that distance?

This lets the system create an image that is closer to how human vision spends detail.

## Sources to compare later

- Human foveal vision is commonly described as the central 1.5 to 2 degrees of the visual field.
- Peripheral acuity is commonly described as declining rapidly with eccentricity, with examples around half acuity at 2 degrees and one sixteenth at 30 degrees.
- 20/20 vision is commonly approximated as 60 pixels per degree.
- Recent display-resolution research reports foveal achromatic limits around 94 pixels per degree.
