---
title: "Password Reset for OH Client Portal"
category: "password_reset"
type: "external"
auto_resolvable: true
queue: "IT Support"
last_updated: "2025-01-28"
---

# Password Reset for OH Client Portal

## Problem Description
A client needs to reset their password for the Operation HOPE Client Portal. This may involve a corrupted Azure AD entry or an incomplete sign-up process.

## Resolution Steps

1. **Verify the user email in Azure Active Directory**
   - Navigate to Azure Portal > All Users > Legacy Users
   - Search for the client's email address

2. **If the email EXISTS in Azure:**
   - Delete the entry from Azure AD
   - Instruct the client to re-register using the same email address

3. **If the email is NOT found in Azure:**
   - Instruct the client to complete the "Sign up now" process on the Client Portal

4. **Confirm resolution**
   - Ensure the client successfully completes the sign-up process with the same email address

## Response Template

"We have reviewed your account in Azure. Please follow the steps below: Ensure you complete the Sign-Up process. If you have already signed up, we've reset your access. Please sign up again using the same email address."

## Internal Notes

- Deleting the Azure AD entry allows the client to re-register with a fresh account.
- Always verify the client uses the same email address when re-registering.
- Allow a few minutes after deletion before the client attempts to sign up again.
