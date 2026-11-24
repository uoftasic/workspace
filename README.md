# workspace

The shared open-source EDA workspace ([`uoftasic/workspace`](https://github.com/uoftasic/workspace)) for the [UofT ASIC Internal Education Initiative](https://edu.uoftasic.com/). You clone it once during [IC101](https://uoftasic.com/ic101/) and reuse it for every tool-heavy course.

Every course's manual, with its troubleshooting and labs, is linked from https://edu.uoftasic.com/. The IC101 manual at https://uoftasic.com/ic101/ covers setting up this workspace.

## Quick start

1. Install Docker Desktop. The [IC101 Docker guide](https://uoftasic.com/ic101/guide/install-docker.html) walks you through it.
2. Clone this repo into a folder named `workspace`:
   ```bash
   git clone https://github.com/uoftasic/workspace.git workspace
   cd workspace
   ```
3. With Docker Desktop running, start the environment. On macOS or Linux, run `./scripts/start_vnc.sh`. On Windows, double-click `scripts/start_vnc.bat`. The script pulls the IIC-OSIC-TOOLS image (`hpretl/iic-osic-tools:2026.08`) and starts a container named `asic-edu-osic`, with this repo mounted at `/foss/designs`. Running it again replaces the container with a fresh one. Your files under `/foss/designs` are kept, because they are the files in this folder on your computer; anything you saved elsewhere in the container is lost.
4. Open http://localhost/ in your browser. You get the EDA desktop, a Linux desktop running in the browser through noVNC. If it asks for a password, it's `abc123`.
5. In a terminal on the desktop, check your tools:
   ```bash
   . /foss/designs/common/.designinit   # load the environment: SKY130 PDK and the mod command
   /foss/designs/scripts/smoke_test.sh
   mod                                 # list the course modules under modules/
   ```
   A passing smoke test ends with `=== All checks passed ===`.

New terminals load the environment on their own: the image runs the `.designinit` at the repo root, which sources `common/.designinit`. The first line above is a safety net for a terminal that didn't, and running it twice does no harm.

### Apple silicon Macs: Apple's `container` instead of Docker Desktop

On an M-series Mac with macOS 26 or later, you can use Apple's container runtime, [`apple/container`](https://github.com/apple/container), instead of Docker Desktop. It runs each container in its own lightweight VM; Docker Desktop runs all of them inside one shared Linux VM. On an Intel Mac or an older macOS, use Docker Desktop and the Quick start above.

These steps replace Quick start steps 1, 3 and 4. Clone the repo first (Quick start step 2), and check your tools afterwards (Quick start step 5).

1. Install the signed `container-<version>-installer-signed.pkg` from the [releases page](https://github.com/apple/container/releases), or run `brew install container`.
2. Install the TigerVNC viewer: download `TigerVNC-<version>.dmg` from the newest folder of the [TigerVNC downloads](https://sourceforge.net/projects/tigervnc/files/stable/), open it, and drag **TigerVNC** into Applications.
3. From the workspace folder, run:
   ```bash
   ./scripts/start_vnc_apple.sh
   ```
   The first run starts Apple's container services, downloads a Linux kernel without asking, and pulls the image, which is about 7 GB. You get the same container as Quick start step 3 gives you: it's named `asic-edu-osic` and has this repo at `/foss/designs`. Running the script again replaces the container with a fresh one.
4. When the desktop is ready, the script opens TigerVNC on `localhost::5901`. Enter the password `abc123`. If no window opens, open TigerVNC from Applications and connect to `localhost::5901` yourself (two colons: `5901` is a port). TigerVNC connects to the container's VNC server directly, without a browser. It also passes text both ways between your Mac's clipboard and the desktop's, so you can paste into a desktop terminal with Ctrl+Shift+V. To use the browser instead, go to http://localhost:8080/ (not port 80, which Apple's runtime can only use with root), or start with `VNC_CLIENT=browser ./scripts/start_vnc_apple.sh` and the script opens it for you.

macOS's own Screen Sharing app can also connect, but it can't paste from your Mac into this desktop, which is why the script uses TigerVNC.

The container gets half your Mac's RAM (between 4 and 16 GB) and all but two of its CPU cores. Apple's default is 1 GB, which is not enough for KLayout, Magic or LibreLane. To pick a different size, set `CONTAINER_MEMORY` and `CONTAINER_CPUS` when you run the script, for example `CONTAINER_MEMORY=12g CONTAINER_CPUS=6 ./scripts/start_vnc_apple.sh`. The new size applies to the container that run creates.

Run these in your Mac's own terminal, not the one on the EDA desktop:

```bash
container exec -it asic-edu-osic bash -l   # open a shell in the container
container stop asic-edu-osic               # stop the container and free its RAM; start_vnc_apple.sh starts a new one
container system stop                      # stop Apple's container services (stop the container first)
```

For later courses, `mod add <course>` clones `github.com/uoftasic/<course>` into `modules/<course>`, for example `mod add ad101`. See [`modules/README.md`](modules/README.md).

## What's in this repo

| Path | Purpose |
|------|---------|
| `.designinit` | Run by the image in every new terminal; it sources `common/.designinit` |
| `.devcontainer/` | VS Code Dev Containers config |
| `scripts/` | Scripts that launch the container (`start_vnc.sh` with Docker, `start_vnc_apple.sh` with Apple `container`), and helpers (noVNC, X11, clipboard, smoke test, `add_module.sh`) |
| `common/` | Shared environment: `.designinit` with `mod`, and `xschemrc` |
| `pdk/` | `volare.lock`, which records the SKY130 PDK and image tag |
| `modules/` | One folder per course (`mod`, `mod add <name>`, `mod <name>`) |
| `docker/` | noVNC landing page |

Every course that uses the workspace runs the same image and the same PDK. The toolchain is the IIC-OSIC-TOOLS image, maintained by IIC-JKU.
