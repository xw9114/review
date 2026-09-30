# Workspace navigation contract

## Scope and configuration

`frontend/src/lib/workspace-navigation.ts` is the single source for the six main routes. Each entry has `id`, `href`, `label`, and `icon` (`IconName`). `WorkspacePage` is inferred from this data; `AppShell.active` must be one of these IDs. The header breadcrumb uses `workspaceLabel(active)` and therefore cannot drift from the sidebar label.

Groups appear in this order: 工作台 (今日概览), 收集与整理 (资料收件箱、草稿审核), 知识与复习 (我的知识库、每日复习), 来源管理 (订阅源). URLs remain `/`, `/sources`, `/drafts`, `/knowledge`, `/review`, `/feeds`. The groups are navigation labels, not new routes or database categories.

## Behavior and validation

| State | Required behavior |
| --- | --- |
| Active route | Exactly one link has `aria-current="page"`; breadcrumb and visible label agree. |
| Desktop | Group captions separate tasks and sources without hiding any route. |
| 768px tablet or 320px phone | All six links stay visible and inside the viewport; icon-only links retain `aria-label` and `title`. |
| Unknown `WorkspacePage` at compile time | TypeScript rejects the route; add the route to the shared config when implemented. |

Good: Add a route once to the config and use its ID in `AppShell`. Base: existing deep links continue to work. Bad: duplicate route labels in `AppShell`, which let the sidebar and breadcrumb disagree.

## Tests required

- `npm run lint`, `npx tsc --noEmit`, and `npm run build` in `frontend/`.
- `node docs/visual-qa/check-workspace-structure.cjs` asserts six links, active route, viewport bounds at 1440/768/390/320px in light/dark mode, and no horizontal overflow.
