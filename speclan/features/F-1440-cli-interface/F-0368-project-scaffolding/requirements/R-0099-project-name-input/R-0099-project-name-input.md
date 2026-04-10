---
id: R-0099
type: requirement
title: Project Name Input
status: review
owner: speclan
created: "2026-04-10T05:47:16.373Z"
updated: "2026-04-10T05:47:16.373Z"
---
# Project Name Input

Operators can specify the name of their new project when initializing it. The project name determines the directory name and serves as the identifier for the new client project throughout the onboarding workflow.

When operators provide a project name as a command-line argument, the system uses it directly without further prompts. When no project name is provided, the system enters an interactive mode and prompts the operator to type a name. This dual-input approach supports both scripted automation (where the name is known in advance) and exploratory use (where the operator decides interactively).

The project name is used to create the project directory. The system ensures the name is suitable for use as a directory name on the target filesystem.

## Acceptance Criteria

- [ ] Operator can provide a project name as a positional argument to the init command
- [ ] When no project name argument is given, the system prompts the operator interactively to enter one
- [ ] The provided project name is used as the name of the created project directory
- [ ] The system accepts valid directory-safe project names without modification
- [ ] The command proceeds to project creation after a valid name is obtained through either input method
