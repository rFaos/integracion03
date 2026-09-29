# Bitácora de integración y reflexión

**Aplicación:** `apps/Python_app` — cliente de escritorio de los microservicios de
Login (`:5000`) y Libros (`:5001`).
**Tecnología:** Python 3.14 + Tkinter. Dependencia opcional: Pillow (portadas).
**Alumno:** Fabián Azaed Orta Singlaterry — Matrícula 613504

---

## 1. Bitácora de pruebas

Todas las pruebas se ejecutaron contra los microservicios **en ejecución real**, no
contra datos simulados. La columna *Resultado HTTP* es el código que devolvió el
servicio, medido durante la sesión de pruebas.

| # | Acción realizada | Endpoint | Resultado HTTP | Resultado observado |
|---|---|---|---|---|
| 01 | Comprobar el estado de los dos servicios | `GET /health` (ambos) | 200 | Los dos semáforos en verde; fecha y hora de la última comprobación visibles |
| 02 | Pedir el desafío obligatorio | `GET /captcha` | 200 | Devuelve `captcha_id` y una pregunta aritmética |
| 03 | Registrar un usuario nuevo | `POST /register` | **201** | Cuenta creada; `Location: /users/{id}` |
| 04 | Registrar el mismo correo otra vez | `POST /register` | **409** | *"El correo ya está registrado."* |
| 05 | Iniciar sesión con contraseña incorrecta | `POST /login` | **401** | *"El correo o la contraseña son incorrectos."* |
| 06 | Iniciar sesión correctamente | `POST /login` | 200 | Devuelve token de sesión y fecha de expiración |
| 07 | Reabrir la aplicación con sesión guardada | `GET /session` | 200 | Entra directo al panel sin pedir credenciales |
| 08 | Extender la sesión | `POST /session/extend` | 200 | Nueva fecha de expiración |
| 09 | Modificar el perfil | `PATCH /profile` | 200 | Cambios aplicados solo a los campos enviados |
| 10 | Cambiar contraseña con la actual incorrecta | `PATCH /profile` | **403** | `INVALID_CURRENT_PASSWORD` |
| 11 | Consultar el catálogo | `GET /books?format=json` | 200 | 10 libros con formato, categoría, precio y existencia |
| 12 | Buscar por texto y rango de precio | `GET /books/search` | 200 | Resultados filtrados correctamente |
| 13 | Ver el detalle de un libro | `GET /books/{isbn}` | 200 | Incluye imágenes y conceptos asociados |
| 14 | Dar de alta un libro | `POST /books` | **201** | Libro creado y visible en el catálogo |
| 15 | Dar de alta un ISBN repetido | `POST /books` | **409** | *"El ISBN '…' ya existe en la base de datos"* |
| 16 | Modificación parcial (solo `stock`) | `PATCH /books/{isbn}` | 200 | `modified_fields: ["stock"]`; el resto intacto |
| 17 | Modificación completa del libro | `PUT /books/{isbn}` | 200 | Representación completa reemplazada |
| 18 | `PUT` con campos faltantes | `PUT /books/{isbn}` | **400** | *"PUT requiere la representación completa del libro"* |
| 19 | Consultar un ISBN inexistente | `GET /books/{isbn}` | **404** | *"Libro no encontrado"* |
| 20 | Eliminar un libro (con confirmación previa) | `DELETE /books/{isbn}` | 200 | Libro eliminado del catálogo |
| 21 | Comprobar el libro eliminado | `GET /books/{isbn}` | **404** | Confirma que ya no existe |
| 22 | **Caso A:** los dos servicios disponibles | `GET /health` | 200 / 200 | 🟢 Login y 🟢 Libros |
| 23 | **Caso B:** detener el servicio de libros en caliente | `GET /health` | *sin respuesta* | 🔴 Libros, 🟢 Login; **la aplicación no se cerró** |
| 24 | Usar el catálogo con el servicio caído | `GET /books` | *sin respuesta* | Mensaje comprensible, ventana intacta |
| 25 | **Caso C:** restaurar el servicio de libros | `GET /health` | 200 | 🔴 → 🟢 sin reiniciar la aplicación |
| 26 | **Caso D:** configurar un puerto incorrecto (`:5999`) | `GET /health` | *sin respuesta* | 🔴 en ambos; la aplicación siguió viva |
| 27 | Volver a las direcciones correctas | `GET /health` | 200 | 🟢 en ambos |
| 28 | Cerrar sesión | `POST /logout` | 200 | Token local borrado; el correo recordado se conserva |
| 29 | Ciclo individual `POST → GET → PATCH → GET → DELETE → GET` | `/books` | 201 / 200 / 200 / 200 / 200 / **404** | Título `PRUEBA INTEGRACION - 613504` creado, modificado, consultado y eliminado |
| 30 | Iniciar sesión con una cuenta deshabilitada | `POST /login` | **403** | `ACCOUNT_DISABLED` → *"La cuenta todavía no puede autenticarse: está deshabilitada."* (la cuenta se reactivó después de la prueba) |
| 31 | Reabrir la aplicación con una sesión revocada en el servidor | `GET /session` | **401** | La aplicación borra el token y vuelve al catálogo: *"El servidor ya no reconoce la sesión guardada (expiró o fue cerrada)."* |
| 32 | Dejar la sesión a 2 minutos de expirar | — | — | Aviso automático en pantalla y botón *"Extender sesión"* en la cabecera |
| 33 | Guardar la configuración, cerrar y volver a abrir | — | — | El valor guardado (`page_size=24`) se relee desde `runtime/config.json` |

