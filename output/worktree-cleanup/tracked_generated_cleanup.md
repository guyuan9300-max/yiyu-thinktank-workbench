# Tracked Generated Artifact Cleanup

Recorded scope: main repository cleanup batch for generated files that were already tracked by Git.

## Removed from Git tracking

- `.playwright-cli/*.yml`: 45 files
- Empty database placeholders: 4 files
  - `app.db`
  - `cloud_backend/app.db`
  - `cloud_backend/app/dev.db`
  - `cloud_backend/yiyu_cloud.db`

## Verification notes

- All four tracked DB files were empty (`0` bytes) before removal from tracking.
- Product/runtime code references runtime DB paths such as `userData/app.db` or temporary test DB paths, not these tracked placeholder files.
- `.playwright-cli` references are limited to ignore rules, collaboration filtering, and cleanup audit notes.
- Local files are kept on disk and ignored; this commit removes them from the repository index only.
