# Deer Repellent Enclosure Handoff

## Project files

- `deer_repellent_housing.scad` — parametric OpenSCAD source.
- `deer_repellent_body.stl` — enclosure body for slicing.
- `deer_repellent_lid.stl` — flat removable lid for slicing.

## Current design

- Enclosure shell dimensions: **175.5 × 127 × 36 mm** (length × depth × height). The dowel sleeves extend 15 mm below the shell, so the body STL's total Z extent includes those sleeves.
- Sized for a **159.5 × 49 mm** breadboard with 5 mm clearance at each end along its length and 3 mm enclosure walls.
- The PIR opening is **23 × 23 mm**, centered 18 mm above the base. This leaves 6.5 mm below and above the opening.
- The camera mounting opening is **8.5 × 8.5 mm**. The LED opening is circular; the buzzer uses five grille slots.
- Two exterior sleeves fit nominal **12.7 mm (½-inch) dowels**. Each sleeve has a 13.5 mm bore, 12 mm insertion depth, tapered closed end, and 3 mm roof. The sockets do not open into the enclosure interior.
- Four corner bosses provide lid screw locations. Their bores stop at the bosses and do not pass through the enclosure floor.
- The lid is a flat plate without a recessed locating section.
- Internal board supports and the USB-C opening are omitted.

## Parametric controls

Edit the dimensions and component positions near the top of `deer_repellent_housing.scad`. The `part` selector supports `"body"`, `"lid"`, and `"assembly"`. For STL export in OpenSCAD, select a part, render with **F6**, then use **File → Export → Export as STL**.

## Fit checks before printing

- Confirm that the 13.5 mm dowel sockets fit the actual dowels and printer. Adjust `dowel_socket_clearance` if needed.
- Confirm the camera board's 8.5 mm mounting footprint and required lens clearance.
- Confirm buzzer, LED, and PIR locations against the actual assembled electronics before printing the full enclosure.
- The STL meshes use faceted surfaces; circular features are modeled with 128 segments.
