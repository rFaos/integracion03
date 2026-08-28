/**
 * Servidor Principal de la Aplicación Web Monolítica de Librería
 * Arquitectura Server-Side Rendered (Node.js, Express, EJS, PostgreSQL)
 * Autor: Fabián Azaed Orta Singlaterry (613504)
 */

require('dotenv').config();
const express = require('express');
const session = require('express-session');
const path = require('path');
const libraryRoutes = require('./routes/library');
const { setLocals } = require('./middleware/auth');

const app = express();
const PORT = process.env.PORT || 3000;
const HOST = '127.0.0.1';

// 1. Configuración del Motor de Plantillas EJS
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// 2. Middlewares de Procesamiento de Formularios Server-Side (No JSON)
app.use(express.urlencoded({ extended: true }));

// 3. Configuración de Sesiones de Usuario
app.use(session({
  secret: process.env.SESSION_SECRET || 'secret_monolith_key_2026_sc2236',
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    maxAge: 1000 * 60 * 60 * 24, // 24 horas
    sameSite: 'lax'
  }
}));

// 4. Servir Archivos Estáticos bajo el prefijo /library
app.use('/library/public', express.static(path.join(__dirname, 'public')));
app.use('/library/uploads', express.static(path.join(__dirname, 'uploads')));

// 5. Inyección de Variables Locales para Vistas EJS
app.use(setLocals);

// 6. Montaje del Módulo Monolítico en el prefijo /library (Para Reverse Proxy)
app.use('/library', libraryRoutes);

// Redirección conveniente de la raíz hacia /library
app.get('/', (req, res) => {
  res.redirect('/library');
});

// 7. Manejo Controlado de Errores 404 (Recurso No Encontrado)
app.use((req, res) => {
  res.status(404).render('error', {
    status: 404,
    message: 'Página no encontrada',
    details: `La ruta solicitada "${req.originalUrl}" no existe en el servidor.`
  });
});

// 8. Manejo Controlado de Errores 500 (Sin exponer Stack Traces ni detalles de BD)
app.use((err, req, res, next) => {
  console.error('[Error de Servidor Monolito]:', err);
  const status = err.status || 500;
  res.status(status).render('error', {
    status: status,
    message: 'Error interno del servidor',
    details: 'Ha ocurrido un error inesperado al procesar su solicitud. Por motivos de seguridad no se muestran detalles técnicos.'
  });
});

// 9. Arranque del Servidor en Localhost (Aislamiento tras Reverse Proxy)
app.listen(PORT, HOST, () => {
  console.log(`=======================================================`);
  console.log(` Servidor Monolítico de Librería Activo`);
  console.log(` URL Local: http://${HOST}:${PORT}/library`);
  console.log(` Base de Datos: PostgreSQL @ ${process.env.DB_HOST || '127.0.0.1'}:${process.env.DB_PORT || 5432}`);
  console.log(` Entorno: Monolito Server-Side (Express + EJS + pg)`);
  console.log(`=======================================================`);
});
