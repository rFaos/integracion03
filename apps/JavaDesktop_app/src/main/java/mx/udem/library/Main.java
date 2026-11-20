package mx.udem.library;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.beans.property.SimpleStringProperty;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.concurrent.Worker;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.*;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.*;
import javafx.scene.text.Font;
import javafx.scene.text.FontWeight;
import javafx.scene.web.WebEngine;
import javafx.scene.web.WebView;
import javafx.stage.Stage;
import javafx.util.Duration;
import javafx.animation.KeyFrame;
import javafx.animation.Timeline;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.http.WebSocket;
import java.time.OffsetDateTime;
import java.util.*;
import java.util.concurrent.CompletionStage;
import java.util.function.Consumer;
import java.util.function.Supplier;

/**
 * Library Desktop - cliente JavaFX de los microservicios Library.
 * Modulos: Login/Perfil, Catalogo, Cesta, Compra, Mis compras, Rastreo (WebSocket + Leaflet).
 */
public class Main extends Application {

    private final ApiClient api = new ApiClient();
    private Stage stage;
    private Label statusBar = new Label();
    private TabPane tabs;
    private Timeline sessionWatch;

    // ------------------------------------------------------------------ cesta
    static class CartItem {
        int bookId; String isbn, title; BigDecimal price; int qty, stock;
        BigDecimal subtotal() { return price.multiply(BigDecimal.valueOf(qty)); }
    }
    private final ObservableList<CartItem> cart = FXCollections.observableArrayList();
    private Label cartTotal = new Label();
    private TableView<CartItem> cartTable;

    // ---------------------------------------------------------------- rastreo
    private WebEngine mapEngine;
    private boolean mapReady = false;
    private WebSocket socket;
    private TextField trackCode;
    private ComboBox<String> myCodes;
    private Label trkEstado = new Label("-"), trkPos = new Label("-"), trkProg = new Label("-"), trkRuta = new Label("-");
    private TextArea trkLog = new TextArea();

    // ------------------------------------------------------------ mis compras
    private final ObservableList<Map<String, Object>> orders = FXCollections.observableArrayList();
    private final Map<Integer, String> codesByOrder = new HashMap<>();

    // ------------------------------------------- modo evidencias (capturas)
    /** -Devidencias=<dir>: recorre la app con el usuario de demo.properties y guarda PNGs. */
    static final String EVID = System.getProperty("evidencias");
    private TextField catalogQ; private Button catalogSearch;
    private final List<Map<String, Object>> lastBooks = new ArrayList<>();

