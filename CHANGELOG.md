# Changelog

All notable changes to this project are documented in this file.

## [1.0.3] - 2026-04-10

### Added

- Initial public release of `Scan Surface Align`.
- Right-side Blender `N` panel: `View3D > Scan Align`.
- Storage for two polygon sets: `Side 1` and `Side 2`.
- Manual alignment to `X`, `Y`, and `Z`.
- `AUTO AXES` and `AUTO ALIGN`.
- `Quick Align` for the current polygon selection.
- `Rotate` and `Bake Rotation` modes.
- Optional `Center Origin` after alignment.
- Hotkeys for side storage and alignment actions.
- Release documentation in `README.md`.
- Open-source `GPL-3.0-or-later` license.
- Project logo asset in `SVG`.

### Changed

- Updated addon metadata with author, studio, website, Telegram, and Blender `5.1`.
- Expanded README with Russian and English descriptions.
- Added media placeholders for GIFs and screenshots.

### Fixed

- Fixed compatibility with Blender `5.1` by removing deprecated `mesh.calc_normals()` usage.
- Fixed `AUTO ALIGN` errors when the stored object was not available in the active `View Layer`.
- Improved `Quick Align` so repeated `X`, `Y`, or `Z` presses flip the model by 180 degrees.
