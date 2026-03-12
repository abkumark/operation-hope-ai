---
title: "Client Cannot Log In to the OH Client Portal"
category: "account_access"
type: "external"
auto_resolvable: true
queue: "IT Support"
last_updated: "2025-01-28"
---

# Client Cannot Log In to the OH Client Portal

## Problem Description
A client is unable to log in to the Operation HOPE Client Portal. This may be caused by an incomplete registration, a corrupted Azure Active Directory entry, or an incorrect identity source.

## Resolution Steps

1. **Verify the user email in Azure Active Directory**
   - Navigate to Azure Portal > All Users > Legacy Users List
   - Search for the client's email address

2. **If the email is NOT found in Azure:**
   - Inform the client that their account does not exist yet
   - Instruct the client to complete the "Sign up now" process on the Client Portal

3. **If the email EXISTS but login still fails:**
   - Select the email entry in Azure
   - Click "Delete User" to remove the corrupted entry
   - Ask the client to re-register using the same email address

4. **If the Source field shows "Other" instead of "Azure Active Directory":**
   - This indicates a misconfigured identity source
   - Select the entry in Azure
   - Click "Delete User"
   - Ask the client to sign in again to re-create the account with the correct source

5. **If the client is a Delta employee:**
   - Follow the same verification and deletion steps as above
   - Instruct the client to click "Sign in with Delta" instead of the standard login button

## Response Template

"We have reviewed your account in Azure. Please follow the steps below: Ensure you complete the Sign-Up process. If you have already signed up, we've reset your access. Please sign up again using the same email address. Let us know if the issue persists."

## Internal Notes

- Always check the "Source" column in Azure AD. Entries showing "Other" instead of "Azure Active Directory" are known to cause login failures.
- Delta clients must use the Delta SSO login path, not the standard registration flow.
- After deleting a user entry, allow a few minutes before asking the client to re-register.
- If the issue persists after re-registration, escalate to the Azure AD administrator.
