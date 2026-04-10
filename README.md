# Scan Surface Align

Blender addon for scan cleanup, mesh orientation, and print-friendly alignment.

Author: `Glazyrin Alexey Sergeevich`  
Studio: `3dpotok.ru`  
Telegram: `@standalone2k`  
Website: `https://3dpotok.ru`  
Version: `1.0.6`  
Blender: `5.1`

## ✨ What This Addon Does

`Scan Surface Align` helps you:

- align scanned surfaces to world axes
- orient meshes for comfortable editing
- prepare objects for 3D printing
- quickly place models on the floor plane

It works from:

`View3D > N-panel > Scan Align`

## 📘 Guides

Choose the guide you prefer:

- 🇷🇺 [Русское руководство](docs/GUIDE_RU.md)
- 🇬🇧 [English Guide](docs/GUIDE_EN.md)
- 🖼 [Media Gallery](docs/media/README.md)

## 🚀 Main Features

- `ALIGN` for manual side-based alignment
- `AUTO ALIGN` for automatic print-oriented placement
- `TO FLOOR` for placing the mesh on `Z = 0`
- `FLIP` for rotating the result by `180°`
- `Quick Align` for fast local face alignment
- `Rotate / Bake Rotation`
- `Center Origin`
- side storage with `Side 1` and `Side 2`

## 🧭 Recommended Workflows

### 🧱 Manual Surface Alignment

1. Go to `Edit Mode`
2. Select the needed polygons
3. Press `Store Selected Faces`
4. Choose `X`, `Y`, or `Z`
5. Press `ALIGN`

### 🤖 Automatic Print Placement

1. Select the object
2. Press `AUTO ALIGN`
3. If needed, press `FLIP`
4. Press `TO FLOOR`

### ⚡ Fast Local Alignment

1. Select polygons in `Edit Mode`
2. Use `Quick Align`
3. Press the same axis again to flip by `180°`

## 🖼 Preview

![Preview](docs/media/preview-main.png)

## 🎞 Demos

![Workflow Demo](docs/media/workflow.gif)

![Quick Align Demo](docs/media/quick-align.gif)

![Auto Align Demo](docs/media/auto-align.gif)

## 📦 Installation

1. Download the latest addon archive
2. Open `Edit > Preferences > Add-ons > Install...`
3. Select the zip archive
4. Enable `Scan Surface Align`

## 🔗 Additional Project Files

- [Changelog](CHANGELOG.md)
- [License](LICENSE)
- [Media Gallery](docs/media/README.md)

## 📬 Contacts

- Studio: `3dpotok.ru`
- Telegram: `@standalone2k`
- Website: `https://3dpotok.ru`
