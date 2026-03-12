---
title: "Duplicate Client Records in Dynamics 365"
category: "duplicate_records"
type: "internal"
auto_resolvable: false
queue: "IT Support"
last_updated: "2025-01-28"
---

# Duplicate Client Records in Dynamics 365

## Problem Description
Duplicate client records exist in Dynamics 365 that need to be merged into a single record. This can occur when a client registers multiple times or when data is imported from different sources.

## Resolution Steps

1. **Open Advanced Find in Dynamics 365**
   - Navigate to Dynamics 365 and open the Advanced Find tool

2. **Search for the duplicate records**
   - Select "Contacts" as the entity
   - Filter by the client's full name or email address
   - Add the HOPE Client ID column via Edit Columns for easier identification

3. **Identify the records to merge**
   - Review the search results and select the two duplicate records
   - Determine which record to retain (usually the one with more complete or recent data)

4. **Perform the merge**
   - Select both duplicate records
   - Click the Merge button on the toolbar
   - Follow the merge wizard to combine the records
   - Ensure the primary (master) record is correctly selected

5. **Verify the merge**
   - Open the retained record and confirm all relevant information was preserved
   - Check that program enrollments and follow-ups are associated with the correct record

## Response Template

"The duplicate client records have been merged successfully. Please verify that the retained record contains the correct information."

## Internal Notes

- Always identify which record to retain before merging; the secondary record will be deactivated.
- Program enrollments and activities from the merged record should transfer to the primary record.
- Document the merge in case rollback or audit is needed.
