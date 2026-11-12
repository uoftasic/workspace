# IC101 setup module

Scratch space for IC101 (Onboarding onto Tools). The full manual is at https://uoftasic.com/ic101/.

Once the container is running (see Quick start in the [workspace README](../../README.md)), open a terminal on the desktop and check your tools:

```bash
. /foss/designs/common/.designinit     # load the environment: SKY130 PDK and the mod command
/foss/designs/scripts/smoke_test.sh    # check every tool and the mod helpers
mod                                    # list course modules
mod ic101_setup                        # go to this folder
```

Later courses go in folders next to this one. From a terminal with the environment loaded, `mod add <course>` (for example `mod add ad101`) clones that course's repo into `modules/`. Keep this workspace: you reuse it for the other courses in the [catalog](https://edu.uoftasic.com/).
