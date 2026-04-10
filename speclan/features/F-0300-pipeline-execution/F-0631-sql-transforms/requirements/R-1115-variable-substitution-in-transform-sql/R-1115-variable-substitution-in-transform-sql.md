---
id: R-1115
type: requirement
title: Variable Substitution in Transform SQL
status: review
owner: speclan
created: "2026-04-10T05:10:46.117Z"
updated: "2026-04-10T05:10:46.117Z"
---
# Variable Substitution in Transform SQL

Operators can use variable placeholders within their transform SQL files, allowing the same transform definitions to adapt to different environments, schemas, or configurations without duplicating SQL. This promotes reusability and reduces maintenance burden when transforms need to work across multiple deployment contexts.

When a transform is processed, the system substitutes variable placeholders with their configured values before executing the SQL. This enables operators to write a single transform file that references environment-specific schema names, table prefixes, or other configurable values. Variables are resolved at execution time, so the same SQL files can be used across development, test, and production environments with different configurations.

If a variable placeholder is used in a SQL file but no corresponding value is configured, the system should provide a clear indication of the issue rather than executing malformed SQL.

## Acceptance Criteria

- [ ] Operator can include variable placeholders in transform SQL files
- [ ] Variable placeholders are substituted with configured values before the SQL is executed
- [ ] The same transform SQL file can produce different results based on environment-specific variable values
- [ ] Missing variable values result in a clear error or warning rather than silent execution of unresolved placeholders
- [ ] Variable substitution works in both silver and gold layer transforms
