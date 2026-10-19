# Review packet template — `@ace-reviewer`

Copy to `docs/coordinator/reviews/<task-id>.md` header when requesting a
review. The reviewer is read-only and writes findings in place.

- task_id:
- worker report: `docs/coordinator/tasks/<task-id>/report.md`
- diff scope: `git diff --stat` plus exact files
- contracts to check (versions):
- rendered evidence to inspect (path, frames):
- output: severity, confidence, file or frame evidence per finding, verdict
  `PASS` / `FAIL` / `PARTIAL` / `NEEDS_REVIEW`
- rule: never `PASS` from an asset ID or expected code path alone
