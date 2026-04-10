---
id: R-0921
type: requirement
title: Automatic Recovery on Successful Extraction
status: review
owner: spec-agent
created: "2026-04-10T05:42:30.674Z"
updated: "2026-04-10T05:42:30.674Z"
---
# Automatic Recovery on Successful Extraction

When a table that was previously in a backoff state is successfully extracted, the system automatically resets all retry state for that table. The consecutive failure count returns to zero and the "retry after" timestamp is cleared. This ensures the table resumes its normal extraction schedule immediately, with no residual penalty from prior failures.

Recovery is fully automatic and requires no operator intervention. Once the underlying issue resolves — whether it was a transient network error, a temporary source system outage, or a permissions change that was corrected — the table seamlessly returns to normal operation on its next successful extraction.

This reset behavior means that a single success is sufficient to clear any accumulated backoff state, regardless of how many consecutive failures preceded it. The table starts fresh, and any future failure would begin the backoff progression from the beginning again.

## Acceptance Criteria

- [ ] A successful extraction resets the table's consecutive failure count to zero
- [ ] A successful extraction clears the table's "retry after" timestamp
- [ ] Recovery occurs automatically without any manual operator action
- [ ] A single successful extraction fully clears all backoff state regardless of prior failure count
- [ ] After recovery, any new failure starts the backoff progression from the beginning (15 minutes)
- [ ] The table resumes normal extraction scheduling immediately after recovery
