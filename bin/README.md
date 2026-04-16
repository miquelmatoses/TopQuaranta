# Ops scripts

Bash helpers for running + monitoring + backing up TopQuaranta. They sit in
the repo so they're version-controlled, but cron runs them from
`/home/topquaranta/bin/` (symlinked into this directory).

To re-deploy after a change:

```bash
ln -sf /home/topquaranta/app/bin/tq-run    /home/topquaranta/bin/tq-run
ln -sf /home/topquaranta/app/bin/tq-health /home/topquaranta/bin/tq-health
ln -sf /home/topquaranta/app/bin/tq-backup /home/topquaranta/bin/tq-backup
```

## `tq-run <cmd> [args...]`
Wraps a Django management command. Captures exit code + last 20 lines of
output to `/var/log/topquaranta/status/<tag>.status`. `<tag>` is the command
name with `_provisional` appended when `--provisional` is among the args, so
the setmanal and provisional ranking each have their own status entry.

## `tq-health`
Reads the status files + today's entries in
`/var/log/topquaranta/errors.log` (populated by the Django `errors_file`
log handler in `settings/base.py`). Prints a summary table and exits
non-zero when any of:
- a command's status is FAIL,
- a command's last run is older than its expected cadence (STALE),
- Django has logged any ERROR+ records today.

Run manually (`ssh topquaranta@server tq-health`) or wire to a notifier.

## `tq-backup`
Runs as user `postgres` from cron at 03:00 daily. `pg_dump | gzip -9` into
`/home/topquaranta/backups/daily/`. Copies to `weekly/` on Sundays and to
`monthly/` on the 1st. Retention: 7 daily, 4 weekly, 12 monthly.

DB is ~45 MB; gzipped ~3 MB per snapshot. Total worst-case retention ~60 MB.
