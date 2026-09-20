# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

## Notes for this repo

- `/to-spec` applies `ready-for-agent` to the spec issue it creates — no further triage needed.
- Tickets produced by `/to-tickets` are already agent-ready; **do not** run `/triage` on them. `/triage` is only for issues that arrive raw (bug reports, incoming requests).
- Some work is genuinely human-only and should carry `ready-for-human`:
  - Anything needing the **physical device unlocked** (真机 install/run, `.om` 三关验证).
  - **DDK / signing credentials** setup.
  - Anything requiring a **Huawei developer account** interaction.
  - **Store-channel** measurements (RQ2, currently out of scope per ADR-0007).
