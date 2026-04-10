---
id: R-0752
type: requirement
title: Mode Resolution Priority
status: review
owner: system
created: "2026-04-10T05:33:22.295Z"
updated: "2026-04-10T05:33:22.295Z"
---
# Mode Resolution Priority

Users can specify the operating mode through multiple channels, and the system resolves conflicts using a clear, predictable priority chain. This layered approach supports diverse workflows: teams set a default in their shared configuration file, CI/CD systems override it with an environment variable, and individual users can force a specific mode for a single run via the command line.

The priority chain, from highest to lowest, is: the command-line flag, then the environment variable, then the mode declared in the YAML configuration file, and finally the built-in default of development mode. When a higher-priority source specifies a mode, all lower-priority sources are ignored. This means a CLI flag always wins, regardless of what the environment variable or config file says.

This design ensures that the same configuration file works across all environments without modification. A team can commit a config file with no mode specified (defaulting to development), while their CI pipeline sets the environment variable to test mode and their production scheduler uses the CLI flag for production mode.

## Acceptance Criteria

- [ ] A mode specified via CLI flag takes precedence over all other sources
- [ ] A mode specified via environment variable takes precedence over the YAML config and default
- [ ] A mode specified in the YAML configuration file takes precedence over the default
- [ ] The default mode is development when no mode is specified anywhere
- [ ] Only one mode is active per pipeline run, even when multiple sources specify different modes
- [ ] Users can determine which mode is active and how it was resolved
- [ ] The pipeline rejects invalid mode values with a clear error message
