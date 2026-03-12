---
title: "Coach Follow-Ups Not Reporting on PowerBI Dashboard"
category: "follow_up_logging"
type: "internal"
auto_resolvable: false
queue: "IT Support"
last_updated: "2025-01-28"
---

# Coach Follow-Ups Not Reporting on PowerBI Dashboard

## Problem Description
Coach follow-up services are not appearing on the PowerBI dashboard. This may be due to follow-ups not being marked as completed, incorrect dates, or status not set properly in Dynamics 365.

## Resolution Steps

1. **Log into Dynamics 365**
   - Access the Dynamics 365 application

2. **Search for the client**
   - Search by client name
   - Open the client record

3. **Navigate to Programs**
   - Go to the Programs tab
   - Select the relevant program enrollment

4. **Open Follow-Ups & Recruitment tab**
   - Navigate to the Follow-Ups & Recruitment section
   - Locate the follow-up in question

5. **Verify the follow-up**
   - Confirm the date is within the desired reporting range
   - Verify the Status field is set to "completed"
   - If Status is not "completed," open the follow-up record and mark it as complete
   - Save the record

6. **Allow for reporting delay**
   - PowerBI dashboards typically refresh daily
   - The follow-up will report the following day after being marked complete

## Response Template

"The follow-up is now marked complete and will report the following day."

## Internal Notes

- Follow-ups must have Status = "completed" to appear on the PowerBI dashboard.
- Dashboard data refreshes on a schedule; allow up to 24 hours for updates.
- Verify the follow-up date falls within the reporting period being viewed.
