---
id: R-1294
type: requirement
title: Broad SMTP Provider Compatibility
status: review
owner: speclan
created: "2026-04-10T05:00:41.802Z"
updated: "2026-04-10T05:00:41.802Z"
---
# Broad SMTP Provider Compatibility

Operators can use any SMTP-compatible email service to deliver alerts, including consumer email providers (such as Gmail with app passwords), corporate SMTP relays, and transactional email platforms. The system does not require a specific email vendor, proprietary API, or additional software installation — it works with the standard SMTP protocol that virtually all email services support.

This broad compatibility means operators can integrate alerting with whatever email infrastructure their organization already uses. Small teams can route alerts through a personal Gmail account; enterprise teams can use their corporate mail relay; and production deployments can leverage transactional email services for high deliverability. The system handles the standard SMTP handshake, authentication, and secure connection requirements that these diverse providers expect, requiring no additional software dependencies beyond what the pipeline already includes.

## Acceptance Criteria

- [ ] Alerts can be delivered through a standard SMTP relay requiring authentication (username/password)
- [ ] Alerts can be delivered through SMTP services that require TLS/SSL connections
- [ ] The alerting system requires no additional software packages or dependencies beyond the pipeline's core installation
- [ ] Operators configure the SMTP host and port to match their provider's requirements
- [ ] The system works with SMTP services on non-standard ports (not just port 25 or 587)
