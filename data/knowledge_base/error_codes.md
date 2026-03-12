---
title: "Common Error Messages and Meanings"
category: "no_information"
type: "internal"
auto_resolvable: false
queue: "IT Support"
last_updated: "2026-03-12"
---

# Common Error Messages and Meanings

## Problem Description
Clients and internal staff encounter error messages across Operation HOPE systems (Client Portal, EverFi LMS, Dynamics 365 CRM, and certificate generation). This article catalogs common errors, explains their root causes, and provides basic troubleshooting steps.

## Client Portal Errors

### "Unable to sign in. Please check your credentials and try again."
- **Root cause:** Incorrect email/password combination, or the Azure AD entry is corrupted.
- **Troubleshooting:**
  1. Confirm the client is using the correct email address (the one used during registration)
  2. Attempt a password reset through the Portal "Forgot Password" flow
  3. If reset fails, check Azure AD for the user entry (see password_reset.md)
  4. Delete and re-create the Azure AD entry if corrupted

### "Your account is not associated with an active program."
- **Root cause:** The client logged in successfully but has no active program enrollment in Dynamics 365, or the sync between Dynamics and the Portal has not completed.
- **Troubleshooting:**
  1. Verify the client has an active program enrollment in Dynamics 365
  2. Check if the enrollment was recently created (allow up to 24 hours for sync)
  3. If enrolled in Dynamics but not showing in Portal, trigger a manual sync (see multi_system_sync.md)

### "Session expired. Please log in again."
- **Root cause:** The client's authentication token timed out due to inactivity (default timeout: 30 minutes).
- **Troubleshooting:**
  1. Ask the client to log in again
  2. If this happens frequently during active use, check for browser cookie-blocking extensions
  3. Recommend using Chrome or Edge for best compatibility

### "An unexpected error occurred. Please try again later. (Error Code: 500)"
- **Root cause:** Server-side error in the Portal application. Could be caused by a failed API call, database timeout, or deployment issue.
- **Troubleshooting:**
  1. Ask the client to wait 5 minutes and retry
  2. Check the Portal application logs for the specific error stack trace
  3. If the error persists across multiple clients, escalate immediately as a potential outage

### "Access denied. You do not have permission to view this page."
- **Root cause:** The client is trying to access a resource they are not authorized for (e.g., a program they are not enrolled in, or an admin page).
- **Troubleshooting:**
  1. Verify the client's role and program enrollment
  2. If the client should have access, check their role assignment in the Portal admin panel
  3. Clear browser cache and retry

## EverFi LMS Errors

### "Course not available. Please contact your administrator."
- **Root cause:** The course has been deactivated, the enrollment period has closed, or the client's LMS account is not linked to the correct organization.
- **Troubleshooting:**
  1. Verify the course is active in the EverFi admin panel
  2. Check that the client's LMS account is associated with the Operation HOPE organization
  3. Re-enroll the client in the course if the enrollment was dropped

### "Unable to save progress. Please check your internet connection."
- **Root cause:** Network interruption during course activity, or the LMS session expired.
- **Troubleshooting:**
  1. Ask the client to check their internet connection and refresh the page
  2. Recommend completing courses on a stable Wi-Fi connection (not mobile data)
  3. If the issue persists, have the client clear browser cache and log in again
  4. Check EverFi system status page for any ongoing outages

### "You have already completed this course."
- **Root cause:** The client is attempting to re-enroll in or restart a course that is already marked 100% complete.
- **Troubleshooting:**
  1. Confirm the course shows 100% in the LMS admin panel
  2. If the client needs to retake the course, check whether the course allows re-enrollment
  3. Contact EverFi support if a manual enrollment reset is needed

### "Certificate generation failed. Please try again."
- **Root cause:** The certificate PDF generation service encountered an error, or the course completion record has not fully propagated.
- **Troubleshooting:**
  1. Verify all required courses are 100% complete in the LMS
  2. Ask the client to wait 15 minutes and retry
  3. Have the client try a different browser
  4. If the issue persists, generate the certificate manually through the admin panel

## Dynamics 365 CRM Errors (Internal Staff)

### "Duplicate record detected."
- **Root cause:** A contact or enrollment record with matching key fields (typically email) already exists.
- **Troubleshooting:**
  1. Search for the existing record using the email address
  2. Determine which record is the primary (most recent activity, most complete data)
  3. Merge the duplicate records following the Dynamics duplicate merge procedure
  4. Document the merge in the ticket notes

### "The record is unavailable. It may have been deleted or you may not have permission."
- **Root cause:** The record was deactivated/deleted by another user, or the current user's security role does not include read access.
- **Troubleshooting:**
  1. Check with the assigned coach or admin whether the record was intentionally deactivated
  2. If the record should exist, search for it in the "Inactive" records view
  3. If a permissions issue, request a role update through the Dynamics admin

### "Business process error: Required field is missing."
- **Root cause:** A workflow or business process flow requires a field value that was not provided (e.g., program type, coach assignment, or client goal).
- **Troubleshooting:**
  1. Identify the required field from the error message
  2. Fill in the missing field and retry the operation
  3. If the required field is unclear, consult the business process documentation or escalate to the Dynamics admin

### "Plugin execution failed. Contact your system administrator."
- **Root cause:** A Dynamics plugin (custom code triggered by a record action) encountered an unhandled exception.
- **Troubleshooting:**
  1. Note the exact operation being performed when the error occurred
  2. Check the Dynamics plugin trace log for the specific error details
  3. Escalate to the development team with the trace log entry

## HUD Certificate Process Errors

### "Certificate not available. Complete all required courses first."
- **Root cause:** One or more of the three required HUD courses (Before You Buy, Purchasing Your Home, After You Buy) is not marked as 100% complete.
- **Troubleshooting:**
  1. Check each course individually in the LMS for completion status
  2. If all courses show complete, check for sync delay (wait up to 24 hours)
  3. See hud_certificate.md for the full certification process

### "Unable to download certificate. File not found."
- **Root cause:** The certificate PDF was not generated successfully, or the file storage service is temporarily unavailable.
- **Troubleshooting:**
  1. Ask the client to refresh the page and try the download again
  2. Try a different browser (Chrome or Edge recommended)
  3. If the issue persists, regenerate the certificate from the admin panel

## Response Template

"I see you're encountering an error. Could you share the exact error message or a screenshot? This will help me identify the issue and provide the right solution. In the meantime, please try clearing your browser cache and logging in again."

## Internal Notes

- Always ask clients for the exact error message text or a screenshot before troubleshooting.
- Many client-facing errors resolve with a browser cache clear, different browser, or brief wait.
- Server-side errors (500-level) affecting multiple clients should be escalated immediately.
- Document any new or unrecognized error messages in this article for future reference.
- When in doubt about a Dynamics error, check the plugin trace log before escalating.
