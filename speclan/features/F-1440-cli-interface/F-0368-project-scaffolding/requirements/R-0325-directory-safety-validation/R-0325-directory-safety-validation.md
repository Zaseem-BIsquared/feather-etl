---
id: R-0325
type: requirement
title: Directory Safety Validation
status: review
owner: speclan
created: "2026-04-10T05:47:20.612Z"
updated: "2026-04-10T05:47:20.612Z"
---
# Directory Safety Validation

The system prevents accidental overwriting of existing project files by validating the target directory before scaffolding. This safety check protects operators from inadvertently destroying work in a directory that already contains content.

Before creating any files, the system inspects the target directory. If the directory already exists and contains non-hidden files, the system refuses to proceed and displays a clear error message explaining why the operation was blocked. Hidden files (such as `.git` or system metadata) are ignored during this check, so operators can safely initialize a project inside a freshly cloned or pre-configured repository.

If the target directory does not exist, or exists but contains only hidden files, the system proceeds normally with scaffolding.

## Acceptance Criteria

- [ ] The system checks the target directory for existing non-hidden files before creating any scaffolded content
- [ ] If non-hidden files are found, the system refuses the operation and displays an error message
- [ ] The error message clearly explains that the directory already contains files
- [ ] Hidden files and directories in the target location do not trigger the safety check
- [ ] If the target directory does not exist, the system creates it and proceeds with scaffolding
- [ ] If the target directory exists but contains only hidden files, scaffolding proceeds normally
