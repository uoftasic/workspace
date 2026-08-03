# IC101 — setup module

Scratch space for **IC101 — Onboarding onto Tools**. Full manual:
**https://uoftasic.github.io/ic101/**

Once the environment is running, open the in-container terminal and verify your tools:

```bash
. /foss/designs/common/.designinit     # load the environment + SKY130 PDK
/foss/designs/scripts/smoke_test.sh    # health-check every tool + mod helpers
mod                                    # list course modules
mod ic101_setup                        # jump into this folder
```

Later courses live beside this one. From a sourced shell: `mod add <course>` (for example
`mod add ad101`) clones the course repo into `modules/`. Keep this workspace cloned — you reuse it
across the catalog.
