---
title: "LMS/Portal/Dynamics Multi-System Sync Troubleshooting"
category: "lms_enrollments"
type: "internal"
auto_resolvable: false
queue: "IT Support"
last_updated: "2026-03-12"
---

# LMS/Portal/Dynamics Multi-System Sync Troubleshooting

## Problem Description
Data is not synchronizing correctly between the three core Operation HOPE systems: EverFi LMS (course completions and enrollments), the Client Portal (client-facing dashboard), and Dynamics 365 CRM (coach records, program tracking, and reporting). This manifests as enrollment mismatches, missing completion records, stale client data, or discrepancies between what coaches see in Dynamics and what clients see in the Portal.

## Common Sync Failure Scenarios

### Scenario 1: LMS completion not reflected in Client Portal
- Client completes a course in EverFi but the Portal still shows it as incomplete.
- **Typical cause:** Sync job delay or failure between EverFi and the Portal database.
- **Expected sync window:** Up to 24 hours under normal conditions.

### Scenario 2: Portal enrollment missing from Dynamics 365
- A client enrolls in a program through the Portal, but the coach cannot see the enrollment in Dynamics.
- **Typical cause:** API integration failure between Portal and Dynamics, or the enrollment record was created with a mismatched email address.

### Scenario 3: Dynamics record updates not pushing to Portal
- A coach updates client information or program status in Dynamics, but the Portal does not reflect the change.
- **Typical cause:** Outbound sync from Dynamics is queued or the Dynamics plugin encountered an error.

### Scenario 4: Duplicate or conflicting records across systems
- The same client appears with slightly different data in each system (e.g., different email casing, name spelling).
- **Typical cause:** Client registered separately in each system instead of going through the unified enrollment flow.

## Resolution Steps

1. **Identify which systems are out of sync**
   - Check the client record in all three systems (EverFi LMS, Client Portal, Dynamics 365)
   - Note the specific data points that differ (enrollment status, completion percentage, program assignment, contact info)

2. **Check the sync job status**
   - Review the integration dashboard for recent sync job runs
   - Look for failed jobs or jobs stuck in a pending state
   - Note any error messages or exception logs from the most recent run

3. **Verify client identity across systems**
   - Confirm the client is using the same email address in all three systems
   - Check for duplicate records in Dynamics 365 (Contacts > search by name and email)
   - Check for duplicate LMS accounts in EverFi admin panel

4. **For LMS-to-Portal sync issues:**
   - Verify the course shows 100% completion in the EverFi admin panel
   - If complete in LMS but not in Portal, trigger a manual sync for that client record
   - If manual sync fails, log the error and escalate to the development team

5. **For Portal-to-Dynamics sync issues:**
   - Check the Dynamics integration queue for pending or failed messages
   - Verify the Portal API credentials have not expired
   - Attempt a manual push of the enrollment record from the Portal admin tools

6. **For Dynamics-to-Portal sync issues:**
   - Check the Dynamics plugin trace logs for errors
   - Verify the outbound integration endpoint is reachable
   - Manually update the Portal record if the sync cannot be restored quickly

7. **If sync cannot be restored:**
   - Manually reconcile the data in the target system based on the source of truth
   - Source of truth hierarchy: EverFi LMS (for course data) > Dynamics 365 (for program/coach data) > Client Portal (for display)
   - Document the manual correction and escalate the underlying sync failure

## Manual Sync Procedures

### Triggering a Manual LMS Sync
- Access the Portal admin panel > Integration Settings > EverFi Sync
- Select the affected client by email address
- Click "Sync Now" and monitor the job status
- Allow up to 15 minutes for the sync to complete

### Triggering a Manual Dynamics Sync
- Access the Dynamics 365 admin area > System Jobs
- Filter for failed or suspended integration jobs
- Resume or retry the failed job
- If the job cannot be retried, create a new manual sync request through the integration dashboard

## Common Error States

| Error | System | Meaning |
|-------|--------|---------|
| `SYNC_TIMEOUT_LMS` | Portal | EverFi API did not respond within the expected window |
| `DUPLICATE_CONTACT` | Dynamics | A contact with the same email already exists; merge required |
| `AUTH_TOKEN_EXPIRED` | Portal/Dynamics | API authentication token needs renewal |
| `ENROLLMENT_MISMATCH` | Portal | Program ID in Portal does not match any active Dynamics program |
| `RECORD_LOCKED` | Dynamics | Another process is updating the same record; retry after a few minutes |

## Response Template

"We've identified a sync delay between our systems affecting your account. Our team is working to reconcile the data. This process may take up to 24 hours. If the issue persists after that, we will follow up with you directly."

## Internal Notes

- Always check all three systems before concluding a sync issue exists; the problem may be isolated to one system.
- The source of truth for course completion data is always EverFi LMS, not the Portal display.
- The source of truth for program enrollment and coach assignment is Dynamics 365.
- Document all manual sync interventions in the ticket for audit purposes.
- Recurring sync failures for the same integration point should be escalated to the development team with error logs attached.
- Sync jobs run on a scheduled cadence; check the schedule before assuming a failure has occurred.
