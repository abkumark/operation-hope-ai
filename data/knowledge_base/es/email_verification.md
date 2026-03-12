---
title: "No se puede registrar o verificar el correo electronico"
category: "account_access"
type: "external"
auto_resolvable: true
queue: "IT Support"
language: "es"
last_updated: "2025-01-28"
---

# No se puede registrar o verificar el correo electronico

## Descripcion del problema
Un cliente no puede completar el proceso de registro o verificar su direccion de correo electronico en el Client Portal de Operation HOPE. Esto puede incluir no recibir el codigo de verificacion o encontrar errores durante la creacion de la contrasena.

## Pasos de resolucion

1. Navegue al Client Portal de Operation HOPE
2. Haga clic en el boton **Register**
3. Ingrese la direccion de correo electronico del cliente en el formulario de registro
4. Revise la bandeja de entrada del correo electronico en busca del codigo de verificacion
   - Si el codigo no esta en la bandeja de entrada, revise la carpeta de **Spam** o **Correo no deseado**
   - El correo de verificacion se envia desde el sistema del portal de Operation HOPE
5. Ingrese el codigo de verificacion en el portal cuando se le solicite
6. Cree una contrasena que cumpla con los siguientes requisitos:
   - Minimo 8 caracteres
   - Al menos una letra mayuscula
   - Al menos una letra minuscula
   - Al menos un caracter especial (por ejemplo: !, @, #, $)
   - Al menos un numero

## Plantilla de respuesta

"Para completar su registro, por favor siga estos pasos: Vaya al Client Portal de Operation HOPE y haga clic en Register. Ingrese su direccion de correo electronico, luego revise su bandeja de entrada (y la carpeta de spam o correo no deseado) para encontrar el codigo de verificacion. Ingrese el codigo cuando se le solicite y cree una contrasena de al menos 8 caracteres que incluya una letra mayuscula, una letra minuscula, un caracter especial y un numero. Haganos saber si necesita asistencia adicional."

## Preguntas de seguimiento

- Recibio el correo de verificacion? Si no, ha revisado su carpeta de spam o correo no deseado?
- Ve algun mensaje de error especifico durante el proceso de registro?
- Que proveedor de correo electronico utiliza (Gmail, Outlook, Yahoo, etc.)?

## Internal Notes

- Some email providers may delay delivery of the verification code by several minutes.
- If the client repeatedly does not receive the verification email, verify that the email address is correctly spelled and check Azure AD for any existing entries that may conflict.
- Corporate or organizational email filters may block the verification email. Suggest using a personal email address as an alternative.
