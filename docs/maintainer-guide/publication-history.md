# Publication history and state

The website's [History](/history/) page is built from a ledger the publisher keeps outside the disposable release
directories.

## Files

| Path | Content |
|---|---|
| `publish-state/history.json` | the ledger: one entry per published snapshot (`payload_kind: site_history`) |
| `publish-state/snapshots/<snapshot-id>.inventory.json` | the inventory of that snapshot: every family, instance and BKS with identifying hashes |

`snapshot-id` defaults to `<published date>-<short commit>`; pass `--snapshot-id` to override and `--published-at`
for a reproducible timestamp.

## What an entry records

The summary you pass with `--history-summary`, the route of the detail page, the affected problem types, families and
objectives, and `change_counts`: families, instances and BKS **added**, **removed**, **improved** or **regressed**,
computed by diffing the new inventory against the previous one. A BKS counts as improved when its cost is strictly
better under its objective; a regression means a stored BKS got worse, which the write path forbids, so a regression
signals a hand edit or a corrupted file and deserves investigation.

## Rules

- **The state dir survives releases.** Deployments keep it under the releases root (`SITE_BUILD_STATE_DIR`) and
  hydrate it from older release copies before each build (`SITE_BUILD_HYDRATE_PUBLISH_STATE=1`); a fresh release
  directory therefore never resets the history to "initial snapshot".
- **Staging builds write the state dir too.** A staging build is a publication; if you only want to look, point
  `--state-dir` at a scratch directory.
- **Legacy layouts migrate once.** `migrate_legacy_state` seeds an empty state dir from a pre-roots `dist/site/`
  tree.
- **Summaries are for humans.** Say what changed and why (`"Rifki2020: FIFO restoration fix, 12 BKS improved"`),
  not "rebuild".
