package mx.udem.library;

import java.io.*;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.*;
import java.util.concurrent.CompletableFuture;

/**
 * Cliente REST de los microservicios Library. Todas las URLs vienen de
 * config.properties (local o GCP); nada de credenciales de BD aqui: la app
 * Java solo habla HTTP/JSON con los servicios.
 */
public class ApiClient {

    /** Error de negocio devuelto por un servicio (codigo HTTP + code + message). */
    public static class ApiException extends RuntimeException {
        public final int status; public final String code;
        public ApiException(int status, String code, String message) { super(message); this.status = status; this.code = code; }
    }

    /** 401: token ausente, expirado, invalido o revocado -> hay que volver a autenticar. */
    public static class SessionExpired extends ApiException {
        public SessionExpired(String code, String msg) { super(401, code, msg); }
    }

    public final Properties cfg = new Properties();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(8)).build();

    // --- sesion JWT (en memoria) ---
    public String accessToken;
    public OffsetDateTime expiresAt;
    public Map<String, Object> user = new LinkedHashMap<>();

    /** Los siete servicios que se alcanzan a traves del gateway: /api/<servicio>. */
    public static final String[] SERVICES = {"login", "books", "users", "autores", "pedidos", "pagos", "rastreo"};
    public static final int GATEWAY_PORT = 8080;
    private static final Path CONFIG = Paths.get("config.properties");

    /** Direccion del gateway nginx, p. ej. http://34.51.29.27:8080 (sin /api). */
    private String gateway;

    public ApiClient() {
        // Sesion 08 - Reverse Proxy: la app solo conoce UNA direccion, la del
        // gateway. Las rutas de cada servicio se arman como <gateway>/api/<svc>
        // y nginx quita el prefijo antes de reenviar.
        if (Files.exists(CONFIG)) try (Reader r = Files.newBufferedReader(CONFIG)) { cfg.load(r); } catch (IOException ignored) { }
        gateway = normalizeGateway(cfg.getProperty("gateway", "127.0.0.1"));
    }

    /**
     * Acepta lo que el usuario escriba ("34.51.29.27", "34.51.29.27:8080",
     * "http://mi-vm:8080/api/login"...) y devuelve "http://host:puerto".
     */
    public static String normalizeGateway(String input) {
        String g = input == null ? "" : input.trim();
        if (g.isEmpty()) g = "127.0.0.1";
        if (!g.matches("(?i)^https?://.*")) g = "http://" + g;
        g = g.replaceAll("/+$", "").replaceAll("(?i)/api(/.*)?$", "");
        String hostPort = g.replaceFirst("(?i)^https?://", "").split("/", 2)[0];
        if (!hostPort.contains(":")) g = g.replaceFirst("(?i)^(https?://[^/]+)", "$1:" + GATEWAY_PORT);
        return g;
    }

    public String gateway() { return gateway; }

    /** Cambia la IP del gateway y la guarda en config.properties para el proximo arranque. */
    public void setGateway(String input) {
        String g = normalizeGateway(input);
        boolean changed = !g.equals(cfg.getProperty("gateway"));
        gateway = g;
        if (!changed) return;               // misma IP: no se reescribe el archivo
        cfg.setProperty("gateway", gateway);
        for (String s : SERVICES) cfg.remove(s);
        try (Writer w = Files.newBufferedWriter(CONFIG)) {
            cfg.store(w, "Library Desktop - direccion del gateway nginx (Sesion 08). Las rutas se arman como <gateway>/api/<servicio>.");
        } catch (IOException ignored) { }
    }

    /** true si el gateway responde GET /health. */
    public boolean gatewayAlive() {
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(gateway + "/health")).timeout(Duration.ofSeconds(4)).GET().build();
            return http.send(req, HttpResponse.BodyHandlers.discarding()).statusCode() == 200;
        } catch (Exception e) { return false; }
    }

    /** URL base de un servicio: <gateway>/api/<svc>. Una clave <svc>= en config.properties la sobreescribe. */
    public String url(String svc) {
        String override = cfg.getProperty(svc);
        return (override != null && !override.isBlank() ? override : gateway + "/api/" + svc).replaceAll("/+$", "");
    }

    public static String enc(String v) { return URLEncoder.encode(v, StandardCharsets.UTF_8); }

    // ------------------------------------------------------------- HTTP basico
    public Object call(String method, String svc, String path, Object body, boolean auth) {
        HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url(svc) + path))
                .timeout(Duration.ofSeconds(15))
                .header("Accept", "application/json");
        if (auth) {
            if (accessToken == null) throw new SessionExpired("NO_SESSION", "Inicia sesion para continuar.");
            if (expiresAt != null && OffsetDateTime.now().isAfter(expiresAt))
                throw new SessionExpired("TOKEN_EXPIRED", "Tu sesion (JWT) expiro. Vuelve a iniciar sesion.");
            b.header("Authorization", "Bearer " + accessToken);
        }
        String json = body == null ? null : Json.write(body);
        if (json != null) b.header("Content-Type", "application/json");
        b.method(method, json == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(json));
        HttpResponse<String> r;
        try {
            r = http.send(b.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new ApiException(0, "UNREACHABLE", "No se pudo conectar con '" + svc + "' (" + url(svc) + ").");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ApiException(0, "INTERRUPTED", "Peticion interrumpida");
        }
        Object parsed;
        try { parsed = r.body().isBlank() ? null : Json.parse(r.body()); }
        catch (Exception e) { parsed = r.body(); }
        if (r.statusCode() >= 400) {
            // login anida {"error":{code,message}}; libros lo pone plano {"error": "...", "code"}.
            Object err = Json.path(parsed, "error");
            String code = Json.str(err instanceof Map ? Json.path(err, "code") : Json.path(parsed, "code"));
            String msg = Json.str(err instanceof Map ? Json.path(err, "message") : (err != null ? err : parsed));
            if (r.statusCode() == 401) throw new SessionExpired(code, msg.isBlank() ? "Token invalido o expirado." : msg);
            throw new ApiException(r.statusCode(), code, msg);
        }
        return parsed;
    }

    public String raw(String method, String svc, String path, String body, String contentType, Map<String, String> headers) {
        try {
            HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url(svc) + path)).timeout(Duration.ofSeconds(15));
            if (contentType != null) b.header("Content-Type", contentType);
            if (headers != null) headers.forEach(b::header);
            b.method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(body));
            HttpResponse<String> r = http.send(b.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            return "HTTP " + r.statusCode() + "\n\n" + r.body();
        } catch (Exception e) { return "Error: " + e.getMessage(); }
    }

    public byte[] bytes(String url) {
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(10))
                    .header("User-Agent", "LibraryJavaDesktop/1.0").build();
            HttpResponse<byte[]> r = http.send(req, HttpResponse.BodyHandlers.ofByteArray());
            return r.statusCode() == 200 ? r.body() : null;
        } catch (Exception e) { return null; }
    }

    // ----------------------------------------------------------- Modulo 1: login
    public Map<String, Object> captcha() {
        return Json.obj(Json.path(call("GET", "login", "/captcha?format=json", null, false), "data"));
    }

    public void login(String email, String password, String captchaId, int answer) {
        Object r = call("POST", "login", "/login?format=json", Json.map(
                "email", email, "password", password, "captcha_id", captchaId, "captcha_answer", answer), false);
        Map<String, Object> session = Json.obj(Json.path(r, "data", "session"));
        accessToken = Json.str(session.get("access_token"));
        try { expiresAt = OffsetDateTime.parse(Json.str(session.get("expires_at"))); } catch (Exception e) { expiresAt = null; }
        user = Json.obj(Json.path(r, "data", "user"));
    }

    /** POST /register (por el gateway: /api/login/register). Lanza ApiException con el motivo. */
    public void register(Map<String, Object> body) {
        call("POST", "login", "/register?format=json", body, false);
    }

    public void logout() {
        try { if (accessToken != null) call("POST", "login", "/logout?format=json", null, true); } catch (Exception ignored) { }
        accessToken = null; expiresAt = null; user = new LinkedHashMap<>();
    }

    public Map<String, Object> sessionInfo() { return Json.obj(Json.path(call("GET", "login", "/session?format=json", null, true), "data")); }

    public int userId() { return Json.num(user.get("id")).intValue(); }

    public boolean isAdmin() { return Json.num(user.get("role_id")).intValue() == 1 || "Administrador".equalsIgnoreCase(Json.str(user.get("role"))); }

    public Map<String, Object> profile() { return Json.obj(Json.path(call("GET", "users", "/users/" + userId(), null, true), "data")); }

    public List<Object> listUsers() { return Json.arr(Json.path(call("GET", "users", "/users?limit=50", null, true), "data")); }

    // -------------------------------------------------------- Modulo 2: catalogo
    public List<Object> books() { return Json.arr(Json.path(call("GET", "books", "/books?format=json", null, false), "books")); }

    public List<Object> searchBooks(String q) {
        Object r = call("GET", "books", "/books/search?format=json&q=" + enc(q), null, false);
        Object list = Json.path(r, "books");
        if (list == null) list = Json.path(r, "results");
        if (list == null) list = Json.path(r, "data");
        return Json.arr(list);
    }

    public Map<String, Object> book(String isbn) { return Json.obj(call("GET", "books", "/books/" + enc(isbn) + "?format=json", null, false)); }

    public Map<String, Object> author(int id) { return Json.obj(Json.path(call("GET", "autores", "/autores/" + id, null, false), "data")); }

    // --------------------------------------------------- Modulo 4: pedidos/pagos
    public Map<String, Object> createOrder(List<Object> lineas) {
        return Json.obj(Json.path(call("POST", "pedidos", "/pedidos", Json.map("lineas", lineas, "notas", "Compra desde JavaDesktop_app"), true), "data"));
    }

    public Map<String, Object> pay(int pedidoId, String metodo, String referencia) {
        return Json.obj(Json.path(call("POST", "pagos", "/pagos", Json.map(
                "pedido_id", pedidoId, "metodo", metodo, "estado", "Aprobado", "referencia", referencia), true), "data"));
    }

    public List<Object> orders() { return Json.arr(Json.path(call("GET", "pedidos", "/pedidos?limit=100", null, true), "data")); }

    public Map<String, Object> order(int id) { return Json.obj(Json.path(call("GET", "pedidos", "/pedidos/" + id, null, true), "data")); }

    public List<Object> paymentsOf(int id) { return Json.arr(Json.path(call("GET", "pagos", "/pedidos/" + id + "/pagos", null, true), "data")); }

    // ------------------------------------------------------- Modulo 6: rastreo
    public Map<String, Object> createTracking(int pedidoId) {
        return Json.obj(Json.path(call("POST", "rastreo", "/rastreo", Json.map("pedido_id", pedidoId), true), "data"));
    }

    public List<Object> myTrackings() { return Json.arr(Json.path(call("GET", "rastreo", "/rastreo", null, true), "data")); }

    public Map<String, Object> tracking(String code) { return Json.obj(Json.path(call("GET", "rastreo", "/rastreo/" + enc(code), null, true), "data")); }

    /** WebSocket nativo de Java 11+ (java.net.http.WebSocket); JWT en el handshake. */
    public CompletableFuture<WebSocket> openTrackingSocket(String code, WebSocket.Listener listener) {
        String ws = url("rastreo").replaceFirst("^http", "ws") + "/ws/rastreo/" + enc(code);
        return http.newWebSocketBuilder()
                .header("Authorization", "Bearer " + accessToken)
                .connectTimeout(Duration.ofSeconds(8))
                .buildAsync(URI.create(ws), listener);
    }
}
