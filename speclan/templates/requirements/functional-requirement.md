---
id: "3db2f0cb-e62c-4ecb-9988-b39af63e75ae"
type: "template"
title: "Functional Requirement"
status: "released"
owner: "system"
created: "2026-04-10"
updated: "2026-04-10"
description: "Detailed functional requirement with business rules"
isSystemTemplate: true
templateFor: "requirement"
---

# {{TITLE}}

## Description

The system shall [action] when [condition] so that [outcome].

## Preconditions

- User must be authenticated
- Required data must be available
- System must be in [state]

## Business Rules

1. **Rule 1:** [Description of business rule]
2. **Rule 2:** [Description of business rule]
3. **Rule 3:** [Description of business rule]

## Postconditions

- Data is persisted to the database
- Audit log entry is created
- Notifications are sent to stakeholders

## Exceptions

| Condition | System Response |
|-----------|-----------------|
| Invalid input | Display validation error |
| Timeout | Retry with exponential backoff |
| Conflict | Show conflict resolution dialog |

## Dependencies

- Depends on: [REQ-XXX], [REQ-YYY]
- Depended by: [REQ-ZZZ]

## Acceptance Criteria

- [ ] GIVEN [precondition], WHEN [action], THEN [expected result]
- [ ] All business rules are correctly enforced
- [ ] Postconditions are met after successful execution
- [ ] Each exception case displays appropriate error message
- [ ] Audit log entry contains all required fields
