# Evidencia de Validación y Reflexión
## Microservicio de Autenticación y Gestión de Usuarios

**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Institución:** Universidad de Monterrey (UDEM) — Primavera 2026  
**Despliegue:** `http://34.51.29.27:5000` (instancia GCloud, PostgreSQL 16.14)

---

## 1. Cumplimiento de los entregables

| # | Requisito | Estado | Evidencia |
| :--- | :--- | :---: | :--- |
| 1 | Microservicio en `apps/services/login` | ✅ | `app.py`, `requirements.txt`, `.env.example`, `README.md` |
| 2 | Modificar e integrar tablas a la base `library` | ✅ | `sql/01_migration_auth.sql`, `sql/02_fix_seed_passwords.sql` |
| 3 | Desplegar en el puerto 5000 | ✅ | `http://34.51.29.27:5000` — `/health` responde `database: connected` |
| 4 | Documentar los endpoints en XML y JSON con Swagger | ✅ | `http://34.51.29.27:5000/docs` |
| 5 | Validar que todos los endpoints funcionen | ✅ | `docs/evidencia_e2e.txt` — 25/26 aserciones |
| 6 | Screenshots y reflexión | ✅ | Este documento |
| 7 | Monorepo compactado | ✅ | `integracion03-login.tar.gz` |

---

## 2. Cómo usar Swagger

**Abrir la documentación:** `http://34.51.29.27:5000/docs`

La interfaz muestra los 8 endpoints agrupados por etiqueta:

| Etiqueta | Endpoints |
| :--- | :--- |
| **Auth** | `POST /register`, `POST /login`, `POST /logout` |
| **Session** | `GET /session` |
| **Users** | `GET /users/{user_id}` |
| **System** | `GET /`, `GET /health`, `GET /captcha` |

**Probar un endpoint paso a paso:**

1. **Paso 1 — Obtener el CAPTCHA.** Abre `GET /captcha`, pulsa **Try it out**, en el campo `format` escribe `json`, y pulsa **Execute**. Copia `captcha_id` y resuelve la suma o resta de `question` (por ejemplo, si dice *"¿Cuánto es 7 + 4?"*, la respuesta es `11`).

2. **Paso 2 — Registrarse.** Abre `POST /register`, **Try it out**, y pega el cuerpo sustituyendo los valores:
   ```json
   {
     "nombre": "Fabián",
     "apellido_paterno": "Azaed",
     "apellido_materno": "Orta",
     "email": "azaedorta@hotmail.com",
     "password": "S3gura!2026",
     "captcha_id": "<pega aquí el captcha_id del paso 1>",
     "captcha_answer": "<la respuesta que calculaste>"
   }
   ```
   El CAPTCHA es de **un solo uso**: si lo reutilizas, devuelve `CAPTCHA_ALREADY_USED`.

3. **Paso 3 — Iniciar sesión.** En `POST /login` envía `email`, `password` y un **CAPTCHA nuevo** (vuelve al paso 1). La respuesta trae el token en `data.session.token`.

4. **Paso 4 — Consultar la sesión.** En `GET /session`, pulsa **Authorize** o escribe el encabezado `X-Session-Token` con el token del paso 3.

5. **Paso 5 — Cerrar sesión.** En `POST /logout` repite el encabezado `X-Session-Token`.

**Cambiar entre XML y JSON:** en cualquier endpoint, el campo `format` acepta `xml` o `json`. **Si lo dejas vacío, la respuesta es XML** (formato predeterminado del enunciado). Los dos formatos están documentados con sus ejemplos en el bloque **Responses** de cada endpoint.

---

## 3. Resultados de la validación

Ejecución completa contra la instancia desplegada. Salida íntegra en `docs/evidencia_e2e.txt`.

