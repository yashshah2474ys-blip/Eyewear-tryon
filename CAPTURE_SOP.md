# LENSFIT 3D — Eyewear Photo Capture SOP
**Version 1.0 | Gold-Standard Protocol for Photogrammetry Reconstruction**

---

## Overview

This protocol produces a 25-image capture set optimized for COLMAP Structure-from-Motion reconstruction. Following it precisely determines the quality ceiling of your 3D model. Do not skip steps.

**Time required:** 15–20 minutes per frame  
**Equipment:** Smartphone (≥12MP, no Portrait mode) or DSLR  
**Minimum images required:** 21 (shots 01–21). Shots 22–25 are supplementary.

---

## Equipment & Setup

### Required
- Smartphone: OnePlus 12R (50MP), iPhone 13+, or any Android flagship
- Backdrop: A4/A3 paper printed in **18% grey** (`#767676`) — print at home
- Support: A wig stand, styrofoam ball on a stick, or foam block
- Lighting: Natural overcast daylight (window, no direct sun) OR a softbox

### Strongly Recommended (CRITICAL for quality)
- **Matte spray:** Krylon Matte Finish, Rust-Oleum Matte, or Aesub Blue
  - Eliminates specular reflections that break photogrammetry
  - Washes off with warm water — does not damage frames
  - Apply 30 min before shooting, let dry completely
- **Turntable:** Any lazy-susan from a kitchen store ($5–15)
- **Digital calipers:** For accurate measurements.json input

### Camera Settings
| Setting | Value |
|---|---|
| Mode | Manual or Pro |
| Portrait Mode | **OFF** |
| HDR | **OFF** |
| AI Enhancement | **OFF** |
| ISO | 100–200 |
| Shutter Speed | 1/60s+ (avoid motion blur) |
| White Balance | Daylight / 5500K |
| Focus | Lock on the bridge of the frame |
| Flash | **OFF** |
| Resolution | Maximum (do not reduce) |
| Format | JPEG (not HEIC/HEIF) |

---

## Anti-Reflection Treatment (MOST IMPORTANT STEP)

1. Place the frame on a clean surface
2. Shake matte spray can for 30 seconds
3. Hold can 25–30cm from frame, spray thin even coat
4. Wait 30 minutes for complete drying
5. The frame should look uniformly matte/flat — no shiny spots
6. Shoot your photos (see below)
7. After shooting: rinse with warm water, pat dry with microfiber cloth

> Without matte spray on glossy/metal frames, COLMAP cannot match features across views and reconstruction will fail. This is the single most impactful step.

---

## Background & Lighting Setup

1. Tape grey paper to a vertical surface (wall, box)
2. Place frame on support 10–15cm in front of the grey backdrop
3. Position your light source 45° to the left of the camera (softbox or window)
4. Optional: add a white foam reflector to the right to fill shadows
5. Frame should be evenly lit with **no harsh shadows on the backdrop**
6. The grey backdrop should appear uniform — no gradient

**Avoid:**
- White backgrounds (lens holes disappear)
- Black backgrounds (dark frames disappear)
- Backgrounds with patterns or text
- Mixed colour temperatures (warm + cool lights)

---

## Capture Distance

Stand/position camera **25–35 cm** from the frame (about 1 foot).  
The frame should fill **60–75%** of the frame width in each shot.

---

## 25-Shot Capture Protocol

Name your images exactly as shown below for the pipeline to validate them automatically.

### Turntable sequence (if using turntable)
Place frame on turntable, camera stays fixed. Rotate turntable between shots.

### Manual sequence
Move camera around the frame. Frame stays still on support.

---

### GROUP A — Front & Near-Front (5 shots)

| Shot | Filename | Description | Camera angle |
|---|---|---|---|
| 01 | `shot_01.jpg` | Front, straight on | 0° horizontal, 0° vertical |
| 02 | `shot_02.jpg` | Front, 5° right | 5° right, 0° vertical |
| 03 | `shot_03.jpg` | Front, 5° left | 5° left, 0° vertical |
| 04 | `shot_04.jpg` | Front, 5° up | 0° horizontal, +5° vertical |
| 05 | `shot_05.jpg` | Front, 5° down | 0° horizontal, -5° vertical |

### GROUP B — Right Side (5 shots)

| Shot | Filename | Description | Camera angle |
|---|---|---|---|
| 06 | `shot_06.jpg` | 45° right-front, eye level | 45° right, 0° |
| 07 | `shot_07.jpg` | 45° right-front, elevated | 45° right, +15° |
| 08 | `shot_08.jpg` | 45° right-front, depressed | 45° right, -15° |
| 09 | `shot_09.jpg` | Pure right profile | 90° right, 0° |
| 10 | `shot_10.jpg` | Right profile, elevated | 90° right, +15° |

### GROUP C — Left Side (5 shots)

