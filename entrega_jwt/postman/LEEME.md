# Colección de Postman — nota sobre el secreto

## Cómo usarla

1. Importa los **dos** archivos de esta carpeta.
2. Selecciona el entorno **"Librería JWT · local (613504)"**.
3. Ajusta `base_url_login` y `base_url_books` si tu instancia no está en
   `172.32.132.174`.
4. Corre las carpetas **en orden** (00 → 06).

Las variables `access_token`, `refresh_token`, `captcha_id`, `isbn` y los cuatro
tokens maliciosos se llenan solas con los scripts de cada petición.

---

## Sobre `jwt_secret`: léelo antes de preguntar por qué está ahí

El archivo `Libreria_JWT_UDEM_613504.postman_environment.json` incluye el valor
**real** del secreto HS256 de la instancia de pruebas:

```
jwt_secret = integracion03-jwt-hs256-compartido-UDEM-613504-2f8a91c4d7e6b0a3
```

**Esto es intencional, y conviene entender por qué antes de copiarlo a un proyecto
de verdad.**

### Por qué está

La carpeta `05 · Ataques contra el JWT` **fabrica tokens maliciosos en tiempo de
ejecución** con `CryptoJS` dentro de Postman: un `alg:none`, uno firmado con otro
secreto, uno expirado y uno con audiencia ajena. Para que dos de esos ataques sean
significativos —el token expirado y el de audiencia ajena— hay que firmarlos con la
**clave real**, porque si no, el servidor los rechazaría por firma inválida y la
prueba no demostraría nada.

La alternativa era pre-generar los tokens y pegarlos en la colección, pero caducan
en 15 minutos y la colección dejaría de funcionar al día siguiente.

Poner el secreto en la **variable de entorno** (y no dentro de la colección) es
además la forma de enseñar el principio correcto: la clave se inyecta desde fuera,
igual que en producción se inyecta desde una variable de entorno o un secret
manager.

### Por qué esto NO es lo que se debe hacer en producción

Un archivo de entorno de Postman **es un archivo de código**: se versiona, se
comparte, se sube al repositorio. Un secreto ahí está tan expuesto como si estuviera
escrito en el `app.py`. En este proyecto se acepta porque:

- la instancia es **local y desechable** (una base PostgreSQL de prácticas);
- el profesor necesita que la colección **corra tal cual**, sin configurar nada;
- el valor no protege nada real.

En un proyecto real, el mismo ejercicio se resolvería así:

| Alternativa | Cómo |
|---|---|
| **No firmar los ataques** | Ejecutar los tres casos que no necesitan la clave (`alg:none`, firma ajena, token basura) y dejar los otros dos para un script de servidor |
| **Token de vida larga generado en el momento** | Un `pre-request` que llame a un endpoint de pruebas que emita un token expirado a propósito |
| **Secreto en el gestor de Postman** | Postman Vault / variables de tipo *secret* no exportadas, que cada quien llena en su equipo |
| **Claves asimétricas (RS256/ES256)** | Los servicios verifican con la **clave pública** (JWKS). Filtrar la pública no permite firmar nada, así que el problema desaparece |

Esa última fila es la respuesta correcta de fondo: **con HS256 cualquier servicio que
verifique puede también firmar**, porque comparten la misma clave. Es el precio de
simetría, y es exactamente el motivo por el que los sistemas con varios servicios
suelen pasar a RS256.

> En el repositorio, el valor real del secreto vive en `apps/services/login/.env` y
> `apps/services/soap/.env`, que **sí** están en `.gitignore`. Los `.env.example`
> llevan un placeholder (`cambia_esto_por_un_secreto_largo_aleatorio...`), que es lo
> que corresponde versionar.