    private void snapScene(Scene sc, String name) {
        if (EVID == null || sc == null) return;
        try {
            javafx.scene.image.WritableImage img = sc.snapshot(null);
            int w = (int) img.getWidth(), h = (int) img.getHeight();
            java.awt.image.BufferedImage bi = new java.awt.image.BufferedImage(w, h, java.awt.image.BufferedImage.TYPE_INT_RGB);
            javafx.scene.image.PixelReader pr = img.getPixelReader();
            for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) bi.setRGB(x, y, pr.getArgb(x, y));
            java.io.File dir = new java.io.File(EVID); dir.mkdirs();
            javax.imageio.ImageIO.write(bi, "png", new java.io.File(dir, name + ".png"));
            System.out.println("captura: " + name);
        } catch (Exception e) { System.out.println("captura fallida " + name + ": " + e); }
    }

    private void snap(String name) { snapScene(stage.getScene(), name); }

    private String pendingDialogName;

    /** En modo evidencias los dialogos no bloquean: se capturan y se cierran solos. */
    private void showDialog(Dialog<?> d, String name) {
        if (EVID == null) { d.showAndWait(); return; }
        d.show();
        later(2.5, () -> { snapScene(d.getDialogPane().getScene(), name); d.close(); });
    }

    private void later(double s, Runnable r) { new Timeline(new KeyFrame(Duration.seconds(s), e -> r.run())).play(); }

    private static int solveCaptcha(String q) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("(\\d+)\\s*([-+x*×])\\s*(\\d+)").matcher(q);
        if (!m.find()) return 0;
        int a = Integer.parseInt(m.group(1)), b = Integer.parseInt(m.group(3));
        return switch (m.group(2)) { case "+" -> a + b; case "-" -> a - b; default -> a * b; };
    }

    private void evidenceTour() {
        double t = 6;
        later(t, () -> snap("02_catalogo"));
        later(t += 1, () -> { if (!lastBooks.isEmpty()) showBookDetail(Json.str(lastBooks.get(0).get("isbn"))); });
        later(t += 5, () -> {
            String w = lastBooks.isEmpty() ? "a" : Json.str(lastBooks.get(Math.min(2, lastBooks.size() - 1)).get("title")).split("\\s+")[0];
            catalogQ.setText(w); catalogSearch.fire();
        });
        later(t += 4, () -> snap("04_busqueda_titulo"));
        later(t += 1, () -> {
            catalogQ.clear(); catalogSearch.fire();
        });
        later(t += 4, () -> {
            for (int k = 0; k < Math.min(3, lastBooks.size()); k++) addToCart(lastBooks.get(k));
            if (!cart.isEmpty()) addToCart(lastBooks.get(0));
            tabs.getSelectionModel().select(1);
        });
        later(t += 2, () -> snap("05_cesta"));
        later(t += 1, this::checkout);
        // Al confirmar, checkout abre la pestana Rastreo y conecta el WebSocket.
        later(t += 12, () -> snap("07_rastreo_preparando"));
        later(t += 30, () -> snap("08_rastreo_en_ruta"));
        later(t += 30, () -> snap("09_rastreo_en_ruta_avance"));
        later(t += 50, () -> snap("10_rastreo_entregado"));
        later(t += 2, () -> tabs.getSelectionModel().select(2));
        later(t += 5, () -> ordersTable.getSelectionModel().selectFirst());
        later(t += 4, () -> snap("11_mis_compras"));
        later(t += 1, () -> tabs.getSelectionModel().select(4));
        later(t += 3, () -> snap("12_perfil_users"));
        later(t += 1, () -> profileButtons.get(4).fire());
        later(t += 3, () -> snap("13_soap_xml"));
        later(t += 1, () -> { api.expiresAt = OffsetDateTime.now().minusSeconds(1); });
        later(t += 3, () -> snap("14_sesion_expirada"));
        later(t += 2, Platform::exit);
    }

    private final List<Button> profileButtons = new ArrayList<>();

    public static void main(String[] args) { launch(args); }

    @Override
    public void start(Stage st) {
        stage = st;
        stage.setTitle("Library Desktop - Cliente Java de microservicios");
        showLogin(null);
        stage.show();
    }

    @Override
    public void stop() { closeSocket(); }

    // ========================================================= utilidades UI
    /** Ejecuta red fuera del hilo de JavaFX; el resultado vuelve con Platform.runLater. */
    private <T> void async(String what, Supplier<T> work, Consumer<T> done) {
        status("⏳ " + what + "...");
        Thread t = new Thread(() -> {
            try {
                T r = work.get();
                Platform.runLater(() -> { status("✔ " + what); done.accept(r); });
            } catch (ApiClient.SessionExpired e) {
                Platform.runLater(() -> sessionExpired(e.getMessage()));
            } catch (ApiClient.ApiException e) {
                Platform.runLater(() -> { status("✖ " + what); error(what, (e.code.isBlank() ? "" : "[" + e.code + "] ") + e.getMessage()); });
            } catch (Exception e) {
                Platform.runLater(() -> { status("✖ " + what); error(what, String.valueOf(e.getMessage())); });
            }
        }, "net");
        t.setDaemon(true);
        t.start();
    }

    private void status(String s) { statusBar.setText(s); }

    private int dlgCount = 0;

    private void error(String title, String msg) {
        if (EVID != null) System.out.println("ERROR " + title + ": " + msg);
        Alert a = new Alert(Alert.AlertType.ERROR, msg, ButtonType.OK);
        a.setHeaderText(title); a.initOwner(stage);
        showDialog(a, "err_" + (++dlgCount));
    }

    private void info(String title, String msg) {
        Alert a = new Alert(Alert.AlertType.INFORMATION, msg, ButtonType.OK);
        a.setHeaderText(title); a.initOwner(stage);
        String n = pendingDialogName != null ? pendingDialogName : "info_" + (++dlgCount);
        pendingDialogName = null;
        showDialog(a, n);
    }

    private void sessionExpired(String msg) {
        closeSocket();
        api.accessToken = null;
        showLogin("Sesion no valida: " + msg + " Inicia sesion nuevamente.");
    }

    private static String money(Object v) { return "$" + Json.num(v).setScale(2, RoundingMode.HALF_UP).toPlainString(); }

    private static Label h1(String t) { Label l = new Label(t); l.setFont(Font.font("Segoe UI", FontWeight.BOLD, 20)); return l; }

    private Scene scene(Region root) {
        Scene sc = new Scene(root, 1200, 780);
        sc.getStylesheets().add(Objects.requireNonNull(getClass().getResource("/app.css")).toExternalForm());
        return sc;
    }

    // ================================================ Modulo 1: autenticacion
    /** Campo con su etiqueta encima (formulario apilado). */
    private static VBox field(String label, Control input) {
        Label l = new Label(label); l.getStyleClass().add("field-label");
        input.setMaxWidth(Double.MAX_VALUE); input.getStyleClass().add("auth-input");
        return new VBox(5, l, input);
    }

    /** Aviso dentro de la tarjeta: "error", "success" o "info". Vacio = oculto. */
    private static void banner(Label b, String kind, String text) {
        b.getStyleClass().removeAll("banner-error", "banner-success", "banner-info");
        boolean show = text != null && !text.isBlank();
        b.setText(show ? text : ""); b.setVisible(show); b.setManaged(show);
        if (show) b.getStyleClass().add("banner-" + kind);
    }

    /**
     * Pantalla de acceso con dos modos: "Iniciar sesion" y "Crear cuenta".
     * Ambos piden CAPTCHA (el servicio login lo exige y es de un solo uso, asi que
     * se pide uno nuevo tras cada intento). Todo viaja por el gateway nginx.
     */
    private void showLogin(String notice) {
        if (sessionWatch != null) sessionWatch.stop();
        cart.clear();

        // ---------- campos de inicio de sesion
        TextField email = new TextField(); email.setPromptText("correo@ejemplo.com");
        PasswordField pass = new PasswordField(); pass.setPromptText("Tu contrasena");

        // ---------- campos de registro
        TextField rNombre = new TextField(); rNombre.setPromptText("Nombre");
        TextField rPaterno = new TextField(); rPaterno.setPromptText("Apellido paterno");
        TextField rMaterno = new TextField(); rMaterno.setPromptText("Apellido materno");
        TextField rEmail = new TextField(); rEmail.setPromptText("correo@ejemplo.com");
        PasswordField rPass = new PasswordField(); rPass.setPromptText("Minimo 8 caracteres");
        PasswordField rPass2 = new PasswordField(); rPass2.setPromptText("Repite la contrasena");
        Label rules = new Label("Al menos 8 caracteres, con mayuscula, minuscula, numero y simbolo.");
        rules.getStyleClass().add("hint"); rules.setWrapText(true);

        // ---------- CAPTCHA compartido por ambos modos
        Label q = new Label("Cargando..."); q.getStyleClass().add("captcha-q");
        TextField ans = new TextField(); ans.setPromptText("Respuesta"); ans.setPrefWidth(110);
        ans.getStyleClass().add("auth-input");
        Button reload = new Button("↻"); reload.getStyleClass().add("icon-btn");
        reload.setTooltip(new Tooltip("Otro CAPTCHA"));
        Region spacer = new Region(); HBox.setHgrow(spacer, Priority.ALWAYS);
        Label lock = new Label("CAPTCHA"); lock.getStyleClass().add("captcha-tag");
        HBox captchaRow = new HBox(10, lock, q, spacer, ans, reload);
        captchaRow.setAlignment(Pos.CENTER_LEFT); captchaRow.getStyleClass().add("captcha-box");
        String[] captchaId = {null};

        Label msg = new Label(); msg.setWrapText(true); msg.setMaxWidth(Double.MAX_VALUE);
        banner(msg, "Sesion cerrada.".equals(notice) ? "info" : "error", notice);

        Button go = new Button("Iniciar sesion"); go.setDefaultButton(true);
        go.getStyleClass().addAll("primary", "wide"); go.setMaxWidth(Double.MAX_VALUE);

        // ---------- selector de modo (pestanas)
        ToggleGroup modeGroup = new ToggleGroup();
        ToggleButton tLogin = new ToggleButton("Iniciar sesion"), tReg = new ToggleButton("Crear cuenta");
        for (ToggleButton t : new ToggleButton[]{tLogin, tReg}) {
            t.setToggleGroup(modeGroup); t.getStyleClass().add("seg"); t.setMaxWidth(Double.MAX_VALUE);
            HBox.setHgrow(t, Priority.ALWAYS);
        }
        tLogin.setSelected(true);
        HBox seg = new HBox(4, tLogin, tReg); seg.getStyleClass().add("seg-box");

        VBox loginForm = new VBox(14, field("Correo electronico", email), field("Contrasena", pass));
        GridPane names = new GridPane(); names.setHgap(12); names.setVgap(12);
        ColumnConstraints half = new ColumnConstraints(); half.setPercentWidth(50);
        names.getColumnConstraints().addAll(half, half);
        names.add(field("Nombre", rNombre), 0, 0, 2, 1);
        names.add(field("Apellido paterno", rPaterno), 0, 1);
        names.add(field("Apellido materno", rMaterno), 1, 1);
        names.add(field("Correo electronico", rEmail), 0, 2, 2, 1);
        names.add(field("Contrasena", rPass), 0, 3);
        names.add(field("Confirmar", rPass2), 1, 3);
        VBox regForm = new VBox(8, names, rules);

        StackPane forms = new StackPane(loginForm, regForm);
        Label subtitle = new Label(); subtitle.getStyleClass().add("subtitle"); subtitle.setWrapText(true);

        Runnable loadCaptcha = () -> async("Obtener CAPTCHA", api::captcha, c -> {
            captchaId[0] = Json.str(c.get("captcha_id")); q.setText(Json.str(c.get("question"))); ans.clear();
        });

        Runnable applyMode = () -> {
            boolean reg = tReg.isSelected();
            loginForm.setVisible(!reg); loginForm.setManaged(!reg);
            regForm.setVisible(reg); regForm.setManaged(reg);
            go.setText(reg ? "Crear cuenta" : "Iniciar sesion");
            subtitle.setText(reg ? "Crea tu cuenta de cliente para comprar y rastrear pedidos."
                                 : "Bienvenido de nuevo. Ingresa con tu cuenta.");
        };
        // Un ToggleGroup permite deseleccionar: se fuerza que siempre haya un modo.
        modeGroup.selectedToggleProperty().addListener((o, old, now) -> {
            if (now == null) { old.setSelected(true); return; }
            banner(msg, "info", null); applyMode.run();
        });
        reload.setOnAction(e -> loadCaptcha.run());

        // Los errores de esta pantalla (incluido el 401 de credenciales) se muestran
        // en la tarjeta en lugar de tratarse como "sesion vencida".
        go.setOnAction(e -> {
            boolean reg = tReg.isSelected();
            int a;
            try { a = Integer.parseInt(ans.getText().trim()); }
            catch (Exception ex) { banner(msg, "error", "Responde el CAPTCHA con un numero."); return; }
            Supplier<Boolean> work;
            if (!reg) {
                if (email.getText().isBlank() || pass.getText().isEmpty()) { banner(msg, "error", "Escribe tu correo y tu contrasena."); return; }
                String em = email.getText().trim(), pw = pass.getText();
                work = () -> { api.login(em, pw, captchaId[0], a); return true; };
            } else {
                if (rNombre.getText().isBlank() || rPaterno.getText().isBlank() || rMaterno.getText().isBlank()
                        || rEmail.getText().isBlank() || rPass.getText().isEmpty()) {
                    banner(msg, "error", "Todos los campos son obligatorios."); return;
                }
                if (!rPass.getText().equals(rPass2.getText())) { banner(msg, "error", "Las contrasenas no coinciden."); return; }
                Map<String, Object> body = Json.map("nombre", rNombre.getText().trim(), "apellido_paterno", rPaterno.getText().trim(),
                        "apellido_materno", rMaterno.getText().trim(), "email", rEmail.getText().trim(),
                        "password", rPass.getText(), "captcha_id", captchaId[0], "captcha_answer", a);
                work = () -> { api.register(body); return true; };
            }
            go.setDisable(true); go.setText("Procesando..."); banner(msg, "info", null);
            Thread t = new Thread(() -> {
                String err = null;
                try { work.get(); } catch (Exception ex) { err = String.valueOf(ex.getMessage()); }
                String fErr = err;
                Platform.runLater(() -> {
                    go.setDisable(false); applyMode.run();
                    if (fErr != null) { banner(msg, "error", fErr); loadCaptcha.run(); return; }
                    if (!reg) { showMain(); return; }
                    // Registro correcto: se pasa a "Iniciar sesion" con el correo ya escrito.
                    email.setText(rEmail.getText().trim()); pass.clear();
                    for (TextField f : new TextField[]{rNombre, rPaterno, rMaterno, rEmail, rPass, rPass2}) f.clear();
                    tLogin.setSelected(true);
                    banner(msg, "success", "Cuenta creada. Ya puedes iniciar sesion.");
                    loadCaptcha.run(); pass.requestFocus();
                });
            }, "auth");
            t.setDaemon(true); t.start();
        });

        // ---------- encabezado y pie de la tarjeta
        Label logo = new Label("📚"); logo.getStyleClass().add("logo");
        Label title = new Label("Library"); title.getStyleClass().add("brand");
        VBox head = new VBox(2, title, subtitle);
        HBox header = new HBox(14, logo, head); header.setAlignment(Pos.CENTER_LEFT);
        Label server = new Label("●  Gateway  " + api.url("login").replaceAll("/api/login$", ""));
        server.getStyleClass().add("server-pill");
        HBox foot = new HBox(server); foot.setAlignment(Pos.CENTER);

        VBox card = new VBox(18, header, seg, forms, captchaRow, msg, go, foot);
        card.getStyleClass().addAll("card", "auth-card"); card.setMaxWidth(480);
        card.setMaxHeight(Region.USE_PREF_SIZE); card.setPadding(new Insets(32, 36, 26, 36));
        StackPane root = new StackPane(card); root.getStyleClass().add("login-bg");
        root.setPadding(new Insets(24));
        ScrollPane sp = new ScrollPane(root); sp.setFitToWidth(true); sp.setFitToHeight(true);
        sp.getStyleClass().add("login-scroll");
        stage.setScene(scene(sp));
        applyMode.run();

        // ---------- modo evidencias: entra solo con el usuario de demo.properties
        boolean auto = EVID != null && notice == null;
        async("Obtener CAPTCHA", api::captcha, c -> {
            captchaId[0] = Json.str(c.get("captcha_id")); q.setText(Json.str(c.get("question"))); ans.clear();
            if (auto) {
                Properties demo = new Properties();
                try (java.io.Reader r = new java.io.FileReader("demo.properties")) { demo.load(r); } catch (Exception ignored) { }
                email.setText(demo.getProperty("demo.email", "")); pass.setText(demo.getProperty("demo.password", ""));
                ans.setText(String.valueOf(solveCaptcha(q.getText())));
                later(1, () -> { snap("01_login"); go.fire(); });
            } else if (EVID != null) later(1, () -> snap("14_sesion_expirada"));
        });
    }

    private void showMain() {
        String name = (Json.str(api.user.get("nombre")) + " " + Json.str(api.user.get("apellido_paterno"))).trim();
        Label who = new Label("👤 " + name + "  <" + Json.str(api.user.get("email")) + ">  · rol: " + Json.str(api.user.get("role")) + "  · id " + api.userId());
        Label exp = new Label(); exp.getStyleClass().add("muted");
        Button logout = new Button("Cerrar sesion");
        logout.setOnAction(e -> { closeSocket(); async("Cerrar sesion", () -> { api.logout(); return true; }, r -> showLogin("Sesion cerrada.")); });
        Region sp = new Region(); HBox.setHgrow(sp, Priority.ALWAYS);
        HBox top = new HBox(14, h1("📚 Library Desktop"), sp, who, exp, logout);
        top.setAlignment(Pos.CENTER_LEFT); top.setPadding(new Insets(10, 16, 10, 16)); top.getStyleClass().add("topbar");

        tabs = new TabPane(
                new Tab("Catalogo", catalogView()),
                new Tab("Cesta", cartView()),
                new Tab("Mis compras", ordersView()),
                new Tab("Rastreo", trackingView()),
                new Tab("Perfil", profileView()));
        tabs.setTabClosingPolicy(TabPane.TabClosingPolicy.UNAVAILABLE);
        tabs.getSelectionModel().selectedIndexProperty().addListener((o, a, b) -> {
            if (b.intValue() == 2) loadOrders();
            if (b.intValue() == 3) loadMyCodes();
        });

        statusBar.getStyleClass().add("statusbar"); statusBar.setMaxWidth(Double.MAX_VALUE);
        BorderPane root = new BorderPane(tabs, top, null, statusBar, null);
        stage.setScene(scene(root));

        // Vigila la expiracion del JWT (exp) y obliga a re-autenticar.
        sessionWatch = new Timeline(new KeyFrame(Duration.seconds(1), e -> {
            if (api.expiresAt == null) return;
            long s = java.time.Duration.between(OffsetDateTime.now(), api.expiresAt).getSeconds();
            exp.setText("JWT expira en " + Math.max(s, 0) / 60 + ":" + String.format("%02d", Math.max(s, 0) % 60));
            if (s <= 0) { sessionWatch.stop(); sessionExpired("el token JWT expiro."); }
        }));
        sessionWatch.setCycleCount(Timeline.INDEFINITE);
        sessionWatch.play();
        if (EVID != null) evidenceTour();
    }

    // ======================================================= Modulo 2: catalogo
    private Region catalogView() {
        TextField q = new TextField(); q.setPromptText("Buscar por titulo..."); q.setPrefWidth(320);
        Button search = new Button("Buscar"), all = new Button("Ver todo");
        search.setDefaultButton(true);
        FlowPane grid = new FlowPane(16, 16); grid.setPadding(new Insets(16));
        ScrollPane sc = new ScrollPane(grid); sc.setFitToWidth(true);
        catalogQ = q; catalogSearch = search;
        Consumer<List<Object>> render = list -> {
            grid.getChildren().clear();
            if (q.getText().isBlank()) { lastBooks.clear(); for (Object o : list) if (Json.num(Json.path(o, "stock")).intValue() > 1) lastBooks.add(Json.obj(o)); }
            for (Object o : list) grid.getChildren().add(bookCard(Json.obj(o)));
            if (list.isEmpty()) grid.getChildren().add(new Label("Sin resultados."));
        };
        search.setOnAction(e -> {
            if (q.getText().isBlank()) { all.fire(); return; }
            async("Buscar libros", () -> api.searchBooks(q.getText().trim()), render);
        });
        all.setOnAction(e -> async("Consultar catalogo (books)", api::books, render));
        HBox bar = new HBox(10, new Label("📖 Catalogo"), q, search, all);
        bar.setAlignment(Pos.CENTER_LEFT); bar.setPadding(new Insets(12, 16, 0, 16));
        all.fire();
        return new BorderPane(sc, bar, null, null, null);
    }

    private Region cover(String url, double w, double h) {
        Label ph = new Label("Portada\nno disponible"); ph.getStyleClass().add("nocover");
        ph.setPrefSize(w, h); ph.setAlignment(Pos.CENTER);
        StackPane box = new StackPane(ph); box.setPrefSize(w, h); box.setMaxSize(w, h);
        if (url != null && !url.isBlank()) {
            Image img = new Image(url, w, h, true, true, true);
            ImageView iv = new ImageView(img);
            img.progressProperty().addListener((o, a, b) -> { if (b.doubleValue() >= 1 && !img.isError()) ph.setVisible(false); });
            img.errorProperty().addListener((o, a, b) -> iv.setVisible(false));
            box.getChildren().add(iv);
        }
        return box;
    }

    private Region bookCard(Map<String, Object> b) {
        Label title = new Label(Json.str(b.get("title"))); title.setWrapText(true); title.getStyleClass().add("book-title");
        Label authors = new Label(Json.str(b.get("authors"))); authors.setWrapText(true); authors.getStyleClass().add("muted");
        int stock = Json.num(b.get("stock")).intValue();
        Label price = new Label(money(b.get("price"))); price.getStyleClass().add("price");
        Label disp = new Label(stock > 0 ? "Disponibles: " + stock : "Agotado"); disp.getStyleClass().add(stock > 0 ? "ok" : "warn");
        Label isbn = new Label("ISBN " + Json.str(b.get("isbn"))); isbn.getStyleClass().add("muted");
        Button det = new Button("Detalles"), add = new Button("🛒 Agregar");
        add.getStyleClass().add("primary"); add.setDisable(stock <= 0);
        det.setOnAction(e -> showBookDetail(Json.str(b.get("isbn"))));
        add.setOnAction(e -> addToCart(b));
        VBox v = new VBox(6, cover(Json.str(b.get("cover_image")), 150, 210), title, authors, isbn, price, disp, new HBox(6, det, add));
        v.getStyleClass().add("book-card"); v.setPrefWidth(190); v.setPadding(new Insets(10));
        return v;
    }

    private void showBookDetail(String isbn) {
        async("Detalle del libro " + isbn, () -> api.book(isbn), b -> {
            Dialog<Void> d = new Dialog<>(); d.initOwner(stage); d.setTitle(Json.str(b.get("title")));
            d.getDialogPane().getButtonTypes().add(ButtonType.CLOSE);
            String img = "";
            for (Object o : Json.arr(b.get("images"))) { img = Json.str(Json.path(o, "image_url")); if (Boolean.TRUE.equals(Json.path(o, "is_cover"))) break; }
            Label t = h1(Json.str(b.get("title"))); t.setWrapText(true);
            Label desc = new Label(Json.str(b.get("description")).isBlank() ? "(El servicio no proporciona descripcion para este libro)" : Json.str(b.get("description")));
            desc.setWrapText(true); desc.setMaxWidth(460);
            GridPane g = new GridPane(); g.setHgap(10); g.setVgap(4);
            int r = 0;
            g.addRow(r++, new Label("ISBN:"), new Label(Json.str(b.get("isbn"))));
            g.addRow(r++, new Label("ID:"), new Label(Json.str(b.get("id"))));
            g.addRow(r++, new Label("Precio:"), new Label(money(b.get("price"))));
            g.addRow(r++, new Label("Existencias:"), new Label(Json.str(b.get("stock"))));
            g.addRow(r++, new Label("Ano:"), new Label(Json.str(b.get("publication_year"))));
            g.addRow(r++, new Label("Formato:"), new Label(Json.str(b.get("format_name"))));
            g.addRow(r++, new Label("Categoria:"), new Label(Json.str(b.get("category_name"))));
            VBox authorsBox = new VBox(4, new Label("Autores (clic para consultar el microservicio autores):"));
            for (Object o : Json.arr(b.get("authors"))) {
                Map<String, Object> a = Json.obj(o);
                Hyperlink l = new Hyperlink("✍ " + Json.str(a.get("name")) + " (" + Json.str(a.get("country")) + ")");
                l.setOnAction(e -> showAuthor(Json.num(a.get("id")).intValue()));
                authorsBox.getChildren().add(l);
            }
            Button add = new Button("🛒 Agregar a la cesta"); add.getStyleClass().add("primary");
            Map<String, Object> asCard = new HashMap<>(b);
            add.setOnAction(e -> addToCart(asCard));
            VBox right = new VBox(10, t, g, authorsBox, new Label("Descripcion:"), desc, add);
            HBox root = new HBox(20, cover(img, 220, 310), right); root.setPadding(new Insets(10));
            ScrollPane sp = new ScrollPane(root); sp.setPrefSize(780, 520); sp.setFitToWidth(true);
            d.getDialogPane().setContent(sp);
            showDialog(d, "03_detalle_libro_autores");
        });
    }

    private void showAuthor(int id) {
        async("Consultar autor " + id + " (autores)", () -> api.author(id), a -> {
            List<Object> books = Json.arr(a.get("libros"));
            StringBuilder sb = new StringBuilder();
            sb.append("Pais: ").append(Json.str(a.get("country"))).append("\n\n").append(Json.str(a.get("biography")));
            if (!books.isEmpty()) {
                sb.append("\n\nLibros:\n");
                for (Object o : books) sb.append(" • ").append(Json.str(Json.path(o, "title"))).append("\n");
            }
            info(Json.str(a.get("name")), sb.toString());
        });
    }

    // ========================================================= Modulo 3: cesta
    private void addToCart(Map<String, Object> b) {
        String isbn = Json.str(b.get("isbn"));
        CartItem it = cart.stream().filter(c -> c.isbn.equals(isbn)).findFirst().orElse(null);
        int stock = Json.num(b.get("stock")).intValue();
        if (it == null) {
            it = new CartItem();
            it.bookId = Json.num(b.get("id")).intValue(); it.isbn = isbn; it.title = Json.str(b.get("title"));
            it.price = Json.num(b.get("price")); it.qty = 0; it.stock = stock;
            cart.add(it);
        }
        if (it.qty + 1 > it.stock) { error("Cesta", "Solo hay " + it.stock + " ejemplares de '" + it.title + "'."); return; }
        it.qty++;
        refreshCart();
        status("Agregado a la cesta: " + it.title + " (x" + it.qty + ")");
    }

    private void refreshCart() {
        if (cartTable != null) cartTable.refresh();
        BigDecimal sub = cart.stream().map(CartItem::subtotal).reduce(BigDecimal.ZERO, BigDecimal::add);
        int n = cart.stream().mapToInt(c -> c.qty).sum();
        cartTotal.setText("Articulos: " + n + "    Subtotal: " + money(sub) + "    Total: " + money(sub));
        if (tabs != null) tabs.getTabs().get(1).setText("Cesta (" + n + ")");
    }

    private Region cartView() {
        cartTable = new TableView<>(cart);
        TableColumn<CartItem, String> cT = new TableColumn<>("Libro"), cI = new TableColumn<>("ISBN"), cP = new TableColumn<>("Precio"),
                cQ = new TableColumn<>("Cantidad"), cS = new TableColumn<>("Subtotal");
        cT.setCellValueFactory(c -> new SimpleStringProperty(c.getValue().title));
        cI.setCellValueFactory(c -> new SimpleStringProperty(c.getValue().isbn));
        cP.setCellValueFactory(c -> new SimpleStringProperty(money(c.getValue().price)));
        cQ.setCellValueFactory(c -> new SimpleStringProperty(String.valueOf(c.getValue().qty)));
        cS.setCellValueFactory(c -> new SimpleStringProperty(money(c.getValue().subtotal())));
        cT.setPrefWidth(420); cI.setPrefWidth(150);
        cartTable.getColumns().addAll(List.of(cT, cI, cP, cQ, cS));
        cartTable.setPlaceholder(new Label("La cesta esta vacia. Agrega libros desde el Catalogo."));

        Button plus = new Button("+1"), minus = new Button("-1"), del = new Button("Eliminar"), clear = new Button("Vaciar");
        Button buy = new Button("✅ Confirmar compra"); buy.getStyleClass().add("primary");
        plus.setOnAction(e -> { CartItem c = cartTable.getSelectionModel().getSelectedItem(); if (c != null) { if (c.qty < c.stock) c.qty++; else error("Cesta", "Sin existencias adicionales."); refreshCart(); } });
        minus.setOnAction(e -> { CartItem c = cartTable.getSelectionModel().getSelectedItem(); if (c != null) { c.qty--; if (c.qty <= 0) cart.remove(c); refreshCart(); } });
        del.setOnAction(e -> { CartItem c = cartTable.getSelectionModel().getSelectedItem(); if (c != null) { cart.remove(c); refreshCart(); } });
        clear.setOnAction(e -> { cart.clear(); refreshCart(); });
        buy.setOnAction(e -> checkout());
        cartTotal.getStyleClass().add("total");
        refreshCart();
        HBox actions = new HBox(10, new Label("Seleccion:"), plus, minus, del, clear);
        actions.setAlignment(Pos.CENTER_LEFT);
        HBox bottom = new HBox(20, cartTotal, buy); bottom.setAlignment(Pos.CENTER_RIGHT);
        VBox v = new VBox(12, h1("🛒 Cesta de compras"), actions, cartTable, bottom);
        VBox.setVgrow(cartTable, Priority.ALWAYS); v.setPadding(new Insets(16));
        return v;
    }

    // ============================================== Modulo 4: simulacion compra
    private void checkout() {
        if (cart.isEmpty()) { error("Compra", "La cesta esta vacia."); return; }
        ChoiceDialog<String> m = new ChoiceDialog<>("Tarjeta", List.of("Tarjeta", "Transferencia", "Efectivo", "PayPal"));
        m.initOwner(stage); m.setHeaderText("Pago SIMULADO: no se solicitan ni procesan datos bancarios reales.\nTotal: "
                + money(cart.stream().map(CartItem::subtotal).reduce(BigDecimal.ZERO, BigDecimal::add)));
        m.setContentText("Metodo de pago:");
        Optional<String> metodo = EVID != null ? Optional.of("Tarjeta") : m.showAndWait();
        pendingDialogName = "06_compra_confirmada";
        if (metodo.isEmpty()) return;
        List<CartItem> items = new ArrayList<>(cart);
        StringBuilder log = new StringBuilder();
        async("Procesar compra", () -> {
            // 1) Validacion de productos y precios contra el microservicio books.
            for (CartItem c : items) {
                List<Object> found = Json.arr(Json.path(api.call("GET", "books", "/books?format=json&isbn=" + ApiClient.enc(c.isbn), null, false), "books"));
                if (found.isEmpty()) throw new ApiClient.ApiException(404, "BOOK_NOT_FOUND", "El libro " + c.isbn + " ya no existe.");
                Map<String, Object> b = Json.obj(found.get(0));
                BigDecimal real = Json.num(b.get("price"));
                int stock = Json.num(b.get("stock")).intValue();
                if (real.compareTo(c.price) != 0) { log.append("Precio actualizado de '").append(c.title).append("': ").append(money(c.price)).append(" -> ").append(money(real)).append("\n"); c.price = real; }
                if (stock < c.qty) throw new ApiClient.ApiException(409, "INSUFFICIENT_STOCK", "Solo hay " + stock + " de '" + c.title + "'.");
                c.stock = stock;
            }
            // 2) Pedido real en el microservicio pedidos (stock atomico, precio congelado).
            List<Object> lineas = new ArrayList<>();
            for (CartItem c : items) lineas.add(Json.map("book_id", c.bookId, "cantidad", c.qty));
            Map<String, Object> order = api.createOrder(lineas);
            int pid = Json.num(order.get("id")).intValue();
            log.append("Pedido #").append(pid).append(" creado (").append(Json.str(order.get("estado"))).append("), total ").append(money(order.get("total"))).append("\n");
            // 3) Pago simulado en el microservicio pagos (misma transaccion marca el pedido como Pagado).
            Map<String, Object> pay = api.pay(pid, metodo.get(), "SIM-JAVA-" + System.currentTimeMillis());
            log.append("Pago #").append(Json.str(pay.get("id"))).append(" ").append(Json.str(pay.get("estado"))).append(" por ").append(money(pay.get("monto"))).append("\n");
            // 4) Se consulta el resultado real (no se asume exito).
            Map<String, Object> fin = api.order(pid);
            log.append("Estado del pedido segun 'pedidos': ").append(Json.str(fin.get("estado"))).append("\n");
            // 5) Codigo de rastreo asociado al pedido real.
            String code = null;
            if ("Pagado".equals(Json.str(fin.get("estado")))) {
                Map<String, Object> t = api.createTracking(pid);
                code = Json.str(t.get("codigo"));
            }
            return code == null ? "" : code;
        }, code -> {
            cart.clear(); refreshCart();
            if (!code.isEmpty()) {
                trackCode.setText(code);
                info("¡Compra confirmada!", log + "\nCodigo de rastreo: " + code + "\n\nPuedes seguir tu pedido en la pestana Rastreo.");
                tabs.getSelectionModel().select(3);
                startTracking(code);
            } else info("Compra registrada", log + "\nEl pago no quedo aprobado; no se genero codigo de rastreo.");
        });
    }

    // ============================================== Modulo 5: mis compras
    private TableView<Map<String, Object>> ordersTable;
    private TextArea orderDetail;

    private Region ordersView() {
        ordersTable = new TableView<>(orders);
        String[][] cols = {{"Pedido", "id"}, {"Fecha", "created_at"}, {"Estado compra", "estado"}, {"Total", "total"}, {"Estado pago", "_pago"}, {"Codigo de rastreo", "_codigo"}};
        for (String[] c : cols) {
            TableColumn<Map<String, Object>, String> col = new TableColumn<>(c[0]);
            col.setCellValueFactory(x -> new SimpleStringProperty("total".equals(c[1]) ? money(x.getValue().get(c[1])) : Json.str(x.getValue().get(c[1]))));
            col.setPrefWidth("created_at".equals(c[1]) || "_codigo".equals(c[1]) ? 200 : 120);
            ordersTable.getColumns().add(col);
        }
        ordersTable.setPlaceholder(new Label("No tienes pedidos."));
        orderDetail = new TextArea(); orderDetail.setEditable(false); orderDetail.setPrefRowCount(10);
        ordersTable.getSelectionModel().selectedItemProperty().addListener((o, a, b) -> { if (b != null) loadOrderDetail(Json.num(b.get("id")).intValue()); });
        Button reload = new Button("↻ Actualizar"), track = new Button("🗺 Rastrear pedido"), gen = new Button("Generar codigo de rastreo");
        track.getStyleClass().add("primary");
        reload.setOnAction(e -> loadOrders());
        track.setOnAction(e -> {
            Map<String, Object> s = ordersTable.getSelectionModel().getSelectedItem();
            if (s == null) return;
            String code = codesByOrder.get(Json.num(s.get("id")).intValue());
            if (code == null) { error("Rastreo", "El pedido no tiene codigo de rastreo (solo pedidos pagados)."); return; }
            trackCode.setText(code); tabs.getSelectionModel().select(3); startTracking(code);
        });
        gen.setOnAction(e -> {
            Map<String, Object> s = ordersTable.getSelectionModel().getSelectedItem();
            if (s == null) return;
            async("Generar codigo de rastreo", () -> api.createTracking(Json.num(s.get("id")).intValue()),
                    t -> { info("Rastreo", "Codigo: " + Json.str(t.get("codigo"))); loadOrders(); });
        });
        VBox v = new VBox(10, h1("🧾 Mis compras"), new HBox(10, reload, track, gen), ordersTable, new Label("Detalle del pedido seleccionado:"), orderDetail);
        VBox.setVgrow(ordersTable, Priority.ALWAYS); v.setPadding(new Insets(16));
        return v;
    }

    private void loadOrders() {
        async("Consultar pedidos (pedidos/pagos/rastreo)", () -> {
            List<Map<String, Object>> list = new ArrayList<>();
            Map<Integer, String> codes = new HashMap<>();
            try { for (Object t : api.myTrackings()) codes.put(Json.num(Json.path(t, "pedido_id")).intValue(), Json.str(Json.path(t, "codigo"))); }
            catch (ApiClient.SessionExpired e) { throw e; }
            catch (Exception ignored) { /* el servicio de rastreo puede no estar activo; los pedidos se muestran igual */ }
            for (Object o : api.orders()) {
                Map<String, Object> m = new LinkedHashMap<>(Json.obj(o));
                int id = Json.num(m.get("id")).intValue();
                List<Object> pays = api.paymentsOf(id);
                m.put("_pago", pays.isEmpty() ? "Sin pago" : Json.str(Json.path(pays.get(0), "estado")) + " (" + Json.str(Json.path(pays.get(0), "metodo")) + ")");
                m.put("_codigo", codes.getOrDefault(id, "-"));
                list.add(m);
            }
            codesByOrder.clear(); codesByOrder.putAll(codes);
            return list;
        }, list -> orders.setAll(list));
    }

    private void loadOrderDetail(int id) {
        async("Detalle del pedido " + id, () -> {
            Map<String, Object> o = api.order(id);
            List<Object> pays = api.paymentsOf(id);
            StringBuilder sb = new StringBuilder();
            sb.append("Pedido #").append(id).append("  ·  Estado: ").append(Json.str(o.get("estado"))).append("  ·  Total: ").append(money(o.get("total"))).append("\n");
            sb.append("Codigo de rastreo: ").append(codesByOrder.getOrDefault(id, "(sin asignar)")).append("\n\nLibros:\n");
            for (Object l : Json.arr(o.get("lineas")))
                sb.append(String.format("  • %-45s x%s  %s c/u  = %s%n", Json.str(Json.path(l, "title")), Json.str(Json.path(l, "cantidad")),
                        money(Json.path(l, "precio_unitario")), money(Json.path(l, "subtotal"))));
            sb.append("\nPagos:\n");
            for (Object p : pays) sb.append("  • #").append(Json.str(Json.path(p, "id"))).append(" ").append(Json.str(Json.path(p, "metodo"))).append(" ")
                    .append(money(Json.path(p, "monto"))).append(" -> ").append(Json.str(Json.path(p, "estado"))).append("  ref ").append(Json.str(Json.path(p, "referencia"))).append("\n");
            if (pays.isEmpty()) sb.append("  (sin pagos registrados)\n");
            return sb.toString();
        }, orderDetail::setText);
    }

    // ============================================ Modulo 6: rastreo WebSocket
    private Region trackingView() {
        trackCode = new TextField(); trackCode.setPromptText("LIB-MTY-2026-000125"); trackCode.setPrefWidth(220);
        myCodes = new ComboBox<>(); myCodes.setPromptText("Mis codigos");
        myCodes.setOnAction(e -> { if (myCodes.getValue() != null) trackCode.setText(myCodes.getValue()); });
        Button go = new Button("🚚 Rastrear pedido"), stopB = new Button("Detener");
        go.getStyleClass().add("primary");
        go.setOnAction(e -> startTracking(trackCode.getText().trim().toUpperCase()));
        stopB.setOnAction(e -> { closeSocket(); status("WebSocket cerrado"); });

        WebView wv = new WebView();
        mapEngine = wv.getEngine();
        mapEngine.setUserAgent("LibraryJavaDesktop/1.0 (JavaFX WebView; UDEM SC-2236)");
        mapEngine.getLoadWorker().stateProperty().addListener((o, a, b) -> { if (b == Worker.State.SUCCEEDED) mapReady = true; });
        mapEngine.load(Objects.requireNonNull(getClass().getResource("/map.html")).toExternalForm());

        GridPane g = new GridPane(); g.setHgap(8); g.setVgap(8);
        g.addRow(0, new Label("Estado:"), trkEstado);
        g.addRow(1, new Label("Ubicacion:"), trkPos);
        g.addRow(2, new Label("Progreso:"), trkProg);
        g.addRow(3, new Label("Ruta:"), trkRuta);
        trkEstado.getStyleClass().add("estado");
        trkLog.setEditable(false); trkLog.setWrapText(true);
        VBox side = new VBox(10, new Label("Seguimiento en tiempo real"), g, new Label("Mensajes WebSocket:"), trkLog);
        VBox.setVgrow(trkLog, Priority.ALWAYS); side.setPrefWidth(320); side.setPadding(new Insets(0, 0, 0, 12));
        HBox bar = new HBox(10, new Label("Codigo:"), trackCode, myCodes, go, stopB); bar.setAlignment(Pos.CENTER_LEFT);
        BorderPane bp = new BorderPane(wv, bar, side, null, null);
        BorderPane.setMargin(bar, new Insets(0, 0, 10, 0));
        bp.setPadding(new Insets(16));
        return bp;
    }

    private void loadMyCodes() {
        async("Consultar mis codigos (rastreo)", api::myTrackings, list -> {
            List<String> c = new ArrayList<>();
            for (Object o : list) c.add(Json.str(Json.path(o, "codigo")));
            myCodes.getItems().setAll(c);
        });
    }

    private void startTracking(String code) {
        if (code.isBlank()) { error("Rastreo", "Ingresa un codigo de rastreo."); return; }
        closeSocket();
        trkLog.clear();
        // Primero REST (autoriza: 403 si el pedido es ajeno, 404 si no existe), luego WebSocket.
        async("Validar codigo " + code, () -> api.tracking(code), snap -> {
            trkLog.appendText("REST /rastreo/" + code + " -> " + Json.str(snap.get("estado")) + "\n");
            StringBuilder buf = new StringBuilder();
            api.openTrackingSocket(code, new WebSocket.Listener() {
                @Override public void onOpen(WebSocket ws) {
                    Platform.runLater(() -> trkLog.appendText("WebSocket abierto: " + api.url("rastreo").replaceFirst("^http", "ws") + "/ws/rastreo/" + code + "\n"));
                    ws.request(1);
                }
                @Override public CompletionStage<?> onText(WebSocket ws, CharSequence data, boolean last) {
                    buf.append(data);
                    if (last) { String msg = buf.toString(); buf.setLength(0); Platform.runLater(() -> onTrackingMessage(msg)); }
                    ws.request(1);
                    return null;
                }
                @Override public CompletionStage<?> onClose(WebSocket ws, int st, String reason) {
                    Platform.runLater(() -> trkLog.appendText("WebSocket cerrado (" + st + ")\n"));
                    return null;
                }
                @Override public void onError(WebSocket ws, Throwable err) {
                    Platform.runLater(() -> trkLog.appendText("Error WebSocket: " + err.getMessage() + "\n"));
                }
            }).whenComplete((ws, ex) -> {
                if (ex != null) Platform.runLater(() -> error("Rastreo", "No se pudo abrir el WebSocket: " + ex.getMessage()));
                else socket = ws;
            });
        });
    }

    private void onTrackingMessage(String raw) {
        Map<String, Object> m = Json.obj(Json.parse(raw));
        String type = Json.str(m.get("type"));
        if ("error".equals(type)) { trkLog.appendText("Servidor: " + m.get("message") + "\n"); error("Rastreo", Json.str(m.get("message"))); return; }
        trkEstado.setText(Json.str(m.get("estado")));
        trkPos.setText(Json.str(m.get("lat")) + ", " + Json.str(m.get("lng")));
        trkProg.setText(Json.str(m.get("progreso")) + " %  (" + Json.str(m.get("indice")) + "/" + Json.str(m.get("total_puntos")) + ")");
        trkRuta.setText(Json.str(m.get("ruta")));
        String d = Json.write(Json.map("codigo", m.get("codigo"), "estado", m.get("estado"), "lat", m.get("lat"), "lng", m.get("lng"),
                "progreso", m.get("progreso"), "ruta", m.get("ruta")));
        if ("init".equals(type)) {
            trkLog.appendText("init: ruta '" + m.get("ruta") + "' con " + m.get("total_puntos") + " puntos\n");
            runMap("resetRoute(" + Json.write(m.get("ruta_completa")) + "," + Json.write(m.get("recorrido")) + "," + d + ")");
        } else {
            runMap("update(" + d + ")");
            trkLog.appendText(Json.str(m.get("timestamp")) + "  " + m.get("estado") + "  " + Json.str(m.get("progreso")) + "%\n");
        }
        if ("Entregado".equals(Json.str(m.get("estado")))) trkEstado.setText("✅ Entregado (fin de la ruta)");
    }

    private void runMap(String js) {
        if (!mapReady) { Timeline t = new Timeline(new KeyFrame(Duration.millis(400), e -> runMap(js))); t.play(); return; }
        try { mapEngine.executeScript(js); } catch (Exception e) { trkLog.appendText("JS: " + e.getMessage() + "\n"); }
    }

    private void closeSocket() {
        if (socket != null) { try { socket.sendClose(WebSocket.NORMAL_CLOSURE, "bye"); } catch (Exception ignored) { } socket = null; }
    }

    // ================================================ Perfil (users) + SOAP
    private Region profileView() {
        TextArea out = new TextArea(); out.setEditable(false); out.setStyle("-fx-font-family: Consolas;");
        Button prof = new Button("Mi perfil (users)"), sess = new Button("Sesion JWT (login /session)"),
                adm = new Button("Usuarios (solo admin)"), wsdl = new Button("SOAP: ver WSDL"), soap = new Button("SOAP: ObtenerEstadisticasPorModelo");
        adm.setDisable(!api.isAdmin());
        profileButtons.clear(); profileButtons.addAll(List.of(prof, sess, adm, wsdl, soap));
        prof.setOnAction(e -> async("Perfil (users)", api::profile, p -> {
            StringBuilder sb = new StringBuilder("PERFIL - GET " + api.url("users") + "/users/" + api.userId() + "\n\n");
            p.forEach((k, v) -> sb.append(String.format("%-18s %s%n", k + ":", Json.str(v))));
            out.setText(sb.toString());
        }));
        sess.setOnAction(e -> async("Sesion", api::sessionInfo, s -> out.setText("GET /session\n\n" + pretty(s, 0))));
        adm.setOnAction(e -> async("Listar usuarios (admin)", api::listUsers, l -> {
            StringBuilder sb = new StringBuilder("GET /users (requiere rol administrador)\n\n");
            for (Object u : l) sb.append(String.format("#%-4s %-30s %s%n", Json.str(Json.path(u, "id")), Json.str(Json.path(u, "email")), Json.str(Json.path(u, "role"))));
            out.setText(sb.toString());
        }));
        wsdl.setOnAction(e -> async("WSDL", () -> api.raw("GET", "books", "/wsdl", null, null, null), out::setText));
        soap.setOnAction(e -> {
            String env = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:lib=\"http://udem.edu/sc3705/soap/library\">\n"
                    + "  <soap:Body><lib:ObtenerEstadisticasPorModelo/></soap:Body>\n</soap:Envelope>";
            async("Llamada SOAP", () -> api.raw("POST", "books", "/soap", env, "text/xml; charset=utf-8",
                    Map.of("SOAPAction", "http://udem.edu/sc3705/soap/library/ObtenerEstadisticasPorModelo", "Authorization", "Bearer " + api.accessToken)),
                    r -> out.setText("REQUEST:\n" + env + "\n\nRESPONSE:\n" + r));
        });
        VBox v = new VBox(10, h1("👤 Perfil y servicios"), new FlowPane(10, 10, prof, sess, adm, wsdl, soap), out);
        VBox.setVgrow(out, Priority.ALWAYS); v.setPadding(new Insets(16));
        Platform.runLater(prof::fire);
        return v;
    }

    private static String pretty(Object o, int ind) {
        String pad = "  ".repeat(ind);
        if (o instanceof Map<?, ?> m) {
            StringBuilder sb = new StringBuilder();
            m.forEach((k, v) -> {
                if (v instanceof Map) sb.append(pad).append(k).append(":\n").append(pretty(v, ind + 1));
                else sb.append(pad).append(k).append(": ").append(Json.str(v)).append("\n");
            });
            return sb.toString();
        }
        return pad + Json.str(o) + "\n";
    }
}