| Shot | Filename | Description | Camera angle |
|---|---|---|---|
| 11 | `shot_11.jpg` | Right profile, depressed | 90° right, -15° |
| 12 | `shot_12.jpg` | 45° left-front, eye level | 45° left, 0° |
| 13 | `shot_13.jpg` | 45° left-front, elevated | 45° left, +15° |
| 14 | `shot_14.jpg` | 45° left-front, depressed | 45° left, -15° |
| 15 | `shot_15.jpg` | Pure left profile | 90° left, 0° |

### GROUP D — Top & Bottom (6 shots)

| Shot | Filename | Description | Camera angle |
|---|---|---|---|
| 16 | `shot_16.jpg` | Left profile, elevated | 90° left, +15° |
| 17 | `shot_17.jpg` | Left profile, depressed | 90° left, -15° |
| 18 | `shot_18.jpg` | Straight top (looking down) | 0°, +90° |
| 19 | `shot_19.jpg` | 45° above, front-facing | 0°, +45° |
| 20 | `shot_20.jpg` | Straight bottom (looking up) | 0°, -90° |
| 21 | `shot_21.jpg` | 45° below, front-facing | 0°, -45° |

> **Shots 01–21 are REQUIRED.** Processing will fail without them.

### GROUP E — Macro Close-Ups (4 shots, supplementary)

| Shot | Filename | Description | Notes |
|---|---|---|---|
| 22 | `shot_22.jpg` | Bridge close-up, front | Macro. Show bridge geometry clearly |
| 23 | `shot_23.jpg` | Left hinge close-up | Macro. Show hinge mechanism |
| 24 | `shot_24.jpg` | Right hinge close-up | Macro. Show hinge mechanism |
| 25 | `shot_25.jpg` | Scale reference | Frame next to a ruler or known-width card |

**Shot 25 (Scale Reference):** Place the frame next to a printed reference card of known width (e.g., a credit card = 85.6mm wide). Take a straight-on front shot. This allows visual verification of the scale calibration.

---

## Quality Checklist (Before Uploading)

Review each shot before moving on:

- [ ] Frame fills 60–75% of image width
- [ ] Backdrop is uniform grey — no shadows falling on it
- [ ] No motion blur (check zoom in to 100%)
- [ ] No mirror reflections visible on lenses or metal parts
- [ ] Frame is same position in every shot (don't move the frame, only the camera)
- [ ] Temples are OPEN and horizontal for all Group A–D shots
- [ ] No fingers/hands visible in frame

---

## Measurements.json — How to Measure

Use digital calipers (buy for $10–15 on Amazon). Measure in millimetres.

```
┌─────────────────────────────────────────────────────────────────┐
│   LEFT LENS    │  BRIDGE  │  RIGHT LENS                         │
│  lens_width_mm │bridge_mm │  lens_width_mm                      │
│←──────────────→│←────────→│←──────────────→                     │
│                                                                  │
│                total_front_width_mm                              │
│←────────────────────────────────────────────────────────────────→│
└─────────────────────────────────────────────────────────────────┘

temple_length_mm: From hinge screw to tip of temple arm

lens_height_mm: Tallest vertical dimension of the lens opening
```

Create `frames_input/{frame_id}/measurements.json`:
```json
{
  "frame_id": "your_frame_id",
  "name": "Brand Model Name",
  "lens_width_mm": 50,
  "bridge_width_mm": 18,
  "temple_length_mm": 140,
  "lens_height_mm": 38,
  "total_front_width_mm": 135,
  "material": "acetate_gloss",
  "color": "Black",
  "gender": "unisex",
  "shape": "wayfarer"
}
```

**Material values:** `acetate_gloss`, `acetate_matte`, `metal_polished`, `metal_brushed`, `titanium`, `plastic_matte`, `wood`

---

## Folder Structure

```
frames_input/
  your_frame_id/
    images/
      shot_01.jpg    ← Front
      shot_02.jpg    ← Front, slight right
      ...
      shot_21.jpg    ← Bottom view
      shot_22.jpg    ← Bridge macro (optional)
      shot_25.jpg    ← Scale reference (optional)
    measurements.json
```

---

## Processing

Once photos are captured and measurements.json is ready:

```bash
cd /path/to/Eyewear-tryon
python scripts/process_frame.py --frame-id your_frame_id
```

Output will appear in `frames_output/your_frame_id/model.glb`.

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| COLMAP registers < 15 cameras | Reflective surfaces / blurry shots | Apply matte spray, reshoot |
| Temple arms missing in output | Too thin for MVS depth estimation | Apply matte spray; use `--use-api` |
| Scale is wrong by 2× | Wrong measurement in JSON | Re-measure with calipers |
| Model too bumpy | Lighting not diffuse enough | Use a lightbox or move to overcast outdoor |
| Lens area solid/filled | Hole-closing algorithm too aggressive | Use `lens_transparent` material in admin |

---

## Time Estimates

| Task | Time |
|---|---|
| Setup (spray, backdrop, lighting) | 10 min |
| Photo capture (25 shots) | 10–15 min |
| Transfer photos to computer | 2 min |
| Pipeline processing (CPU) | 45–75 min (automated) |
| Review & upload to admin | 5 min |
| **Total per frame** | **~75–90 min** |

---

*LENSFIT 3D Pipeline v1.0 — For support, see README.md*
