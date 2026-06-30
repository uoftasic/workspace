# asic-edu-workbench

The **shared open-source EDA workbench** for the
[UofT ASIC Internal Education Initiative](https://uoftasic.com/). Clone it once during
[IC101](https://uoftasic.com/ic101-docs/) and reuse it for every tool-heavy course.

> 📖 **All course manuals and the full setup guide are online:** **https://uoftasic.com/**

## Quick start

1. Install **Docker Desktop** (see the IC101 setup guide for per-OS instructions).
2. Clone this repository.
3. Start the environment:
   - **macOS / Linux:** `./scripts/start_vnc.sh`
   - **Windows:** double-click `scripts/start_vnc.bat`
4. Open **http://localhost/** in your browser (password `abc123`) for the EDA desktop.
5. In the desktop terminal, verify your tools:
   ```bash
   . /foss/designs/common/.designinit
   /foss/designs/scripts/smoke_test.sh
   ```

## What's here

| Path | Purpose |
|------|---------|
| `.devcontainer/` | VS Code Dev Containers config |
| `scripts/` | Container launch & helper scripts (noVNC, X11, clipboard, smoke test) |
| `common/` | Shared environment (`.designinit`, `xschemrc`) |
| `pdk/` | Pinned SKY130 PDK version (`volare.lock`) |
| `modules/` | Per-course starter files (`mod <name>` to enter one) |
| `docker/` | noVNC landing page |

This generalizes the per-course workbench pattern: **one** image, **one** PDK pin, shared by every
course. The toolchain is the IIC-OSIC-TOOLS image maintained by IIC-JKU.

Course manuals, troubleshooting, and labs are on the docs site linked above.
