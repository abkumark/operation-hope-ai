---
title: "Urgent Situation Escalation Procedures"
category: "no_information"
type: "internal"
auto_resolvable: false
queue: "Tier 2 Support"
last_updated: "2026-03-12"
---

# Urgent Situation Escalation Procedures

## Problem Description
A critical situation has been identified that requires immediate escalation beyond standard support workflows. This includes system outages, data breaches or suspected security incidents, large-scale client impact, and any event that threatens Operation HOPE's ability to deliver services to clients in financial literacy programs, homeownership counseling, or small business coaching.

## When to Escalate Immediately

### Tier 1: System Outage (Immediate Escalation)
Escalate within **15 minutes** of confirmed impact:
- Client Portal is completely inaccessible to all users
- EverFi LMS is down and clients cannot access courses
- Dynamics 365 CRM is unavailable and coaches cannot access client records
- Certificate generation is failing for all clients (not just one individual)
- Authentication system (Azure AD) is rejecting all login attempts

### Tier 2: Data Integrity / Security (Immediate Escalation)
Escalate within **15 minutes** of detection:
- Suspected data breach or unauthorized access to client PII (names, SSNs, financial data)
- Client reports seeing another client's personal information
- Mass data corruption in any system (incorrect records across multiple clients)
- Unauthorized changes to program enrollments or certifications
- Phishing attempts targeting Operation HOPE clients or staff

### Tier 3: Large-Scale Client Impact (Escalate within 1 hour)
Escalate within **1 hour** of identification:
- Sync failure affecting 50+ client records between LMS/Portal/Dynamics
- A scheduled course or program deadline is at risk due to technical issues
- HUD certificate generation is failing for an entire cohort
- A partner organization (e.g., a corporate sponsor running a financial wellness program) reports widespread issues for their participants
- Bulk enrollment failures preventing new clients from starting programs

### Tier 4: Reputational / Partner Impact (Escalate within 2 hours)
Escalate within **2 hours** of awareness:
- A partner or funder raises a complaint about system reliability
- Social media reports of Operation HOPE service disruptions
- Media inquiries about service failures
- Scheduled events (workshops, webinars) at risk due to platform issues

## Escalation Chain

### Level 1: IT Support Lead
- **When:** First point of escalation for all Tier 1-3 issues
- **How:** Direct message in the IT Support channel + phone call if no response in 10 minutes
- **Expectation:** Acknowledge within 15 minutes, provide initial assessment within 30 minutes

### Level 2: Engineering/Development Team
- **When:** IT Support Lead confirms a technical root cause that requires code or infrastructure changes
- **How:** Page the on-call engineer through the incident management system
- **Expectation:** Acknowledge within 15 minutes, begin investigation immediately

### Level 3: IT Director / VP of Technology
- **When:** Issue is not resolved within 2 hours, or it is a Tier 2 (security) issue of any severity
- **How:** Direct phone call + email with incident summary
- **Expectation:** Executive awareness and resource authorization within 30 minutes

### Level 4: Chief Operating Officer / Executive Leadership
- **When:** Issue is not resolved within 4 hours, affects 500+ clients, involves confirmed data breach, or has external visibility (media/partner complaints)
- **How:** Phone call from IT Director + written incident brief
- **Expectation:** Executive decision-making on communications and resource allocation

## Incident Response Procedure

### Step 1: Confirm and Document (First 15 minutes)
1. Verify the issue is real and not an isolated client problem
   - Check with at least 2-3 additional clients or test accounts
   - Review system monitoring dashboards for alerts
2. Create an incident ticket with severity classification (Tier 1-4)
3. Record the following in the ticket:
   - Time of first report
   - Number of known affected clients
   - Systems impacted (Portal, LMS, Dynamics, Certificates)
   - Current client-facing impact description
   - Steps already attempted

### Step 2: Escalate and Communicate (Within 30 minutes)
1. Escalate per the chain above based on severity tier
2. Post an internal status update in the incident channel
3. If client-facing, prepare a client communication using the templates below

### Step 3: Mitigate and Resolve
1. Implement any available workaround to reduce client impact
2. Coordinate with engineering on root cause identification
3. Provide status updates every 30 minutes during active incidents
4. Document all actions taken in the incident ticket

### Step 4: Resolve and Close
1. Confirm the issue is resolved through testing
2. Verify with affected clients that service is restored
3. Send a resolution notification to all stakeholders
4. Schedule a post-incident review within 48 hours

## Communication Templates

### Client-Facing: Service Disruption (Email/Portal Banner)
```
Subject: Operation HOPE System Maintenance in Progress

We are currently experiencing a temporary disruption to [Client Portal / online courses / certificate access]. Our technical team is actively working to restore full service.

What you can do:
- Please try again in [estimated time, e.g., 1-2 hours]
- Your course progress and data are safe and will not be lost
- If you have an urgent need, please contact us at [support email/phone]

We apologize for the inconvenience and appreciate your patience as we work to resolve this.

Operation HOPE Support Team
```

### Client-Facing: Resolution Notification
```
Subject: Service Restored - Operation HOPE Systems

The technical issue affecting [Client Portal / online courses / certificate access] has been resolved. All systems are now operating normally.

If you experience any further issues, please contact us at [support email/phone].

Thank you for your patience.

Operation HOPE Support Team
```

### Internal: Incident Alert
```
INCIDENT ALERT - [Tier Level] - [Date/Time]

Impact: [Brief description of what is broken]
Systems Affected: [Portal / LMS / Dynamics / Certificates]
Clients Affected: [Estimated number or "all"]
Status: [Investigating / Mitigating / Resolved]

Current Actions:
- [What is being done right now]

Next Update: [Time of next status update]

Incident Lead: [Name]
```

### Partner/Funder Communication
```
Subject: Service Update - Operation HOPE Platform

Dear [Partner Name],

We wanted to proactively inform you of a temporary service disruption affecting [specific service]. Our technical team identified the issue at [time] and is actively working on a resolution.

Impact to your participants:
- [Specific impact description]

Expected resolution:
- [Estimated timeline]

We will provide an update within [timeframe]. Please direct any participant inquiries to [support contact].

Thank you for your partnership.

[Name]
Operation HOPE
```

## SLA Expectations

| Severity | Acknowledgment | First Update | Resolution Target | Executive Notification |
|----------|---------------|--------------|-------------------|----------------------|
| Tier 1 (Outage) | 15 minutes | 30 minutes | 4 hours | Immediate if 2+ hours |
| Tier 2 (Security) | 15 minutes | 30 minutes | 2 hours | Immediate |
| Tier 3 (Large-scale) | 30 minutes | 1 hour | 8 hours | If 4+ hours unresolved |
| Tier 4 (Reputational) | 1 hour | 2 hours | 24 hours | As needed |

## Response Template

"This issue has been classified as urgent and has been escalated to our technical team for immediate attention. We are actively working on a resolution and will provide an update within [timeframe based on SLA]. Your data is safe, and we will keep you informed throughout the process."

## Internal Notes

- Never communicate ETAs to clients unless confirmed with the engineering team.
- All security incidents (Tier 2) must be escalated regardless of scale; do not wait to assess scope.
- Keep the incident ticket updated in real time; this becomes the post-incident review source document.
- Post-incident reviews are mandatory for all Tier 1 and Tier 2 incidents. Findings should be documented and shared with the full support team.
- When in doubt about severity classification, escalate to the higher tier. It is always better to over-escalate than to under-escalate.
- For data breach scenarios, do not attempt to investigate the breach yourself. Secure the affected system and escalate to the security team immediately.
- Partner-facing communications must be reviewed by a manager before sending.
