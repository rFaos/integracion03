/**
 * Middleware de Autenticación y Autorización por Rol
 * Aplicación Web Monolítica de Librería
 */

// Middleware para verificar que el usuario tenga una sesión activa
function isAuthenticated(req, res, next) {
  if (req.session && req.session.user) {
    return next();
  }
  return res.redirect('/library/login?error=' + encodeURIComponent('Debe iniciar sesión para acceder a este recurso.'));
}

// Middleware para verificar que el usuario tenga rol 'Administrador'
function isAdmin(req, res, next) {
  if (req.session && req.session.user) {
    if (req.session.user.role === 'Administrador') {
      return next();
    }
    return res.status(403).render('error', {
      status: 403,
      message: 'Acceso Denegado',
      details: 'No cuenta con permisos de Administrador para realizar esta acción o acceder a este módulo.'
    });
  }
  return res.redirect('/library/login?error=' + encodeURIComponent('Debe iniciar sesión como Administrador.'));
}

// Middleware transversal para inyectar usuario y basePath en todas las vistas EJS
function setLocals(req, res, next) {
  res.locals.user = req.session ? req.session.user : null;
  res.locals.basePath = '/library';
  res.locals.query = req.query || {};
  res.locals.errorMessage = req.query.error || null;
  res.locals.successMessage = req.query.success || null;
  next();
}

module.exports = {
  isAuthenticated,
  isAdmin,
  setLocals
};
