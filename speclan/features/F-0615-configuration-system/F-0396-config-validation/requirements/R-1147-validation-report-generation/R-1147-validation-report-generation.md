---
id: R-1147
type: requirement
title: Validation Report Generation
status: review
owner: speclan
created: "2026-04-10T05:36:50.344Z"
updated: "2026-04-10T05:36:50.344Z"
---
# Validation Report Generation

Operators and automation tools receive a structured, machine-readable validation report after every validation run. This enables both human review and programmatic decision-making — such as deployment gates or monitoring alerts — based on validation outcomes.

When `feather validate` completes, the system writes a `feather_validation.json` file alongside the configuration file. This report contains the overall validation result (pass or fail), all resolved paths from the configuration, any errors or warnings discovered during validation, source connectivity test results, and a timestamp recording when validation was performed. The report is written regardless of whether validation passed or failed, so operators always have a record of the most recent validation run.

The report file is overwritten on each validation run, ensuring it always reflects the latest results. Operators can inspect it directly to review resolved paths and confirm their configuration is correct, while automation tools can parse it to gate deployments or trigger alerts.

## Acceptance Criteria

- [ ] A `feather_validation.json` file is written alongside the configuration file after every validation run
- [ ] The report contains the overall validation result indicating pass or fail
- [ ] The report contains all resolved paths from the configuration
- [ ] The report contains all validation errors and warnings discovered during the run
- [ ] The report contains source connectivity test results
- [ ] The report contains a timestamp recording when validation was performed
- [ ] The report is written regardless of whether validation passed or failed
