---
id: R-1498
type: requirement
title: Severity-Based Drift Reporting
status: review
owner: speclan
created: "2026-04-10T05:18:15.828Z"
updated: "2026-04-10T05:18:15.828Z"
---
# Severity-Based Drift Reporting

Every detected schema drift event is assigned a severity level based on its category, enabling operators to quickly prioritize their response. This classification ensures that low-risk, automatically handled changes do not create unnecessary urgency, while high-risk changes that may cause data loss or quarantine are elevated for prompt attention.

Added and removed columns are assigned informational severity. These changes are handled automatically by the system — new columns are accommodated, and removed columns are preserved with NULLs — so they typically require awareness rather than immediate action. Operators can review them at their convenience and coordinate with upstream data owners as needed.

Data type changes are assigned critical severity. These changes carry a risk of conversion failures, which can result in rows being quarantined rather than loaded. Critical severity signals to operators that data may be missing from the destination table and that investigation and remediation may be required.

All drift details — including the column name, drift category, severity, and type information — are recorded as structured data in the run history. This provides a persistent, queryable audit trail of schema evolution that operators can use for trend analysis, compliance reporting, and root-cause investigation.

## Acceptance Criteria

- [ ] Added column drift events are assigned informational severity
- [ ] Removed column drift events are assigned informational severity
- [ ] Type-changed column drift events are assigned critical severity
- [ ] Drift details are recorded as structured data in the pipeline's run history
- [ ] Recorded drift details include the column name, drift category, and severity level
- [ ] Type-change records include both the original and new data types
- [ ] Drift history is queryable across tables and runs for trend analysis
