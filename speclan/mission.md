# Mission: Eliminate the Complexity Tax on Business Data

## What We Do

feather-etl provides a complete, config-driven data pipeline that extracts data from heterogeneous business systems, transforms it through clearly defined layers, and delivers clean, curated tables ready for dashboards and analytics. It replaces what would otherwise require three or more separate heavyweight tools with a single, understandable package that a small team can deploy across many clients.

## How We Achieve This

- **Configuration over code**: Operators define sources, tables, schedules, transforms, and quality checks in plain configuration files. Adding a new data table means editing a file, not writing custom programs
- **Layered data organization**: Raw data flows through optional bronze (audit/cache), silver (canonical names, selected columns), and gold (KPIs, aggregations) layers — each serving a clear purpose, each optional based on client needs
- **Intelligent extraction**: Change detection ensures data is only moved when it has actually changed, minimizing load on source systems and reducing processing time for routine runs
- **Local-first processing**: All extraction and transformation happens locally at minimal cost, with only the final curated output synced to cloud destinations — keeping cloud expenses proportional to business value, not data volume
- **Multi-client by design**: Each client deployment is an independent configuration. The same package serves businesses running different source systems, different schemas, and different reporting needs

## Our Principles

- **Simplicity over sophistication**: A working pipeline that anyone can understand beats a powerful one that requires specialized expertise to maintain
- **Transparency by default**: Every run is recorded, every quality check is logged, every schema change is detected and reported — operators are never left guessing
- **Graceful adaptation**: When source systems change columns, add fields, or modify types, the pipeline adapts automatically where safe and alerts operators where human judgment is needed
- **Idempotent operations**: Every pipeline operation is safe to re-run after partial failures — no manual cleanup, no corrupted state, no fear of double-loading
- **Progressive complexity**: Start with the simplest configuration that works. Add bronze layers, quality checks, scheduling tiers, and cloud sync only when the business need arises