> Las pruebas 22 a 27 y 31 se ejecutaron con la aplicación **en ejecución**, deteniendo y
> restaurando el microservicio de libros y revocando la sesión en el servidor, para
> comprobar que la ventana nunca se cierra ni se queda colgada.

### Códigos HTTP observados y su interpretación en la aplicación

| Código | Significado | Mensaje que ve el usuario |
|---|---|---|
| 200 / 201 | Operación correcta | Confirmación en la franja superior |
| 400 | Petición incompleta | *"PUT requiere la representación completa del libro"* |
| 401 | Credenciales incorrectas | *"El correo o la contraseña son incorrectos."* |
| 403 | Falta confirmación de contraseña | *"La contraseña actual no es correcta."* |
| 404 | El recurso no existe | *"Libro no encontrado"* |
| 409 | Conflicto (dato duplicado) | *"El ISBN '…' ya existe en la base de datos"* |
| 503 | El servicio está vivo pero sin base de datos | 🟡 Ámbar: *"Servicio accesible, base de datos no disponible"* |
| *sin respuesta* | Servicio caído o puerto incorrecto | 🔴 Rojo: *"El servicio no responde"* |

---

## 2. Diferencia entre `PUT` y `PATCH` (lo que realmente se envió)

**`PUT` — actualización completa.** Se envió la representación **entera** del libro:
título, año, precio, existencia, formato, categoría, autores y géneros. `PUT` reemplaza
el recurso, así que el servicio responde **400** si falta algún campo editable. En la
aplicación corresponde a la pantalla de edición completa.

**`PATCH` — actualización parcial.** Se envió **un solo atributo**, por ejemplo:

```json
PATCH /books/978-6135040001
{ "stock": 9 }
```

El servicio responde con `modified_fields: ["stock"]` y deja todo lo demás como estaba.
Se eligió `PATCH` precisamente porque el usuario solo quería cambiar la existencia: no
tiene sentido reenviar el libro completo (y sería peligroso, porque un `PUT` mal
formado puede borrar datos).

> **Nota de implementación:** el microservicio de libros **no traía `PATCH`**, y el de
> login no traía `PATCH /profile` ni `POST /session/extend`. Se añadieron a los
> servicios reutilizando su lógica existente, para poder demostrar la diferencia real
> entre `PUT` y `PATCH` en lugar de simularla.

---

## 3. Reflexión

La parte que más me costó fue **la sesión**. El microservicio de login no usa cookies:
devuelve un token que hay que enviar en la cabecera `X-Session-Token` en cada petición.
Además, `/login` y `/register` exigen resolver un CAPTCHA, algo que el enunciado no
menciona.

El problema más difícil fue un **403 al cambiar la contraseña** con la actual correcta.
Comprobé el hash en la base con `bcrypt.checkpw` y era válido, así que el fallo estaba en
mi cliente: `update_profile` sobrescribía `current_password` con una cadena vacía aunque
ya viniera en los cambios. El servicio recibía una contraseña en blanco y la rechazaba;
lo corregí para que solo la establezca cuando falta.

También apareció un fallo de **hilos**: llamaba a `after()` desde el hilo trabajador y Tk
no lo admite. Lo resolví con una cola que el hilo principal vacía en su bucle.

Cuando un microservicio deja de responder, la aplicación **no se cierra ni se congela**:
su semáforo pasa a rojo, el aviso explica qué pasó y el resto de pantallas siguen
funcionando. Al restaurarlo, vuelve a verde solo.

Entre local y remoto no cambia **nada del programa**: solo la dirección configurada. En
local la respuesta es inmediata; en la instancia se nota la latencia de red, por eso los
tiempos de espera son configurables.

Lo que más claro me quedó es la separación de responsabilidades: el cliente nunca toca la
base de datos, solo habla HTTP con el microservicio, y es este quien decide qué hacer con
PostgreSQL. Por eso pude apagar el servicio de libros y la aplicación siguió en pie.
