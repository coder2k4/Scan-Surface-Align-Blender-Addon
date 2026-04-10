# Scan Surface Align

Blender addon for scan cleanup, mesh orientation, and quick preparation for 3D printing.

Author: `Glazyrin Alexey Sergeevich`  
Studio: `3dpotok.ru`  
Telegram: `@standalone2k`  
Website: `https://3dpotok.ru`  
Version: `1.0.5`  
Blender: `5.1`

## Overview

`Scan Surface Align` helps rotate scanned meshes, hard-surface parts, and irregular models into clean working positions.

The addon supports two different workflows:

- Manual alignment by selected polygons
- Automatic print-oriented alignment without polygon selection

It works from the right-side `N` panel in `View3D > Scan Align`.

## Кратко На Русском

`Scan Surface Align` помогает быстро выровнять скан, деталь или сложный меш в удобное рабочее положение.

Есть два основных режима:

- ручное выравнивание по выбранным полигонам
- автоматическое выравнивание для 3D-печати без выделения полигонов

Если нужен стабильный вариант укладки модели на стол или на стол печати, достаточно выбрать объект и нажать `AUTO ALIGN`. Если после этого нужно перевернуть модель, используйте `FLIP`.

## What's New In 1.0.4

- `AUTO ALIGN` now works on the whole active mesh and does not require selected polygons
- `AUTO ALIGN` searches for the best flat support surface for placing the model on the print bed
- Added `FLIP` button after `AUTO ALIGN`
- `Store Selected Faces` no longer changes the axis you selected manually

## What's New In 1.0.5

- Added `TO FLOOR`
- In `Object Mode`, `TO FLOOR` moves the mesh down using the lowest vertex
- In `Edit Mode`, `TO FLOOR` moves the object down using the selected polygon plane
- Improved axis controls with dedicated `X`, `Y`, `Z` buttons and axis icons

## Main Features

- Store two polygon sets: `Side 1` and `Side 2`
- Align stored sides manually to `X`, `Y`, or `Z`
- `AUTO AXES` for manual side-based alignment
- `AUTO ALIGN` for automatic print support orientation
- `TO FLOOR` for placing the mesh on the ground plane
- `FLIP` to turn the model 180 degrees after auto alignment
- `Quick Align` for the current polygon selection
- Repeating `Quick Align` on the same axis flips the model by 180 degrees
- `Rotate` and `Bake Rotation` modes
- Optional `Center Origin`

## Workflow

### 1. Manual Alignment By Polygons

Use this when you want precise control over how a specific surface should be aligned.

1. Enter `Edit Mode`
2. Select polygons for `Side 1`
3. Click `Store Selected Faces`
4. Choose the target axis manually: `X`, `Y`, or `Z`
5. Optionally store `Side 2`
6. Click `ALIGN`
7. If needed, click `TO FLOOR`

### 2. Automatic Alignment For 3D Printing

Use this when you want the addon to orient the mesh automatically for a stable print-bed position.

1. Select the mesh object
2. No polygon selection is required
3. Click `AUTO ALIGN`
4. The addon analyzes the active mesh and finds the best flat support surface
5. If needed, click `FLIP` to invert the model by 180 degrees
6. Click `TO FLOOR` if you want to place the result exactly on the floor plane

## To Floor

`TO FLOOR` works in two different ways:

- In `Object Mode`, it moves the object down until the lowest mesh vertex touches `Z = 0`
- In `Edit Mode`, it moves the object so the selected polygon plane is placed on `Z = 0`

## Quick Align

`Quick Align` works from the current polygon selection in `Edit Mode`.

- `Auto` chooses the closest axis automatically
- `X`, `Y`, `Z` align directly to the chosen world axis
- Pressing the same axis again flips the model by 180 degrees

## Hotkeys

- `Ctrl + Alt + 1` -> store `Side 1`
- `Ctrl + Alt + 2` -> store `Side 2`
- `Ctrl + Alt + X / Y / Z` -> `Quick Align`
- `Ctrl + Alt + A` -> `ALIGN`
- `Ctrl + Shift + Alt + A` -> `AUTO ALIGN`

## Interface

Sidebar location:

`View3D > N-panel > Scan Align`

Main controls:

- `Store Selected Faces`
- `ALIGN`
- `AUTO AXES`
- `AUTO ALIGN`
- `TO FLOOR`
- `FLIP`
- `Quick Align`

## Media

Preview:

![Preview](docs/media/preview-main.png)

Animated demos:

![Workflow Demo](docs/media/workflow.gif)

![Quick Align Demo](docs/media/quick-align.gif)

![Auto Align Demo](docs/media/auto-align.gif)

Detailed media page with descriptions:

[docs/media/README.md](docs/media/README.md)

Available files:

- `docs/media/preview-main.png`
- `docs/media/workflow.gif`
- `docs/media/quick-align.gif`
- `docs/media/auto-align.gif`

## Installation

1. Download the addon release archive
2. In Blender open `Edit > Preferences > Add-ons > Install...`
3. Select the addon zip file
4. Enable `Scan Surface Align`

## License

This project is licensed under the GNU General Public License v3.0 or later.

See [LICENSE](LICENSE).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Contacts

- Studio: `3dpotok.ru`
- Telegram: `@standalone2k`
- Website: `https://3dpotok.ru`
