---
id: R-0893
type: requirement
title: Table Status Overview
status: review
owner: team
created: "2026-04-10T05:39:50.145Z"
updated: "2026-04-10T05:39:50.145Z"
---
# Table Status Overview

Users can view the last run outcome for every managed table through the `feather status` command, providing an at-a-glance health dashboard of the entire pipeline. This is essential for operators who need to quickly determine whether all tables are healthy or identify which ones need attention.

The command shows one row per table, reflecting the most recent run regardless of when it occurred. Each row includes the table name, the last run's status, when it ran, and the current watermark value. This makes it easy to spot tables that have fallen behind, are stuck in a failure state, or have stale watermarks indicating they haven't been refreshed recently.

The output is presented in a human-readable tabular format by default, designed for quick scanning in a terminal session.

## Acceptance Criteria

- [ ] The `feather status` command displays one entry per managed table
- [ ] Each entry shows the most recent run's status, timestamp, and outcome
- [ ] Current watermark values are displayed for each table
- [ ] The output covers all tables across all time, not just recent runs
- [ ] The default output is a human-readable tabular format suitable for quick scanning
