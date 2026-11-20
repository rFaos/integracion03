package mx.udem.library;

import java.math.BigDecimal;
import java.util.*;

/**
 * Parser/serializador JSON minimo (sin dependencias externas).
 * Objetos -> Map<String,Object>, arreglos -> List<Object>, numeros -> BigDecimal.
 */
public final class Json {
    private final String s;
    private int i;

    private Json(String s) { this.s = s; }

    public static Object parse(String text) {
        Json p = new Json(text.trim());
        Object v = p.value();
        return v;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> obj(Object o) { return o instanceof Map ? (Map<String, Object>) o : new LinkedHashMap<>(); }

    @SuppressWarnings("unchecked")
    public static List<Object> arr(Object o) { return o instanceof List ? (List<Object>) o : new ArrayList<>(); }

    public static String str(Object o) { return o == null ? "" : (o instanceof BigDecimal b ? b.stripTrailingZeros().toPlainString() : o.toString()); }

    public static BigDecimal num(Object o) {
        if (o instanceof BigDecimal b) return b;
        try { return new BigDecimal(str(o)); } catch (Exception e) { return BigDecimal.ZERO; }
    }

    /** Navega por claves: Json.path(m, "data", "user", "id"). */
    public static Object path(Object o, String... keys) {
        for (String k : keys) { if (!(o instanceof Map)) return null; o = ((Map<?, ?>) o).get(k); }
        return o;
    }

    private Object value() {
        ws();
        char c = s.charAt(i);
        switch (c) {
            case '{': return object();
            case '[': return array();
            case '"': return string();
            case 't': i += 4; return Boolean.TRUE;
            case 'f': i += 5; return Boolean.FALSE;
            case 'n': i += 4; return null;
            default: return number();
        }
    }

    private Map<String, Object> object() {
        Map<String, Object> m = new LinkedHashMap<>();
        i++; ws();
        if (s.charAt(i) == '}') { i++; return m; }
        while (true) {
            ws(); String k = string(); ws(); i++; // ':'
            m.put(k, value()); ws();
            if (s.charAt(i++) == '}') return m;
        }
    }

    private List<Object> array() {
        List<Object> l = new ArrayList<>();
        i++; ws();
        if (s.charAt(i) == ']') { i++; return l; }
        while (true) {
            l.add(value()); ws();
            if (s.charAt(i++) == ']') return l;
        }
    }

    private String string() {
        StringBuilder b = new StringBuilder();
        i++;
        while (true) {
            char c = s.charAt(i++);
            if (c == '"') return b.toString();
            if (c == '\\') {
                char e = s.charAt(i++);
                switch (e) {
                    case 'n' -> b.append('\n'); case 't' -> b.append('\t'); case 'r' -> b.append('\r');
                    case 'b' -> b.append('\b'); case 'f' -> b.append('\f');
                    case 'u' -> { b.append((char) Integer.parseInt(s.substring(i, i + 4), 16)); i += 4; }
                    default -> b.append(e);
                }
            } else b.append(c);
        }
    }

    private BigDecimal number() {
        int st = i;
        while (i < s.length() && "+-0123456789.eE".indexOf(s.charAt(i)) >= 0) i++;
        return new BigDecimal(s.substring(st, i));
    }

    private void ws() { while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++; }

    // ------------------------------------------------------------ serializacion
    public static String write(Object o) {
        if (o == null) return "null";
        if (o instanceof String str) return quote(str);
        if (o instanceof Number || o instanceof Boolean) return o.toString();
        if (o instanceof Map<?, ?> m) {
            StringJoiner j = new StringJoiner(",", "{", "}");
            m.forEach((k, v) -> j.add(quote(k.toString()) + ":" + write(v)));
            return j.toString();
        }
        if (o instanceof Collection<?> c) {
            StringJoiner j = new StringJoiner(",", "[", "]");
            c.forEach(v -> j.add(write(v)));
            return j.toString();
        }
        return quote(o.toString());
    }

    private static String quote(String v) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : v.toCharArray()) {
            switch (c) {
                case '"' -> b.append("\\\""); case '\\' -> b.append("\\\\");
                case '\n' -> b.append("\\n"); case '\r' -> b.append("\\r"); case '\t' -> b.append("\\t");
                default -> { if (c < 0x20) b.append(String.format("\\u%04x", (int) c)); else b.append(c); }
            }
        }
        return b.append('"').toString();
    }

    public static Map<String, Object> map(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int k = 0; k < kv.length; k += 2) m.put((String) kv[k], kv[k + 1]);
        return m;
    }
}
