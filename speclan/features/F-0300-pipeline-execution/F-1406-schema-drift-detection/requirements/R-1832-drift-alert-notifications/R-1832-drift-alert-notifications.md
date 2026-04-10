---
id: R-1832
type: requirement
title: Drift Alert Notifications
status: review
owner: speclan
created: "2026-04-10T05:18:23.641Z"
updated: "2026-04-10T05:18:23.641Z"
---
# Drift Alert Notifications

When schema drift is detected during a pipeline run, the system automatically triggers email alert notifications to inform operators of the changes. This ensures that schema evolution is surfaced promptly even when operators are not actively monitoring pipeline output, enabling timely coordination with upstream data owners and proactive remediation of potential issues.

Alert notifications include the details of all detected drift events so that operators can assess the situation without needing to log into the system or query run history. The alert content conveys which table was affected, which columns changed, the category of each change, and the severity level — giving operators enough context to decide whether immediate action is needed.

The severity of the alert corresponds to the most severe drift detected in the run. If any type changes are present, the alert is elevated to critical severity. If only added or removed columns are detected, the alert carries informational severity. This ensures that the notification urgency matches the actual risk to data integrity.

## Acceptance Criteria

- [ ] Schema drift triggers an email alert notification to configured recipients
- [ ] Alert notifications include the affected table name
- [ ] Alert notifications include details of each detected drift event (column, category, types)
- [ ] Alert severity reflects the most severe drift category detected in the run
- [ ] Type-change drift results in a critical-level alert
- [ ] Added-only or removed-only drift results in an informational-level alert