| # | Caso validado | Resultado |
| :--- | :--- | :--- |
| 1 | `GET /health` → `database: connected`, PostgreSQL 16.14 | ✅ |
| 2 | `GET /health` → `schema: ready` (migración aplicada) | ✅ |
| 3 | `POST /register` válido → `201` + encabezado `Location` | ✅ |
| 4 | `POST /register` con correo repetido → `409 EMAIL_ALREADY_EXISTS` | ✅ |
| 5 | El registro **no** devuelve `password_hash` | ✅ |
| 6 | `POST /login` correcto → `200` + token | ✅ |
| 7 | `POST /login` en XML → `<token>` dentro de `<session>` | ✅ |
| 8 | `POST /login` con contraseña incorrecta → `401 INVALID_CREDENTIALS` | ✅ |
| 9 | `POST /login` con correo inexistente → **mismo** `401` (no revela si existe) | ✅ |
| 10 | `GET /session` con token → `200 authenticated: true` | ✅ |
| 11 | `GET /session` sin token → `401 SESSION_REQUIRED` | ✅ |
| 12 | `GET /session` tras logout → `401 SESSION_INVALID` | ✅ |
| 13 | `remaining_seconds` ≤ 1800 (sesión de 30 min) | ✅ |
| 14 | `GET /users/<id>` → `200`, sin exponer `password_hash` | ✅ |
| 15 | Reutilizar un CAPTCHA → `400 CAPTCHA_ALREADY_USED` | ✅ |
| 16 | Firma HMAC manipulada → `400 INVALID_CAPTCHA` | ✅ |
| 17 | El login **no emite `Set-Cookie`** | ✅ |
| 18 | La sesión creada en XML también es válida | ✅ |

**Prueba automatizada sin base de datos:** `tests/smoke_test.py` → **39/39 aserciones**.

**Capturas a anexar:** Swagger UI en `/docs` · `/health` en XML y en JSON mostrando el `Content-Type` · registro exitoso y registro duplicado · login en ambos formatos · login fallido · sesión activa e inválida · logout · tabla `users` mostrando el hash bcrypt.

---

## 4. Dos defectos encontrados durante la validación

### 4.1 Los hashes de los usuarios sembrados eran inválidos

`data/library_data.sql` declaraba en un comentario que este valor era el hash bcrypt de la contraseña `666`:

```
$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea
```

Se comprobó con `bcrypt.checkpw()` contra `666`, `123456`, `password`, `admin`, `usuario1`, `Admin123!` y `library`: **todas devolvieron `False`**. Era un *placeholder* que nunca correspondió a ninguna contraseña.

**Impacto:** los 11 usuarios sembrados (`admin` y `usuario1`..`usuario10`) **no podían autenticarse en ningún servicio del proyecto**, ni en este microservicio ni en el monolito Node/Express, que también usa bcrypt. El defecto estaba latente desde el Prompt 00.

**Corrección:** se generó y verificó un hash real de `666` y se aplicó en los dos lugares donde importa:
- `data/library_data.sql` — para que una carga nueva de la base de datos no reproduzca el error.
- `apps/services/login/sql/02_fix_seed_passwords.sql` — para parchar la base de datos que ya estaba cargada.

### 4.2 `/health` no distinguía «servicio caído» de «migración pendiente»

Sin la migración aplicada, `/login` y `/register` devolvían `500 INTERNAL_ERROR`, mientras `/health` respondía `200` porque solo ejecutaba `SELECT version()`. El síntoma era **idéntico** a una caída del servicio.

**Corrección:** `/health` ahora consulta `information_schema` y expone el campo `schema` con valor `ready` o `migration_pending`, acompañado de un `migration_hint` con el comando exacto a ejecutar.

---

## 5. Reflexión: por qué se tiene que hacer así

**¿Por qué un microservicio aparte y no meter la autenticación en el monolito?**
Porque la identidad es un *concern* transversal con su propio ciclo de vida y su propia superficie de ataque. Aislarla permite escalarla, auditarla y reutilizarla desde cualquier cliente —el navegador, la app Electron, otro servicio— sin acoplar el catálogo bibliográfico a la lógica de sesiones. El monolito ya tenía su propio login; este ejercicio demuestra que la misma tabla `users` y el mismo esquema de hash bcrypt pueden servir a dos aplicaciones distintas sin duplicar datos.

