# IC101 — setup module

This folder is your scratch space for **IC101 — Onboarding onto Tools**. The full manual is online
at **https://uoftasic.com/ic101-docs/**.

Once the environment is running, open the in-container terminal and verify your tools:

```bash
. /foss/designs/common/.designinit     # load the environment + SKY130 PDK
/foss/designs/scripts/smoke_test.sh    # health-check every tool
mod                                    # list course modules
```

If the smoke test passes, you're ready for any track. Keep this workbench cloned — later courses
add their own folders under `modules/`.
