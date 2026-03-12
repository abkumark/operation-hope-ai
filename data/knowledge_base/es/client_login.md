---
title: "El cliente no puede iniciar sesion en el Client Portal de OH"
category: "account_access"
type: "external"
auto_resolvable: true
queue: "IT Support"
language: "es"
last_updated: "2025-01-28"
---

# El cliente no puede iniciar sesion en el Client Portal de OH

## Descripcion del problema
Un cliente no puede iniciar sesion en el Client Portal de Operation HOPE. Esto puede deberse a un registro incompleto, una entrada corrupta en Azure Active Directory o una fuente de identidad incorrecta.

## Pasos de resolucion

1. **Verificar el correo electronico del usuario en Azure Active Directory**
   - Navegue a Azure Portal > All Users > Legacy Users List
   - Busque la direccion de correo electronico del cliente

2. **Si el correo electronico NO se encuentra en Azure:**
   - Informe al cliente que su cuenta aun no existe
   - Indique al cliente que complete el proceso de registro ("Sign up now") en el Client Portal

3. **Si el correo electronico EXISTE pero el inicio de sesion sigue fallando:**
   - Seleccione la entrada del correo electronico en Azure
   - Haga clic en "Delete User" para eliminar la entrada corrupta
   - Pida al cliente que se vuelva a registrar usando la misma direccion de correo electronico

4. **Si el campo Source muestra "Other" en lugar de "Azure Active Directory":**
   - Esto indica una fuente de identidad mal configurada
   - Seleccione la entrada en Azure
   - Haga clic en "Delete User"
   - Pida al cliente que inicie sesion nuevamente para recrear la cuenta con la fuente correcta

5. **Si el cliente es empleado de Delta:**
   - Siga los mismos pasos de verificacion y eliminacion descritos anteriormente
   - Indique al cliente que haga clic en "Sign in with Delta" en lugar del boton de inicio de sesion estandar

## Plantilla de respuesta

"Hemos revisado su cuenta en Azure. Por favor siga los pasos a continuacion: Asegurese de completar el proceso de registro. Si ya se habia registrado anteriormente, hemos restablecido su acceso. Por favor registrese nuevamente utilizando la misma direccion de correo electronico. Haganos saber si el problema continua."

## Internal Notes

- Always check the "Source" column in Azure AD. Entries showing "Other" instead of "Azure Active Directory" are known to cause login failures.
- Delta clients must use the Delta SSO login path, not the standard registration flow.
- After deleting a user entry, allow a few minutes before asking the client to re-register.
- If the issue persists after re-registration, escalate to the Azure AD administrator.
