---
id: R-0695
type: requirement
title: Table Definition Validation
status: review
owner: speclan
created: "2026-04-10T05:36:29.769Z"
updated: "2026-04-10T05:36:29.769Z"
---
# Table Definition Validation

Operators are informed when their table definitions contain invalid names, incorrect schema prefixes, or naming patterns that would cause failures during data extraction or loading. This catches table-level configuration issues that would otherwise surface as cryptic database errors at runtime.

The validation process examines each table definition to ensure that source table names are valid SQL identifiers appropriate to the configured source type. Target table names are checked for valid schema prefixes (bronze, silver, or gold), enforcing the project's data lakehouse naming convention. The system is aware that different source types may have different identifier rules, and applies the appropriate rules for each source.

When issues are found, the operator receives specific error messages identifying which table has the problem and what rule it violates, enabling quick correction.

## Acceptance Criteria

- [ ] Operator receives an error when a source table name is not a valid SQL identifier for its source type
- [ ] Operator receives an error when a target table name does not use a valid schema prefix (bronze, silver, or gold)
- [ ] Validation applies source-type-aware SQL identifier rules rather than a single generic rule
- [ ] Error messages identify the specific table definition that violates the rule
- [ ] All table definition errors are reported together in a single validation run
