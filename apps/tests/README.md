# Pruebas de estrés con Locust: microservicio de libros

Prueba de carga con **20 usuarios simultáneos** contra el microservicio de libros
(`apps/services/soap`), desplegado en la VM de Google Cloud:

```
http://34.51.2.102:5001
```

| Archivo | Para qué sirve |
|---|---|
| `locustfile.py` | Escenario de la prueba: qué endpoints se llaman y con qué frecuencia. |
| `locust.conf` | Valores por defecto (host, 20 usuarios, ritmo de arranque, duración). La GUI ya los muestra rellenados. |

---

## 1. Qué se prueba

Los 20 usuarios se reparten en dos perfiles (proporción 3 a 1):

### `LectorCatalogo`: 15 usuarios, solo lectura (públicos, sin token)

Los tres endpoints que pide el enunciado llevan el mayor peso:

| Endpoint | Respuesta esperada |
|---|---|
| `GET /books` | 200, JSON |
| `GET /books?format=json` | 200, JSON |
| `GET /books?format=xml` | 200, XML |

Y el resto de lecturas del microservicio:

| Endpoint | Descripción |
|---|---|
| `GET /` | Portada del servicio |
| `GET /health` | Sonda de salud (BD, Redis, JWT) |
| `GET /catalogs` · `GET /api/catalogs` | Formatos, categorías, autores y géneros |
| `GET /books?isbn=<isbn>` | Filtro por ISBN |
| `GET /books/<isbn>` (JSON y `?format=xml`) | Detalle de un libro |
| `GET /books/author/<id>` · `GET /api/book/author/<id>` | Libros de un autor |
| `GET /books/<isbn>/temas` · `/books/<isbn>/topics` | Temas de un libro |
| `GET /books/temas` · `/books/topics` | Temas de todo el catálogo |
| `GET /books/search?q=&author=&genre=&year=&min_price=&max_price=` | Búsqueda multicriterio |
| `GET /wsdl` · `GET /soap?wsdl` | Contrato WSDL del servicio SOAP |
| `GET /api/books` · `GET /api/book/<isbn>` | Alias heredados |

Los ISBN y los id de autor se leen del propio servicio al iniciar la prueba, así
que siempre se piden recursos que existen.

### `EditorCatalogo`: 5 usuarios, escrituras protegidas con JWT

| Endpoint | Descripción |
|---|---|
| `POST /books` → `GET` → `PUT /books/<isbn>` → `PATCH /books/<isbn>` → `DELETE /books/<isbn>` | Ciclo CRUD completo sobre un libro desechable (ISBN `LC-…`) |
| `POST /api/book/insert` → `/api/book/update/<isbn>` → `/api/book/patch/<isbn>` → `/api/book/delete/<isbn>` | El mismo ciclo por los alias heredados |
| `POST /books` **sin token** | Debe responder **401** (comprueba que la protección aguanta la carga) |
| `POST /soap` `ObtenerConceptosPendientes` | Operación SOAP |
| `POST /soap` `ObtenerEstadisticasPorModelo` | Operación SOAP |
| `POST /soap` `ObtenerProgresoUsuario` | Operación SOAP |
| `POST /soap` `RegistrarClasificacion` | Operación SOAP |

Cada libro de prueba se crea y se borra en la misma tarea, así que el catálogo
queda igual que antes de la prueba.

**Cómo se obtiene el token:** al pulsar *Start*, el locustfile hace **un solo**
login en el servicio de autenticación (`:5000`): pide `GET /captcha`, resuelve
la suma o resta y envía `POST /login`. Los 5 editores comparten ese JWT, que se
renueva solo cada 10 minutos. Si cada usuario hiciera su propio login, el
limitador del servicio (20 peticiones por minuto y por IP) cortaría la prueba.

Por defecto usa el usuario sembrado `usuario1@library.local`. Para usar otro:

```powershell
$env:LOCUST_EMAIL = "otro@library.local"
$env:LOCUST_PASSWORD = "su_contraseña"
```

> Si el login no está disponible, las lecturas se prueban igual; solo las
> escrituras y las operaciones SOAP salen como fallos `401`.

---

## 2. Instalación en Windows 11 (una sola vez)

