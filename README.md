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

## KLayout and the Magic menu

KLayout in the workspace loads the [klayout-magic-pcells](https://github.com/uoftasic/klayout-magic-pcells) plugin, which the AD104-K course uses. The plugin adds two things to KLayout:

- the `sky130_magic` library in the Libraries panel. Magic draws the devices in this library, so a transistor you place from it in KLayout is the one Magic's Devices menu would draw.
- a Magic menu, between Macros and Help, which runs Magic's design rule check (DRC), Magic's extraction, and a layout-versus-schematic check (LVS) with netgen on the layout you have open.

The plugin is part of this repo, in `klayout/salt/klayout-magic-pcells/`, at the release named in `klayout/PLUGIN_VERSION`. `git pull` updates it with the rest of the workspace, and the container doesn't need GitHub to load it. `common/.designinit` adds the `klayout/` folder to `KLAYOUT_PATH`, the list of folders where KLayout looks for technologies and packages. The plugin keeps the cells it generates in `.cache/klayout-magic-pcells/` at the top of the repo. Git ignores that folder, and it survives a new container, like the rest of your files under `/foss/designs`.

If you start KLayout with the KLayout icon on the desktop, a file you open with File > Open shows the sky130A layer names. From a terminal, name the technology and the file: `klayout -e -n sky130A my_cell.gds` (`-e` opens KLayout in edit mode, and `-n sky130A` applies the sky130A technology to the file you name). In a KLayout started from a terminal, a file opened later with File > Open can show bare layer numbers instead; open it from a KLayout started with the icon, or name it on the command line.

The smoke test checks the plugin. Its last KLayout check is `doctor`, the plugin's self-check, which starts Magic. On a working setup the KLayout lines are these, with the version from `klayout/PLUGIN_VERSION`:

```
--- KLayout ---
OK  KLayout technology sky130A
OK  KLayout library sky130_magic (klayout-magic-pcells v0.6.2)
OK  KLayout Magic menu (8 entries)
OK  Magic built a sky130_fd_pr__nfet_01v8 for KLayout
OK  klayout-magic-pcells doctor
```

If KLayout has no Magic menu, the terminal you started it from didn't load `.designinit`, or you ran `sak-pdk-script.sh` (the image's script for switching PDKs) in that terminal afterwards; that script resets `KLAYOUT_PATH`. Open a new terminal, or run `. /foss/designs/common/.designinit` in that one, then start KLayout again from it.

To move the workspace to a later release of the plugin, a maintainer runs `scripts/update_klayout_plugin.sh <tag>` on the host (your own machine, outside the container), runs the smoke test in the container, and commits.

## What's in this repo

| Path | Purpose |
|------|---------|
| `.designinit` | Run by the image in every new terminal; it sources `common/.designinit` |
| `.devcontainer/` | VS Code Dev Containers config |
| `scripts/` | Scripts that launch the container (`start_vnc.sh` with Docker, `start_vnc_apple.sh` with Apple `container`), and helpers (noVNC, X11, clipboard, smoke test, `add_module.sh`) |
| `common/` | Shared environment: `.designinit` with `mod`, and `xschemrc` |
| `pdk/` | `volare.lock`, which records the SKY130 PDK and image tag |
| `modules/` | One folder per course (`mod`, `mod add <name>`, `mod <name>`) |
| `klayout/` | KLayout packages: the klayout-magic-pcells plugin, at the release named in `klayout/PLUGIN_VERSION` |
| `docker/` | noVNC landing page |

Every course that uses the workspace runs the same image and the same PDK. The toolchain is the IIC-OSIC-TOOLS image, maintained by IIC-JKU.
