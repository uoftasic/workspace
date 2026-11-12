# workspace

The shared open-source EDA workspace ([`uoftasic/workspace`](https://github.com/uoftasic/workspace)) for the [UofT ASIC Internal Education Initiative](https://edu.uoftasic.com/). You clone it once during [IC101](https://uoftasic.com/ic101/) and reuse it for every tool-heavy course.

Every course's manual, with its troubleshooting and labs, is linked from https://edu.uoftasic.com/. The IC101 manual at https://uoftasic.com/ic101/ covers setting up this workspace.

## Quick start

1. Install Docker Desktop. The [IC101 Docker guide](https://uoftasic.com/ic101/#/guide/install-docker) walks you through it.
2. Clone this repo into a folder named `workspace`:
   ```bash
   git clone https://github.com/uoftasic/workspace.git workspace
   cd workspace
   ```
3. With Docker Desktop running, start the environment. On macOS or Linux, run `./scripts/start_vnc.sh`. On Windows, double-click `scripts/start_vnc.bat`. The script pulls the IIC-OSIC-TOOLS image (`hpretl/iic-osic-tools:2026.08`) and starts a container named `asic-edu-osic`, with this repo mounted at `/foss/designs`. Running it again replaces the container with a fresh one.
4. Open http://localhost/ in your browser. You get the EDA desktop, a Linux desktop running in the browser through noVNC. If it asks for a password, it's `abc123`.
5. In a terminal on the desktop, check your tools:
   ```bash
   . /foss/designs/common/.designinit   # load the environment: SKY130 PDK and the mod command
   /foss/designs/scripts/smoke_test.sh
   mod                                 # list the course modules under modules/
   ```
   A passing smoke test ends with `=== All checks passed ===`.

New terminals load the environment on their own: the image runs the `.designinit` at the repo root, which sources `common/.designinit`. The first line above is a safety net for a terminal that didn't, and running it twice does no harm.

For later courses, `mod add <course>` clones `github.com/uoftasic/<course>` into `modules/<course>`, for example `mod add ad101`. See [`modules/README.md`](modules/README.md).

## What's in this repo

| Path | Purpose |
|------|---------|
| `.designinit` | Run by the image in every new terminal; it sources `common/.designinit` |
| `.devcontainer/` | VS Code Dev Containers config |
| `scripts/` | Scripts to launch the container, and helpers (noVNC, X11, clipboard, smoke test, `add_module.sh`) |
| `common/` | Shared environment: `.designinit` with `mod`, and `xschemrc` |
| `pdk/` | `volare.lock`, which records the SKY130 PDK and image tag |
| `modules/` | One folder per course (`mod`, `mod add <name>`, `mod <name>`) |
| `docker/` | noVNC landing page |

Every course that uses the workspace runs the same image and the same PDK. The toolchain is the IIC-OSIC-TOOLS image, maintained by IIC-JKU.