1. Instala **Python 3.10 o superior** desde <https://www.python.org/downloads/>.
   En el instalador marca **"Add python.exe to PATH"**.
2. Abre **PowerShell** y entra a esta carpeta:

   ```powershell
   cd C:\VSCODEOMG\IntegracionWeb\integracion03\apps\tests
   ```

3. Crea un entorno virtual e instala Locust:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install locust
   ```

   Si PowerShell bloquea `Activate.ps1` con *"la ejecución de scripts está
   deshabilitada"*, ejecuta una vez el siguiente comando y vuelve a activar el
   entorno:

   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   ```

4. Comprueba la instalación:

   ```powershell
   locust --version
   ```

---

## 3. Ejecutar la prueba con la interfaz gráfica (GUI)

1. **Prende la VM y levanta los microservicios** (desde la VM):

   ```bash
   bash /opt/udem/integracion03/scripts/servicios.sh start
   ```

   Comprueba desde Windows que responde: abre
   <http://34.51.2.102:5001/health> en el navegador.

2. **Arranca Locust** en PowerShell, dentro de `apps\tests` y con el entorno activado:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   locust
   ```

   Locust lee `locust.conf` solo y muestra:

   ```
   Starting web interface at http://0.0.0.0:8089
   ```

   Si el Firewall de Windows pregunta, permite el acceso en **redes privadas**.

3. **Abre la GUI** en el navegador: <http://localhost:8089>

4. En la pantalla **Start new load test** ya vienen los valores de `locust.conf`:

   | Campo | Valor |
   |---|---|
   | Number of users (peak concurrency) | `20` |
   | Ramp up (users started/second) | `5` |
   | Host | `http://34.51.2.102:5001` |
   | Advanced options → Run time | `5m` |

   Pulsa **START**.

5. **Pestañas de la GUI** durante la prueba:

   | Pestaña | Qué muestra |
   |---|---|
   | **Statistics** | Por endpoint: peticiones, fallos, mediana, percentil 95/99, promedio y RPS |
   | **Charts** | Gráficas en vivo de RPS, tiempos de respuesta y número de usuarios |
   | **Failures** | Cada tipo de fallo con el código HTTP y el inicio del mensaje de error |
   | **Exceptions** | Errores de Python dentro del locustfile (debe estar vacía) |
   | **Current ratio** | Reparto real entre `LectorCatalogo` y `EditorCatalogo` |
   | **Download Data** | CSV de estadísticas y el **reporte HTML** para la evidencia |

6. Pulsa **STOP** para detener la prueba antes de tiempo, o espera a que termine
   el *run time*. Para la evidencia, descarga el reporte desde **Download Data →
   Download Report**.

7. Para cerrar Locust, en PowerShell pulsa `Ctrl + C`.

---

## 4. Otras formas de ejecutarlo

Cambiar el número de usuarios o el host sin editar archivos:

```powershell
locust -u 50 -r 10 -H http://34.51.2.102:5001
```

Solo un perfil (por ejemplo, solo lectores):

```powershell
locust LectorCatalogo
```

Sin GUI, con el reporte HTML directo a archivo:

```powershell
locust --headless -t 2m --html reporte_locust.html
```

> **Ojo con la IP:** la IP externa de la VM cambia cada vez que se apaga y se
> prende. Si cambia, actualiza `host` en `locust.conf` o escríbela en el campo
> *Host* de la GUI.

---

## 5. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| Todas las peticiones fallan con `ConnectionError` | La VM está apagada, el servicio no está levantado o el firewall de GCP no abre el puerto 5001. |
| Escrituras y SOAP con `HTTP 401` | No se pudo hacer login. En la consola de Locust aparece `No se pudo obtener el JWT: …`. |
| Login con `503 SERVICE UNAVAILABLE` | El servicio login no tiene Redis configurado (`REDIS_URL` en su `.env`). Revisa con `servicios.sh redis`. |
| Escrituras con `401 INVALID_SIGNATURE` | `JWT_SECRET` no es igual en `login/.env` y `soap/.env`. |
| `429 TOO MANY REQUESTS` en el login | Se superaron 20 peticiones por minuto al login desde tu IP. Espera un minuto y vuelve a pulsar *Start*. |
