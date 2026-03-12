---
title: "Intake/Output Survey Not Accepting Values"
category: "survey_issue"
type: "external"
auto_resolvable: false
queue: "L&D"
last_updated: "2025-01-28"
---

# Intake/Output Survey Not Accepting Values

## Problem Description
A client cannot input certain values on an Intake or Output survey (e.g., unable to input "0" on a payment question). This may be a validation issue, a UI bug, or a configuration problem with the survey.

## Resolution Steps

1. **Gather information from the client**
   - What is the name of the program or course?
   - Which specific question or field is not accepting the value?
   - What value are they trying to enter (e.g., "0")?
   - Are there any error messages displayed?

2. **Verify expected behavior**
   - Check if "0" or the value in question is a valid response for that field
   - Review survey configuration for validation rules
   - Determine if this is a known limitation or a bug

3. **Provide workaround if available**
   - If "0" is valid but not accepted, document and escalate
   - If there is a known workaround (e.g., entering "0.00" or a different format), share with client

4. **Escalate if needed**
   - Create a ticket for the development team with program name, question/field, and value attempted
   - Include screenshot or description of the error if provided by client

## Response Template

"I understand that you're unable to input '0' on the page. To assist further, could you provide more information about the program or course you are completing?"

## Internal Notes

- Intake/Output surveys may have strict validation; verify whether "0" is an allowed value for the field.
- Document which programs and questions are affected for trend analysis.
- Some numeric fields may require a specific format (e.g., decimal places).
