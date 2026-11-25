# Course modules

Each course that uses the tools keeps its files in a folder here. Inside the container the folder is at `/foss/designs/modules/<name>`. Load the environment (`.designinit`), then use `mod` to list modules, enter one, or add one.

```bash
. /foss/designs/common/.designinit   # load the environment: SKY130 PDK and the mod command
mod                                  # list course modules
mod ic101_setup                      # enter a module
mod add ad101                        # clone github.com/uoftasic/ad101 into modules/ad101
```

| Module | Course |
|--------|--------|
| `ic101_setup/` | [IC101 — Onboarding onto Tools](https://uoftasic.com/ic101/) |
| `ad101/` | [AD101 — Signals](https://uoftasic.com/ad101/). Not committed in this repo; clone it with `mod add ad101`. |
| `ad104-m/` | [AD104-M — Layout](https://uoftasic.com/ad104-m/). Not committed in this repo; clone it with `mod add ad104-m`. |

You can also clone a course on your own machine (the host) instead of in the container. The result is the same, because the workspace is bind-mounted into the container:

```bash
# from the workspace root on the host
./scripts/add_module.sh ad101
# or: cd modules && git clone https://github.com/uoftasic/ad101.git
```

Either way, `mod ad101` inside the container takes you to `/foss/designs/modules/ad101`.

More folders are planned, added as each course's lab content is ready: `ad103_nonlinear/`, `dd103_rtl/`, `dd104_verification/`, … See the [course catalog](https://edu.uoftasic.com/).
