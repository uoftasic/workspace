# Course modules

Each tool-using course drops its starter files in a folder here, mounted inside the container at
`/foss/designs/modules/<name>`. Source the environment, then use `mod` to list, enter, or add modules.

```bash
. /foss/designs/common/.designinit   # required once per shell
mod                                  # list course modules
mod ic101_setup                      # enter a module
mod add ad101                        # clone github.com/uoftasic/ad101 into modules/ad101
```

| Module | Course |
|--------|--------|
| `ic101_setup/` | [IC101 — Onboarding onto Tools](https://uoftasic.com/ic101/) |
| `ad101/` | [AD101 — Signals](https://uoftasic.com/ad101/) — clone with `mod add ad101` (not committed in workspace) |

You can also clone on the host (same result, bind-mounted into the container):

```bash
# from the workspace root on the host
./scripts/add_module.sh ad101
# or: cd modules && git clone https://github.com/uoftasic/ad101.git
```

Inside the container: `mod ad101` → `/foss/designs/modules/ad101`.

Planned (added as each course reaches its lab content): `ad103_nonlinear/`, `ad104_layout/`,
`dd103_rtl/`, `dd104_verification/`, … See the [course catalog](https://edu.uoftasic.com/catalog/).
