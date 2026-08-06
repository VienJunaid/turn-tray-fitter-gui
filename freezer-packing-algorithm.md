# Freezer Packing Algorithm — Design Spec

## Overview

This document defines the algorithm for calculating how many objects (cylinders,
cubes, rectangular prisms) can fit inside a cylindrical freezer, given:

- Mandatory spacing between all objects and the freezer wall
- A physical vertical obstruction (handle bar) near the top
- Horizontal packing followed by vertical stacking (layer-based approach)

This spec is meant to be handed directly to an AI coding assistant (e.g. Claude in
an IDE) as ground-truth context before implementation begins.

---

## 1. Freezer Definition

```
R = freezer interior radius (inches)
H = freezer interior height (inches)
handle_bar_clearance = 1 inch   # vertical stack may not come within 1" of the top
```

### Data source: JSON file (not hardcoded)

Freezer data (`R`, `H`, and any other freezer-specific attributes like model name/ID,
`handle_bar_clearance` if it varies per model, etc.) will be stored in a separate
JSON file, not hardcoded into the Python script. The script should look up the
relevant freezer's data from this JSON file at runtime (e.g. by freezer ID/name)
rather than embedding freezer dimensions directly in code.

> Status: JSON file has not been created yet. Schema/field names are TBD and
> should be finalized before implementation — do not assume a structure yet.
> The Python script's freezer-loading function should be written against
> whatever schema is finalized (e.g. `load_freezer(freezer_id, json_path) -> {R, H, handle_bar_clearance, ...}`),
> keeping the lookup logic isolated in its own function so the JSON schema can
> change without affecting the packing algorithm itself.

**Effective usable height:**

```
H_usable = H - handle_bar_clearance
```

All vertical stacking calculations use `H_usable`, not `H`.

---

## 2. Global Spacing Rule

```
GAP = 0.125 inches   # 1/8" required gap between:
                      #   - object and object (horizontally)
                      #   - object and object (vertically, between stacked layers)
                      #   - object and the freezer wall (horizontally)
```

The gap is **not** optional and must be baked into every dimension used in
packing math — not applied as an afterthought/subtraction at the end. This
matters because packing counts are non-linear (an extra 1/8" per object compounds
across many objects), so gap must be added to each object's *effective* footprint
size before running any packing calculation.

### Effective radius available for packing

```
R_eff = R - GAP     # object surfaces can't touch the wall either
```

### Effective object dimensions (add gap as a "halo" around each object)

For packing calculations, treat every object as if it were slightly larger than
its real size — this guarantees the true 1/8" clearance between any two adjacent
objects and between an object and the wall.

```
effective_radius(r)      = r + GAP/2      # cylinder objects
effective_length(l)      = l + GAP        # rect prism / cube footprint
effective_width(w)       = w + GAP
effective_side(s)        = s + GAP        # cube special case (l = w = s)
effective_height(h)      = h + GAP        # vertical stacking spacing
```

> Why `GAP/2` for cylinder radius vs. full `GAP` for rect edges: two adjacent
> circles need `GAP` total distance between their surfaces, which is naturally
> achieved by giving each circle a `GAP/2` "halo" radius increase. Rectangles are
> packed on a grid by full edge length, so the full `GAP` is added directly to
> each side to guarantee `GAP` spacing between neighboring rectangle edges.

---

## 3. Horizontal Expansion (packing the circular cross-section)

Regardless of shape, horizontal packing produces an integer count:
`objects_per_layer`.

### 3a. Cylinders → Circle-in-circle packing

```
r_eff = r + GAP/2

Ring-based placement:
  ring 0: 1 object at center (if r_eff <= R_eff)
  ring k: placed at radius r_k, count_k = floor( (2 * pi * r_k) / (2 * r_eff) )
  stop adding rings once r_k + r_eff > R_eff

objects_per_layer = sum of all ring counts that fit
```

### 3b. Cubes and Rectangular Prisms → Rectangle-in-circle packing

```
l_eff = l + GAP
w_eff = w + GAP        # for cubes, l_eff = w_eff = s + GAP

Grid-scan placement:
  - lay a grid over the cross-section, spaced l_eff (x-axis) by w_eff (y-axis)
  - try a few grid offsets (e.g. origin-centered, and shifted by half-cell)
    and keep whichever offset yields the highest valid count
  - for each candidate cell position, the rectangle is valid only if
    ALL FOUR CORNERS satisfy:
        sqrt(x^2 + y^2) <= R_eff

objects_per_layer = count of valid grid cells (best offset)
```

### 3c. Mandatory rounding rule

**After computing `objects_per_layer` for ANY shape, always round down by 1
additional unit** (beyond normal floor/integer truncation) as a safety margin:

```
objects_per_layer_final = max(0, floor(objects_per_layer) - 1)
```

