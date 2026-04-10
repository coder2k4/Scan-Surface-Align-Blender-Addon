# 🇬🇧 Scan Surface Align Guide

`Scan Surface Align` helps you quickly orient scans, hard-surface parts, and uneven meshes in Blender for editing, cleanup, retopology, and 3D printing.

## 🧭 Addon Location

You can find the panel here:

`View3D > N-panel > Scan Align`

## 🧩 Core Workflows

The addon supports two main workflows:

### 1. Manual alignment from selected polygons

Use this when you know exactly which surface should face `X`, `Y`, or `Z`.

Best for:

- aligning scan fragments
- orienting a mesh to world axes
- precise manual control

### 2. Automatic print-oriented alignment

Use this when you want the addon to place the mesh into a practical support position automatically.

Best for:

- 3D-print preparation
- finding the best flat support surface
- quick orientation without selecting polygons

## 🔘 Button Reference

### 📥 Store Selected Faces

Stores the current polygon selection as `Side 1` or `Side 2`.

Use it:

- in `Edit Mode`
- after selecting the surface you want to align

### 👁 Select Stored Faces

Restores the previously stored polygon selection for a side.

Useful when:

- you want to review the stored area
- you want to align the same side again

### 🗑 Clear Stored Faces

Clears the stored polygons for the selected side.

Use it:

- when you want to store another surface
- when the wrong area was saved

### 🧭 X / Y / Z

These buttons define the target world axis for the stored side.

Example:

- choose `Z` when the surface should become horizontal
- choose `X` or `Y` for side-facing alignment

### 🌐 Auto Axes

Automatically picks the closest world axes for already stored sides.

Use it:

- after saving `Side 1` or both sides
- when you want Blender to choose the best axis match

### 🧱 ALIGN

Performs manual alignment using stored sides and selected axes.

Use it like this:

1. store `Side 1`
2. optionally store `Side 2`
3. choose `X`, `Y`, or `Z`
4. press `ALIGN`

### 🤖 AUTO ALIGN

Analyzes the active mesh automatically and finds the best flat support surface.

Important:

- no polygon selection is required
- works from the active object
- intended for print-friendly orientation

Use it like this:

1. select the object in `Object Mode`
2. press `AUTO ALIGN`
3. if needed, press `FLIP`
4. then optionally press `TO FLOOR`

### 🔄 FLIP

Rotates the mesh by `180°` after `AUTO ALIGN`.

Use it:

- when auto-alignment is almost correct but facing the wrong direction
- when you want a quick inverted orientation without manual rotation

### ⬇️ TO FLOOR

Moves the mesh to the floor plane (`Z = 0`) and behaves differently depending on the mode.

In `Object Mode`:

- it uses the lowest vertex of the mesh
- the object is moved so the lowest part rests on the grid

In `Edit Mode`:

- it uses the selected polygon plane
- the object is moved so the selected surface reaches `Z = 0`

Use it:

- after `AUTO ALIGN`
- after manual `ALIGN`
- before export
- before checking print-bed placement

### ⚡ Quick Align

Quickly aligns the current selection in `Edit Mode`.

Buttons:

- `Auto` - chooses the nearest axis automatically
- `X` - aligns to world `X`
- `Y` - aligns to world `Y`
- `Z` - aligns to world `Z`

Special behavior:

- pressing the same axis again flips the mesh by `180°`

### 🧰 Rotate / Bake Rotation

`Rotate`:

- rotates the object only
- keeps the object transform as rotation

`Bake Rotation`:

- applies the rotation to the mesh
- resets the object rotation

Use `Bake Rotation` when:

- you want the orientation permanently applied
- you want a clean export state

### 🎯 Center Origin

Moves the origin toward the center of the geometry after alignment.

Useful when:

- you want a cleaner pivot
- you plan to rotate the object again later

## 🛠 Recommended Workflows

### Fast print preparation

1. Switch to `Object Mode`
2. Select the object
3. Press `AUTO ALIGN`
4. Press `FLIP` if needed
5. Press `TO FLOOR`

### Precise manual alignment

1. Switch to `Edit Mode`
2. Select the target polygons
3. Press `Store Selected Faces`
4. Choose `X`, `Y`, or `Z`
5. Press `ALIGN`
6. Press `TO FLOOR` if needed

### Fast local reorientation

1. Switch to `Edit Mode`
2. Select polygons
3. Use `Quick Align`
4. Press the same axis again if you want to flip the result

## ⌨️ Hotkeys

- `Ctrl + Alt + 1` - store `Side 1`
- `Ctrl + Alt + 2` - store `Side 2`
- `Ctrl + Alt + X / Y / Z` - `Quick Align`
- `Ctrl + Alt + A` - `ALIGN`
- `Ctrl + Shift + Alt + A` - `AUTO ALIGN`

## 📌 Practical Tip

A reliable print-prep flow is:

1. `AUTO ALIGN`
2. `FLIP` if needed
3. `TO FLOOR`
4. `Bake Rotation` if you want the orientation applied permanently

## 🔗 Useful Links

- [Main Project Page](../README.md)
- [Русское руководство](GUIDE_RU.md)
- [Media Gallery](media/README.md)
