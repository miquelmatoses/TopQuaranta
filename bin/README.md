# Ops scripts

Bash helpers for running + monitoring + backing up TopQuaranta. They sit in
the repo so they're version-controlled, but cron runs them from
`/home/topquaranta/bin/` (symlinked into this directory).

To re-deploy after a change:

```bash
ln -sf /home/topquaranta/app/bin/tq-run     /home/topquaranta/bin/tq-run
ln -sf /home/topquaranta/app/bin/tq-recover /home/topquaranta/bin/tq-recover
ln -sf /home/topquaranta/app/bin/tq-health  /home/topquaranta/bin/tq-health
ln -sf /home/topquaranta/app/bin/tq-backup  /home/topquaranta/bin/tq-backup
```

## `tq-run <cmd> [args...]`
Wraps a Django management command with retry. Captures exit code + last 20
lines of output to `/var/log/topquaranta/status/<tag>.status`. `<tag>` is the
command name with `_provisional` appended when `--provisional` is among the
args, so the setmanal and provisional ranking each have their own status
entry.

Retry policy (R7): on a non-zero exit the wrapper retries up to MAX_ATTEMPTS
times with sleep between attempts. Default: 3 attempts, sleeping 60s then
300s. Exception: `obtenir_novetats` runs hourly, so its MAX_ATTEMPTS is 1
(the next cron tick is the natural retry — no point burning the rate limit).
The status file records `attempts=N` and `max_attempts=M` so failures are
visible even after a successful retry.

## `tq-recover`
Second line of defence for the daily pipeline (R7). Runs every 30 min via
cron. For each tracked daily command (and the weekly ranking on Saturdays),
checks its `<tag>.status` file: if missing, FAIL, or `last_run` is earlier
than today's expected cutoff, re-launches the command via `tq-run`. Capped
at `MAX_RECOVER_PER_DAY=5` re-launches per command per day to avoid storms
during a permanent upstream outage. Per-day counters live in
`/var/log/topquaranta/status/<tag>.recover` and reset when the date changes.

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

## `tq-restore-test`
Runs as user `postgres` from cron on the 1st of each month at 04:30 (R14).
Picks the newest dump in `daily/`, restores it to a throwaway database
`topquaranta_restore_test`, validates row counts against the live DB
(must be within 5%), then drops the test DB. Failures land in
`tq-restore-test.status` and are surfaced by `tq-health` (max-age 35 days).

Defends against silent backup corruption: a `pg_dump` that produces an
unreadable gzip would otherwise only be discovered during a real disaster.
