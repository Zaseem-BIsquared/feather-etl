---
id: "faf4162c-9a7a-4ed8-b66d-6ab9df2dc44c"
type: "template"
title: "Non-Functional Requirement"
status: "released"
owner: "system"
created: "2026-04-10"
updated: "2026-04-10"
description: "Template for performance, security, and quality requirements"
isSystemTemplate: true
templateFor: "requirement"
---

# {{TITLE}}

## Category

[ ] Performance  [ ] Security  [ ] Scalability  [ ] Reliability  [ ] Usability

## Description

The system shall [quality attribute] under [conditions].

## Metrics

| Metric | Target | Acceptable | Unacceptable |
|--------|--------|------------|--------------|
| Response time | < 200ms | < 500ms | > 1000ms |
| Availability | 99.9% | 99.5% | < 99% |
| Throughput | 1000 req/s | 500 req/s | < 100 req/s |

## Measurement Method

How this requirement will be measured and verified:
- Tool/technique used
- Test conditions
- Measurement frequency

## Constraints

- Hardware limitations
- Network bandwidth
- Third-party service SLAs

## Trade-offs

What may be sacrificed to meet this requirement:
- Cost implications
- Feature limitations
- Complexity increase

## Acceptance Criteria

- [ ] Target metric is achieved under normal load conditions
- [ ] Acceptable threshold is maintained under peak load
- [ ] System degrades gracefully when limits are exceeded
- [ ] Measurement method produces consistent, reproducible results
- [ ] Metrics are logged and available for monitoring
