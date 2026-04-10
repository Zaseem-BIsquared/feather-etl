---
id: R-0840
type: requirement
title: Transform Dependency Declaration and Resolution
status: review
owner: speclan
created: "2026-04-10T05:10:32.302Z"
updated: "2026-04-10T05:10:32.302Z"
---
# Transform Dependency Declaration and Resolution

Operators can declare dependencies between transforms using simple annotations within their SQL files, and the system automatically resolves these into a valid execution order. This ensures upstream transforms are always created before the downstream transforms that depend on them, preventing errors caused by missing references.

When an operator annotates a transform with a dependency on another transform within the silver or gold layer, the system validates that the referenced transform exists. If a declared transform-layer dependency is missing — for example, referencing a silver transform that has no corresponding SQL file — the system raises an error at setup time, alerting the operator before any transforms are executed. This fail-fast behavior prevents cascading failures and makes dependency issues easy to diagnose.

Dependencies on external objects outside the transform layers (such as raw source tables) are silently accepted, since those objects are managed by other parts of the pipeline and are expected to exist at runtime. Operators can declare multiple dependencies per transform, and the system handles complex dependency graphs including multi-level chains across both layers.

## Acceptance Criteria

- [ ] Operator can declare one or more dependencies on other transforms using annotations in the SQL file
- [ ] The system resolves declared dependencies and processes transforms in the correct topological order
- [ ] Upstream transforms are always created before downstream transforms that depend on them
- [ ] Missing transform-layer dependencies cause an error at setup time with a clear message identifying the missing transform
- [ ] Dependencies referencing external objects outside the transform layers (e.g., source tables) are silently accepted
- [ ] Circular dependencies are detected and reported as errors at setup time
