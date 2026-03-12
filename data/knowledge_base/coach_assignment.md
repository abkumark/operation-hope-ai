---
title: "Coach Assignment or Coach Change Request"
category: "coach_assignment"
type: "external"
auto_resolvable: false
queue: "IT Support"
last_updated: "2025-01-28"
---

# Coach Assignment or Coach Change Request

## Problem Description
A client wants to change coaches or needs a coach assigned to their program. This requires updating the enrollment record in Dynamics 365 and ensuring the HI Location is correctly set.

## Resolution Steps

1. **Search for the client in Dynamics 365**
   - Open Dynamics 365 and search for the client by name or email

2. **Navigate to Programs**
   - Open the client's profile
   - Go to the Programs tab
   - Select the relevant enrollment

3. **Update coach details**
   - Replace the old coach with the new coach in the enrollment record
   - Click Save

4. **Verify "Working with coach" field**
   - Ensure the "Working with coach" field is set to "Yes"

5. **Update HI Location**
   - Use Advanced Find to locate the enrollment
   - Update the HI Location field as needed

## Response Template

"The client has been successfully transferred to the new coach. The program details and location have been updated. Please confirm the changes in Dynamics."

## Internal Notes

- Always verify the "Working with coach" field is set to "Yes" after coach changes.
- HI Location must be updated via Advanced Find for reporting accuracy.
- Document the coach change in the client record for audit purposes.