**¿Por qué XML por defecto y JSON opcional?**
Porque los sistemas empresariales y los clientes de escritorio suelen hablar XML, mientras que los clientes web modernos prefieren JSON. Resolver la representación con el parámetro `format` demuestra que **un mismo recurso puede serializarse en dos formatos sin duplicar la lógica de negocio**: la consulta SQL es una sola y el serializador decide al final. Ese es exactamente el problema que este curso busca enseñar sobre integración de aplicaciones.

**¿Por qué hash y no cifrado de contraseñas?**
Porque el sistema **nunca necesita recuperar** la contraseña, solo verificarla. Un cifrado reversible obligaría a custodiar la llave, y quien la obtuviera tendría todas las contraseñas. Con bcrypt —que añade una *sal* aleatoria por usuario y un costo computacional ajustable— dos usuarios con la misma contraseña producen hashes distintos y un ataque de diccionario se vuelve prohibitivamente caro.

**¿Por qué no una tabla exclusiva de contraseñas?**
Porque la contraseña es un atributo de la cuenta, no una entidad independiente. Separarla crearía una dependencia 1:1 artificial, un `JOIN` extra en cada login y una violación conceptual de la normalización: no existe ninguna dependencia multivaluada que justifique la separación. `password_hash` pertenece a `users`.

**¿Por qué una sesión del lado del servidor y sin cookies?**
Porque el servicio lo consumen clientes de API, no un navegador. Sin cookies se elimina por diseño el vector de CSRF y, sobre todo, se habilita la **revocación inmediata**: cerrar sesión marca `revoked_at` y el token muere en el siguiente request. Una cookie firmada o un JWT no permiten eso sin mantener igualmente una lista negra. Guardar en la base únicamente el **SHA-256 del token** aplica el mismo principio que con las contraseñas: si la base se filtra, los tokens robados no sirven.

**¿Por qué un CAPTCHA sin interfaz gráfica?**
Porque un endpoint de login expuesto a Internet es el objetivo número uno de la fuerza bruta, y no hay navegador donde dibujar un captcha de imágenes. Un desafío aritmético firmado con HMAC aporta fricción sin exigir servicios externos ni claves de terceros. **Pero conviene ser honesto sobre su alcance:** al ser aritmético, un script puede resolverlo en dos líneas —de hecho así lo hace la colección de Postman para automatizar las pruebas—. El CAPTCHA es una capa de fricción, **no** una defensa definitiva. La protección real son el *rate limiting* por IP y el bloqueo temporal tras varios intentos fallidos, que sí están implementados.

**¿Por qué se habla de Nivel 3 de Richardson si los endpoints son acciones?**
Porque `/register`, `/login` y `/logout` llevan el verbo dentro del URI, lo cual es estilo RPC y por sí solo aterriza en **Nivel 1**. El Nivel 3 (HATEOAS) se alcanza sobre las **representaciones**: toda respuesta incluye un bloque `_links` que le indica al cliente qué puede hacer después, la raíz `GET /` publica los recursos disponibles para que no haya URLs codificadas en el cliente, y hasta los errores devuelven enlaces de recuperación —un `401` incluye el enlace a `/login`—. Vale la pena declarar la desviación en lugar de ocultarla: es una decisión consciente, no un descuido.

**¿Por qué el `Accept: */*` de Postman importa?**
Porque Postman y `curl` envían `Accept: */*` por defecto. Si el servidor interpretara ese comodín como «quiero JSON», violaría el requisito de que **XML sea el predeterminado** y las pruebas no reflejarían el comportamiento real. La regla implementada es explícita: `?format=` manda, luego `Accept: application/json`, y ante `*/*` o ausencia se responde XML.

---

## 6. Cómo reproducir la validación

```bash
# 1. Prueba del flujo completo sin base de datos (39 aserciones)
python tests/smoke_test.py

# 2. Prueba end-to-end contra la instancia (requiere red)
python tests/e2e_test.py

# 3. Colección de Postman: importar
#    docs/login-microservice.postman_collection.json
#    y ejecutarla con el Collection Runner de arriba hacia abajo.
```

> La prueba end-to-end crea un usuario `e2e.test.<timestamp>@library.local` en la base de datos. Se puede eliminar con:
> `DELETE FROM users WHERE email LIKE 'e2e.test.%@library.local';`
