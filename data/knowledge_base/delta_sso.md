---
title: "Delta Employee SSO Login"
category: "delta_sso"
type: "external"
auto_resolvable: true
queue: "IT Support"
last_updated: "2025-01-28"
---

# Delta Employee SSO Login

## Problem Description
A Delta employee is having trouble logging into the Operation HOPE Client Portal. Delta employees must use a different login path—the "Sign in with Delta" option—which uses Single Sign-On (SSO) with their Delta email credentials.

## Resolution Steps

1. **Verify the user is a Delta employee**
   - Confirm they have a Delta email address (@delta.com or similar)
   - Delta employees cannot use the standard registration or login flow

2. **Instruct the correct login process**
   - Direct the client to use the "Sign in with Delta" option on the Client Portal login page
   - This will redirect them to the Delta SSO service
   - They should log in with their Delta email and Delta credentials

3. **Confirm access after login**
   - Once signed in via Delta SSO, they can view their coaches
   - They can enroll in the Delta ESP Program or Credit & Money Management Program as applicable

4. **If login still fails**
   - Verify their Delta email is correctly configured in Azure AD
   - Check if there are any Azure AD or SSO configuration issues
   - Escalate to IT if the Delta SSO integration is not working

## Response Template

"As a Delta employee, you will need to use the Delta Sign-In option to log in with your Delta email through the Single Sign-On (SSO) service."

## Internal Notes

- Delta employees must NEVER use the standard "Sign up now" or regular login—only "Sign in with Delta."
- The Delta SSO integration is separate from the standard Azure AD flow.
- If a Delta employee has previously registered with a personal email, they may need to use their Delta email and the Delta SSO path instead.
