# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

**Repo**: `YangShusen2001/lpr-kirin8020` (private). `gh` infers it from `git remote -v` when run inside a clone.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

This is a solo project; there is no external contribution surface to triage.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Blocking edges

`/to-tickets` declares each ticket's **blocking edges**. Use GitHub's **native issue dependencies** — the canonical, UI-visible representation:

- Add an edge: `gh api --method POST repos/YangShusen2001/lpr-kirin8020/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/YangShusen2001/lpr-kirin8020/issues/<n> --jq .id`, _not_ the `#number` or `node_id`).
- The live gate is `issue_dependencies_summary.blocked_by` (open blockers only).
- Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body.

A ticket is unblocked when every blocker is closed.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
- **Frontier query**: list the map's open children, drop any with an open blocker or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`.

> Note: `/wayfinder` was considered for this project and **not** used — the design tree closed inside one session via `/grill-with-docs`. See ADR-0002.
