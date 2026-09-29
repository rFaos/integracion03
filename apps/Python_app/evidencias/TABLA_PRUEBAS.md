# Pruebas del prototipo — Cliente de escritorio (Python + Tkinter)

**Aplicación:** `apps/Python_app` — consume los microservicios de Login (`:5000`) y Libros (`:5001`).
**Alumno:** Fabián Azaed Orta Singlaterry — Matrícula 613504

> Formato listo para pegar en la tabla *"Pruebas del prototipo"* del documento del equipo.
> Versión simplificada: 21 casos representativos de los 33 de la bitácora completa.

| Prueba | Descripción | Resultado esperado | Resultado obtenido |
|---|---|---|---|
| 1 | Registro de un usuario nuevo (`POST /register`) | Código 201 y cuenta creada | 201; cuenta creada y cabecera `Location` devuelta |
| 2 | Registro con un correo ya existente (`POST /register`) | Código 409 (conflicto) | 409; *"El correo ya está registrado"* |
| 3 | Inicio de sesión correcto (`POST /login`) | Código 200 y token de sesión | 200; devuelve token y fecha de expiración |
| 4 | Inicio de sesión con contraseña incorrecta (`POST /login`) | Código 401 | 401; *"El correo o la contraseña son incorrectos"* |
| 5 | Reabrir la aplicación con la sesión guardada (`GET /session`) | Código 200 (sesión válida) | 200; entra al panel sin pedir credenciales |
| 6 | Cerrar sesión y reutilizar el token (`POST /logout`, `GET /session`) | 200 al cerrar y 401 al reutilizar | 200 y luego 401; el token queda revocado |
| 7 | Modificar el perfil (`PATCH /profile`) | Código 200 | 200; solo cambian los campos enviados |
| 8 | Cambiar la contraseña con la actual incorrecta (`PATCH /profile`) | Código 403 | 403; `INVALID_CURRENT_PASSWORD` |
| 9 | Consultar el catálogo (`GET /books`) | Código 200 con la lista de libros | 200; 10 libros con formato, categoría, precio y existencia |
| 10 | Buscar por texto y rango de precio (`GET /books/search`) | Código 200 con resultados filtrados | 200; resultados filtrados correctamente |
| 11 | Ver el detalle de un libro (`GET /books/{isbn}`) | Código 200 con imágenes y conceptos | 200; incluye imágenes y conceptos asociados |
| 12 | Dar de alta un libro (`POST /books`) | Código 201 | 201; el libro aparece en el catálogo |
| 13 | Dar de alta un ISBN repetido (`POST /books`) | Código 409 | 409; *"El ISBN ya existe en la base de datos"* |
| 14 | Modificación parcial de un libro (`PATCH /books/{isbn}`) | Código 200, solo cambia lo enviado | 200; `modified_fields: ["stock"]`, el resto intacto |
| 15 | Modificación completa de un libro (`PUT /books/{isbn}`) | Código 200 | 200; el recurso se reemplaza por completo |
| 16 | `PUT` con campos faltantes (`PUT /books/{isbn}`) | Código 400 | 400; *"PUT requiere la representación completa del libro"* |
| 17 | Eliminar un libro y comprobarlo (`DELETE`, `GET`) | 200 al eliminar y 404 al consultar | 200 y luego 404; el libro ya no existe |
| 18 | Consultar un ISBN inexistente (`GET /books/{isbn}`) | Código 404 | 404; *"Libro no encontrado"* |
| 19 | Detener el servicio de libros (`GET /health`) | El semáforo pasa a rojo y la app no se cierra | Sin respuesta; semáforo rojo y la aplicación siguió funcionando |
| 20 | Restaurar el servicio de libros (`GET /health`) | El semáforo vuelve a verde | 200; vuelve a verde sin reiniciar la aplicación |
| 21 | Guardar la configuración y reabrir la aplicación | El valor guardado se conserva | `page_size=24` se relee desde `runtime/config.json` |

---

**Códigos HTTP cubiertos:** 200, 201, 400, 401, 403, 404, 409 y "sin respuesta" (servicio caído).

**Evidencia gráfica:** 30 capturas en `apps/Python_app/evidencias/` + `INFORME_EVIDENCIAS.pdf`.

> Bitácora completa con las 33 pruebas, la comparación `PUT` vs `PATCH` y la reflexión:
> `apps/Python_app/evidencias/BITACORA_Y_REFLEXION.md`.
