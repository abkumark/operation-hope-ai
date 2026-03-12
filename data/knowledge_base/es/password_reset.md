---
title: "Restablecimiento de contrasena del Client Portal de OH"
category: "password_reset"
type: "external"
auto_resolvable: true
queue: "IT Support"
language: "es"
last_updated: "2025-01-28"
---

# Restablecimiento de contrasena del Client Portal de OH

## Descripcion del problema
Un cliente necesita restablecer su contrasena del Client Portal de Operation HOPE. Esto puede deberse a una entrada corrupta en Azure AD o a un proceso de registro incompleto.

## Pasos de resolucion

1. **Verificar el correo electronico del usuario en Azure Active Directory**
   - Navegue a Azure Portal > All Users > Legacy Users
   - Busque la direccion de correo electronico del cliente

2. **Si el correo electronico EXISTE en Azure:**
   - Elimine la entrada de Azure AD
   - Indique al cliente que se vuelva a registrar usando la misma direccion de correo electronico

3. **Si el correo electronico NO se encuentra en Azure:**
   - Indique al cliente que complete el proceso de registro ("Sign up now") en el Client Portal

4. **Confirmar la resolucion**
   - Asegurese de que el cliente complete exitosamente el proceso de registro con la misma direccion de correo electronico

## Plantilla de respuesta

"Hemos revisado su cuenta en Azure. Por favor siga los pasos a continuacion: Asegurese de completar el proceso de registro. Si ya se habia registrado anteriormente, hemos restablecido su acceso. Por favor registrese nuevamente utilizando la misma direccion de correo electronico."

## Internal Notes

- Deleting the Azure AD entry allows the client to re-register with a fresh account.
- Always verify the client uses the same email address when re-registering.
- Allow a few minutes after deletion before the client attempts to sign up again.