This applies uniformly to cylinders, cubes, and rectangular prisms. This is a
deliberate real-world safety buffer (accounts for imperfect placement, handling
tolerance, non-rigid packaging, etc.) and is **not** the same as normal
mathematical floor rounding — it is an explicit "minus 1" on top of it.

---

## 4. Vertical Expansion (stacking layers)

```
h_eff = object_height + GAP

num_layers = floor( H_usable / h_eff )
```

Where `H_usable = H - handle_bar_clearance` (see Section 1). The stack must never
extend past `1 inch below the top handle bar` — this is the hard vertical
constraint, and it is enforced by computing layers against `H_usable`, not the
raw freezer height `H`.

> Note: unlike the horizontal case, there is **no additional "-1" safety
> rounding** applied vertically — `floor()` alone is the rule for `num_layers`,
> since the handle-bar clearance already provides the safety margin vertically.
> (Flag this assumption — confirm before implementation if a vertical safety
> buffer beyond the handle bar clearance is also wanted.)

---

## 5. Combining Horizontal + Vertical → Total Capacity

```
total_fit = objects_per_layer_final * num_layers
result     = min(total_fit, quantity_requested)
leftover   = max(0, quantity_requested - total_fit)
```

---

## 6. Shape Normalization Table

All three shapes reduce to a common "footprint + height" model before packing:

| Shape       | Footprint Type | Footprint Dims (effective)      | Height (effective) |
|-------------|-----------------|----------------------------------|---------------------|
| Cylinder    | circle          | `r_eff = r + GAP/2`              | `h + GAP`           |
| Cube        | rectangle       | `l_eff = w_eff = s + GAP`        | `s + GAP`           |
| Rect Prism  | rectangle       | `l_eff = l + GAP`, `w_eff = w + GAP` | `h + GAP`        |

This means the algorithm only needs **two** horizontal-packing functions total
(circle-in-circle, rectangle-in-circle) — cubes reuse the rectangle-in-circle
function with `l = w`.

---

## 7. Orientation Assumption (v1 scope)

- **Cylinders**: upright only (footprint = circle of radius `r`, height = `h`).
  Sideways cylinders are out of scope for v1.
- **Rect prisms**: orientation is either user-specified, or defaults to placing
  the smallest dimension as the vertical height (maximizes number of layers).
  *(Confirm this default with the user before implementing — not yet finalized.)*
- **Cubes**: orientation-invariant, no decision needed.

---

## 8. "Turn Tray" Note (future scope — NOT implemented in v1)

A turn tray (like a lazy-susan-style rack) can be sliced into wedges in two ways:
- **Horizontally** (like cutting a pie into a top layer / bottom layer)
- **Radially** (like cutting a pie into wedge slices from the center out)

For v1, we are treating every turn tray as **a single tray cut straight through
the middle** (i.e., one flat horizontal layer, no radial wedge subdivision).
Radial/wedge-based slicing is a future enhancement and should NOT be built into
the v1 algorithm — flag it as a placeholder for later, but keep v1's packing
logic simple and layer-based only.

---

## 9. Function Boundaries (for implementation)

```
load_freezer(freezer_id, json_path) -> {R, H, handle_bar_clearance, ...}   # schema TBD

normalize_to_footprint(object_type) -> (footprint_type, footprint_dims_eff, height_eff)

pack_circles_in_circle(R_eff, r_eff) -> count            # ring-based
pack_rects_in_circle(R_eff, l_eff, w_eff) -> count        # grid-scan, multi-offset

apply_horizontal_safety_margin(count) -> count            # the mandatory "-1" rule

objects_per_layer(footprint_type, footprint_dims_eff, R_eff) -> count
layers_available(H_usable, height_eff) -> count

allocate_single_type(freezer, object_type) -> {fit, leftover}
allocate_multi_type(freezer, list_of_object_types) -> {per_type_results, totals}
```

---

## 10. Inputs Summary (for reference)

**Freezer (fixed, provided once):**
```
R  = radius (inches)
H  = height (inches)
handle_bar_clearance = 1 inch   (constant)
GAP = 0.125 inches              (constant)
```

**Per object request (user provides):**
```
shape: "cylinder" | "cube" | "rect_prism"
dimensions:
  cylinder    -> (r, h)
  cube        -> (s)
  rect_prism  -> (l, w, h)
quantity_requested: integer
```

---

## 11. Open Questions to Confirm Before Coding

1. Rect prism default orientation (smallest side up vs. user-specified) — not
   yet finalized.
2. Whether a vertical safety margin (beyond the 1" handle bar clearance) is also
   desired, similar to the horizontal "-1" rule.
3. Multi-type allocation strategy: whole-layer-per-type (simple, v1 default) vs.
   mixed-type-per-layer (harder, marginal gain) — confirm whole-layer approach
   is acceptable for v1.
4. Freezer JSON file schema — not yet created. Needs field names/structure
   decided (e.g. freezer ID, R, H, handle_bar_clearance, any other metadata)
   before `load_freezer()` can be implemented.
