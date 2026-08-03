# workspace

The **shared open-source EDA workspace** for the
[UofT ASIC Internal Education Initiative](https://edu.uoftasic.com/). Clone it once during
[IC101](https://uoftasic.github.io/ic101/) and reuse it for every tool-heavy course.

> 📖 **Course manuals:** **https://edu.uoftasic.com/** · **IC101 setup:** **https://uoftasic.github.io/ic101/**

> Local folder name: **`workspace`**. GitHub: [`uoftasic/workspace`](https://github.com/uoftasic/workspace).

## Quick start

1. Install **Docker Desktop** (see the [IC101 Docker guide](https://uoftasic.github.io/ic101/#/guide/install-docker)).
2. Clone into a folder named `workspace`:
   ```bash
   git clone https://github.com/uoftasic/workspace.git workspace
   cd workspace
   ```
3. Start the environment:
   - **macOS / Linux:** `./scripts/start_vnc.sh`
   - **Windows:** double-click `scripts/start_vnc.bat`
4. Open **http://localhost/** in your browser (password `abc123`) for the EDA desktop.
5. In the desktop terminal, verify your tools:
   ```bash
   . /foss/designs/common/.designinit   # load env + mod helpers (once per shell)
   /foss/designs/scripts/smoke_test.sh
   mod                                 # list course modules under modules/
   ```

Later courses: `mod add <course>` clones `github.com/uoftasic/<course>` into `modules/<course>`
(for example `mod add ad101`). See [`modules/README.md`](modules/README.md).

## What's here

| Path | Purpose |
|------|---------|
| `.devcontainer/` | VS Code Dev Containers config |
| `scripts/` | Container launch & helper scripts (noVNC, X11, clipboard, smoke test, `add_module.sh`) |
| `common/` | Shared environment (`.designinit` with `mod`, `xschemrc`) |
| `pdk/` | Pinned SKY130 PDK version (`volare.lock`) |
| `modules/` | Per-course starter files (`mod` / `mod add` / `mod <name>`) |
| `docker/` | noVNC landing page |

One image, one PDK pin, shared by every course. The toolchain is the IIC-OSIC-TOOLS image maintained by IIC-JKU.

Course manuals, troubleshooting, and labs are on the docs site linked above.
