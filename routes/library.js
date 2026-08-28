const express = require('express');
const router = express.Router();
const path = require('path');
const fs = require('fs');
const bcrypt = require('bcrypt');
const multer = require('multer');
const db = require('../config/db');
const { isAuthenticated, isAdmin } = require('../middleware/auth');

// ==============================================================================
// CONFIGURACIÓN DE MULTER PARA CARGA SEGURA DE IMÁGENES
// ==============================================================================
const uploadsDir = path.join(__dirname, '..', 'uploads');
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, uploadsDir);
  },
  filename: function (req, file, cb) {
    const ext = path.extname(file.originalname).toLowerCase();
    const sanitizedName = 'book-' + Date.now() + '-' + Math.round(Math.random() * 1e9) + ext;
    cb(null, sanitizedName);
  }
});

const fileFilter = (req, file, cb) => {
  const allowedMimeTypes = ['image/jpeg', 'image/png', 'image/webp'];
  if (allowedMimeTypes.includes(file.mimetype)) {
    cb(null, true);
  } else {
    cb(new Error('Solo se permiten archivos de imagen en formato JPG, PNG o WebP.'), false);
  }
};

const upload = multer({
  storage: storage,
  limits: { fileSize: 5 * 1024 * 1024 }, // 5 MB
  fileFilter: fileFilter
});

// ==============================================================================
// RUTAS DE AUTENTICACIÓN Y SESIÓN
// ==============================================================================

// Vista de Login
router.get('/login', (req, res) => {
  if (req.session && req.session.user) {
    return res.redirect('/library');
  }
  res.render('login', { title: 'Iniciar Sesión - Librería' });
});

// Procesar Login (Consultas Parametrizadas y Verificación Bcrypt)
router.post('/login', async (req, res, next) => {
  try {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.redirect('/library/login?error=' + encodeURIComponent('Todos los campos son obligatorios.'));
    }

    const userResult = await db.query(
      'SELECT id, username, password_hash, role FROM users WHERE username = $1',
      [username.trim()]
    );

    if (userResult.rows.length === 0) {
      return res.redirect('/library/login?error=' + encodeURIComponent('Credenciales incorrectas.'));
    }

    const user = userResult.rows[0];
    const match = await bcrypt.compare(password, user.password_hash);
    if (!match) {
      return res.redirect('/library/login?error=' + encodeURIComponent('Credenciales incorrectas.'));
    }

    // Iniciar sesión
    req.session.user = {
      id: user.id,
      username: user.username,
      role: user.role
    };

    return res.redirect('/library?success=' + encodeURIComponent(`¡Bienvenido de nuevo, ${user.username}!`));
  } catch (error) {
    next(error);
  }
});

// Procesar Registro de Nuevos Usuarios (Solo rol 'Usuario' permitido públicamente)
router.post('/register', async (req, res, next) => {
  try {
    const { username, password, confirm_password } = req.body;

    if (!username || !password || !confirm_password) {
      return res.redirect('/library/login?error=' + encodeURIComponent('Todos los campos de registro son obligatorios.'));
    }

    if (password !== confirm_password) {
      return res.redirect('/library/login?error=' + encodeURIComponent('Las contraseñas no coinciden.'));
    }

    if (password.length < 4) {
      return res.redirect('/library/login?error=' + encodeURIComponent('La contraseña debe tener al menos 4 caracteres.'));
    }

    // Verificar si el usuario ya existe
    const existing = await db.query('SELECT id FROM users WHERE username = $1', [username.trim()]);
    if (existing.rows.length > 0) {
      return res.redirect('/library/login?error=' + encodeURIComponent('El nombre de usuario ya se encuentra registrado.'));
    }

    const saltRounds = 10;
    const passwordHash = await bcrypt.hash(password, saltRounds);

    await db.query(
      'INSERT INTO users (username, password_hash, role) VALUES ($1, $2, $3)',
      [username.trim(), passwordHash, 'Usuario']
    );

    return res.redirect('/library/login?success=' + encodeURIComponent('Registro exitoso. Ahora puede iniciar sesión con su cuenta.'));
  } catch (error) {
    next(error);
  }
});

// Cerrar Sesión
router.post('/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) {
      console.error('Error al destruir sesión:', err);
    }
    res.clearCookie('connect.sid');
    res.redirect('/library/login?success=' + encodeURIComponent('Sesión cerrada correctamente.'));
  });
});

// ==============================================================================
// RUTAS DE CATÁLOGO Y CONSULTA (USUARIOS AUTENTICADOS)
// ==============================================================================

// Catálogo Principal con Filtros y Búsqueda por Título / ISBN
router.get('/', isAuthenticated, async (req, res, next) => {
  try {
    const { q, category_id, format_id, genre_id } = req.query;

    let queryText = `
      SELECT 
        b.id,
        b.isbn,
        b.title,
        b.publication_year,
        b.price,
        b.stock,
        f.name AS format_name,
        c.name AS category_name,
        COALESCE(
          (SELECT image_url FROM book_images WHERE book_id = b.id AND is_cover = TRUE LIMIT 1),
          (SELECT image_url FROM book_images WHERE book_id = b.id LIMIT 1),
          '/library/public/img/default-book.png'
        ) AS cover_image,
        COALESCE(
          (SELECT string_agg(a.name, ', ') 
           FROM book_authors ba 
           JOIN authors a ON ba.author_id = a.id 
           WHERE ba.book_id = b.id), 
          'Sin autor asignado'
        ) AS authors_list,
        COALESCE(
          (SELECT string_agg(g.name, ', ') 
           FROM book_genres bg 
           JOIN genres g ON bg.genre_id = g.id 
           WHERE bg.book_id = b.id), 
          'General'
        ) AS genres_list
      FROM books b
      JOIN formats f ON b.format_id = f.id
      JOIN categories c ON b.category_id = c.id
      WHERE 1=1
    `;

    const params = [];
    let paramIndex = 1;

    if (q && q.trim() !== '') {
      queryText += ` AND (b.title ILIKE $${paramIndex} OR b.isbn ILIKE $${paramIndex})`;
      params.push(`%${q.trim()}%`);
      paramIndex++;
    }

    if (category_id && category_id !== '') {
      queryText += ` AND b.category_id = $${paramIndex}`;
      params.push(parseInt(category_id, 10));
      paramIndex++;
    }

    if (format_id && format_id !== '') {
      queryText += ` AND b.format_id = $${paramIndex}`;
      params.push(parseInt(format_id, 10));
      paramIndex++;
    }

    if (genre_id && genre_id !== '') {
      queryText += ` AND b.id IN (SELECT book_id FROM book_genres WHERE genre_id = $${paramIndex})`;
      params.push(parseInt(genre_id, 10));
      paramIndex++;
    }

    queryText += ` ORDER BY b.id ASC`;

    const booksResult = await db.query(queryText, params);
    const categoriesResult = await db.query('SELECT id, name FROM categories ORDER BY name ASC');
    const formatsResult = await db.query('SELECT id, name FROM formats ORDER BY name ASC');
    const genresResult = await db.query('SELECT id, name FROM genres ORDER BY name ASC');

    res.render('index', {
      title: 'Catálogo de Libros - Monolito Librería',
      books: booksResult.rows,
      categories: categoriesResult.rows,
      formats: formatsResult.rows,
      genres: genresResult.rows,
      filters: {
        q: q || '',
        category_id: category_id || '',
        format_id: format_id || '',
        genre_id: genre_id || ''
      }
    });
  } catch (error) {
    next(error);
  }
});

// Detalle de un Libro Específico (Con autores, géneros, imágenes y conceptos de 4FN)
router.get('/books/:id', isAuthenticated, async (req, res, next) => {
  try {
    const bookId = parseInt(req.params.id, 10);
    if (isNaN(bookId)) {
      return res.status(404).render('error', {
        status: 404,
        message: 'Libro no encontrado',
        details: 'El identificador del libro proporcionado no es válido.'
      });
    }

    // 1. Obtener datos del libro
    const bookResult = await db.query(
      `SELECT b.*, f.name AS format_name, c.name AS category_name
       FROM books b
       JOIN formats f ON b.format_id = f.id
       JOIN categories c ON b.category_id = c.id
       WHERE b.id = $1`,
      [bookId]
    );

    if (bookResult.rows.length === 0) {
      return res.status(404).render('error', {
        status: 404,
        message: 'Libro no encontrado',
        details: 'El libro solicitado no existe en la base de datos.'
      });
    }

    const book = bookResult.rows[0];

    // 2. Obtener autores asociados
    const authorsResult = await db.query(
      `SELECT a.id, a.name, a.biography, a.country 
       FROM book_authors ba 
       JOIN authors a ON ba.author_id = a.id 
       WHERE ba.book_id = $1 ORDER BY a.name ASC`,
      [bookId]
    );

    // 3. Obtener géneros asociados
    const genresResult = await db.query(
      `SELECT g.id, g.name 
       FROM book_genres bg 
       JOIN genres g ON bg.genre_id = g.id 
       WHERE bg.book_id = $1 ORDER BY g.name ASC`,
      [bookId]
    );

    // 4. Obtener galería de imágenes
    const imagesResult = await db.query(
      `SELECT id, image_url, alt_text, is_cover 
       FROM book_images 
       WHERE book_id = $1 ORDER BY is_cover DESC, id ASC`,
      [bookId]
    );

    // 5. Obtener conceptos y definiciones específicas asociadas al libro
    const conceptsResult = await db.query(
      `SELECT c.id AS concept_id, c.name AS concept_name, c.general_summary, bc.specific_definition, bc.chapter_page
       FROM book_concepts bc
       JOIN concepts c ON bc.concept_id = c.id
       WHERE bc.book_id = $1
       ORDER BY c.name ASC`,
      [bookId]
    );

    // 6. Si es administrador, obtener lista de todos los conceptos disponibles para asociar
    let availableConcepts = [];
    if (req.session.user && req.session.user.role === 'Administrador') {
      const allConceptsResult = await db.query('SELECT id, name FROM concepts ORDER BY name ASC');
      availableConcepts = allConceptsResult.rows;
    }

    res.render('detail', {
      title: `${book.title} - Detalle del Libro`,
      book,
      authors: authorsResult.rows,
      genres: genresResult.rows,
      images: imagesResult.rows,
      concepts: conceptsResult.rows,
      availableConcepts
    });
  } catch (error) {
    next(error);
  }
});

// ==============================================================================
// RUTAS DE ADMINISTRACIÓN (SOLO ROL 'Administrador')
// ==============================================================================

// Dashboard de Gestión de Catálogos y Entidades
router.get('/admin/catalog', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const booksResult = await db.query(
      `SELECT b.id, b.isbn, b.title, b.publication_year, b.price, b.stock, f.name AS format_name, c.name AS category_name
       FROM books b
       JOIN formats f ON b.format_id = f.id
       JOIN categories c ON b.category_id = c.id
       ORDER BY b.id DESC`
    );

    const authorsResult = await db.query('SELECT * FROM authors ORDER BY name ASC');
    const genresResult = await db.query('SELECT * FROM genres ORDER BY name ASC');
    const formatsResult = await db.query('SELECT * FROM formats ORDER BY name ASC');
    const categoriesResult = await db.query('SELECT * FROM categories ORDER BY name ASC');
    const conceptsResult = await db.query('SELECT * FROM concepts ORDER BY name ASC');

    res.render('admin_catalog', {
      title: 'Administración de Catálogos - Panel de Control',
      books: booksResult.rows,
      authors: authorsResult.rows,
      genres: genresResult.rows,
      formats: formatsResult.rows,
      categories: categoriesResult.rows,
      concepts: conceptsResult.rows
    });
  } catch (error) {
    next(error);
  }
});

// Formulario de Creación de Libro
router.get('/admin/books/new', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const authorsResult = await db.query('SELECT id, name FROM authors ORDER BY name ASC');
    const genresResult = await db.query('SELECT id, name FROM genres ORDER BY name ASC');
    const formatsResult = await db.query('SELECT id, name FROM formats ORDER BY name ASC');
    const categoriesResult = await db.query('SELECT id, name FROM categories ORDER BY name ASC');

    res.render('admin_book_form', {
      title: 'Registrar Nuevo Libro',
      isEdit: false,
      book: {},
      selectedAuthors: [],
      selectedGenres: [],
      authors: authorsResult.rows,
      genres: genresResult.rows,
      formats: formatsResult.rows,
      categories: categoriesResult.rows
    });
  } catch (error) {
    next(error);
  }
});

// Procesar Creación de Libro con Transacción SQL Segura
router.post('/admin/books/new', isAuthenticated, isAdmin, upload.single('cover_image'), async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    const { isbn, title, publication_year, price, stock, format_id, category_id, author_ids, genre_ids } = req.body;

    if (!isbn || !title || !publication_year || !price || !stock || !format_id || !category_id) {
      client.release();
      return res.redirect('/library/admin/books/new?error=' + encodeURIComponent('Todos los campos obligatorios deben completarse.'));
    }

    await client.query('BEGIN');

    // 1. Insertar libro
    const insertBookQuery = `
      INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      RETURNING id
    `;
    const bookResult = await client.query(insertBookQuery, [
      isbn.trim(),
      title.trim(),
      parseInt(publication_year, 10),
      parseFloat(price),
      parseInt(stock, 10),
      parseInt(format_id, 10),
      parseInt(category_id, 10)
    ]);

    const newBookId = bookResult.rows[0].id;

    // 2. Asociar autores seleccionados
    if (author_ids) {
      const selectedAuthorIds = Array.isArray(author_ids) ? author_ids : [author_ids];
      for (const authId of selectedAuthorIds) {
        await client.query(
          'INSERT INTO book_authors (book_id, author_id) VALUES ($1, $2)',
          [newBookId, parseInt(authId, 10)]
        );
      }
    }

    // 3. Asociar géneros seleccionados
    if (genre_ids) {
      const selectedGenreIds = Array.isArray(genre_ids) ? genre_ids : [genre_ids];
      for (const genId of selectedGenreIds) {
        await client.query(
          'INSERT INTO book_genres (book_id, genre_id) VALUES ($1, $2)',
          [newBookId, parseInt(genId, 10)]
        );
      }
    }

    // 4. Si se subió imagen de portada
    if (req.file) {
      const imageUrl = `/library/uploads/${req.file.filename}`;
      await client.query(
        'INSERT INTO book_images (book_id, image_url, alt_text, is_cover) VALUES ($1, $2, $3, TRUE)',
        [newBookId, imageUrl, `Portada de ${title.trim()}`]
      );
    }

    await client.query('COMMIT');
    client.release();

    return res.redirect(`/library/books/${newBookId}?success=` + encodeURIComponent('Libro registrado exitosamente en el sistema.'));
  } catch (error) {
    await client.query('ROLLBACK');
    client.release();
    if (error.code === '23505') { // Código de violación de clave única en PostgreSQL
      return res.redirect('/library/admin/books/new?error=' + encodeURIComponent('Error: El ISBN especificado ya existe en la base de datos.'));
    }
    next(error);
  }
});

// Formulario de Edición de Libro
router.get('/admin/books/edit/:id', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const bookId = parseInt(req.params.id, 10);
    const bookResult = await db.query('SELECT * FROM books WHERE id = $1', [bookId]);

    if (bookResult.rows.length === 0) {
      return res.status(404).render('error', {
        status: 404,
        message: 'Libro no encontrado',
        details: 'El libro solicitado para edición no existe.'
      });
    }

    const currentAuthors = await db.query('SELECT author_id FROM book_authors WHERE book_id = $1', [bookId]);
    const currentGenres = await db.query('SELECT genre_id FROM book_genres WHERE book_id = $1', [bookId]);

    const authorsResult = await db.query('SELECT id, name FROM authors ORDER BY name ASC');
    const genresResult = await db.query('SELECT id, name FROM genres ORDER BY name ASC');
    const formatsResult = await db.query('SELECT id, name FROM formats ORDER BY name ASC');
    const categoriesResult = await db.query('SELECT id, name FROM categories ORDER BY name ASC');

    res.render('admin_book_form', {
      title: `Editar Libro: ${bookResult.rows[0].title}`,
      isEdit: true,
      book: bookResult.rows[0],
      selectedAuthors: currentAuthors.rows.map(r => r.author_id),
      selectedGenres: currentGenres.rows.map(r => r.genre_id),
      authors: authorsResult.rows,
      genres: genresResult.rows,
      formats: formatsResult.rows,
      categories: categoriesResult.rows
    });
  } catch (error) {
    next(error);
  }
});

// Procesar Edición de Libro
router.post('/admin/books/edit/:id', isAuthenticated, isAdmin, async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    const bookId = parseInt(req.params.id, 10);
    const { isbn, title, publication_year, price, stock, format_id, category_id, author_ids, genre_ids } = req.body;

    await client.query('BEGIN');

    await client.query(
      `UPDATE books 
       SET isbn = $1, title = $2, publication_year = $3, price = $4, stock = $5, format_id = $6, category_id = $7
       WHERE id = $8`,
      [
        isbn.trim(),
        title.trim(),
        parseInt(publication_year, 10),
        parseFloat(price),
        parseInt(stock, 10),
        parseInt(format_id, 10),
        parseInt(category_id, 10),
        bookId
      ]
    );

    // Actualizar autores
    await client.query('DELETE FROM book_authors WHERE book_id = $1', [bookId]);
    if (author_ids) {
      const selectedAuthorIds = Array.isArray(author_ids) ? author_ids : [author_ids];
      for (const authId of selectedAuthorIds) {
        await client.query('INSERT INTO book_authors (book_id, author_id) VALUES ($1, $2)', [bookId, parseInt(authId, 10)]);
      }
    }

    // Actualizar géneros
    await client.query('DELETE FROM book_genres WHERE book_id = $1', [bookId]);
    if (genre_ids) {
      const selectedGenreIds = Array.isArray(genre_ids) ? genre_ids : [genre_ids];
      for (const genId of selectedGenreIds) {
        await client.query('INSERT INTO book_genres (book_id, genre_id) VALUES ($1, $2)', [bookId, parseInt(genId, 10)]);
      }
    }

    await client.query('COMMIT');
    client.release();

    return res.redirect(`/library/books/${bookId}?success=` + encodeURIComponent('Libro actualizado correctamente.'));
  } catch (error) {
    await client.query('ROLLBACK');
    client.release();
    next(error);
  }
});

// Eliminar Libro
router.post('/admin/books/delete/:id', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const bookId = parseInt(req.params.id, 10);
    await db.query('DELETE FROM books WHERE id = $1', [bookId]);
    return res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Libro eliminado correctamente.'));
  } catch (error) {
    next(error);
  }
});

// ==============================================================================
// GESTIÓN DE CONCEPTOS ASOCIADOS AL CONTENIDO DEL LIBRO (4FN)
// ==============================================================================

// Asociar o actualizar concepto específico en un libro
router.post('/admin/books/:id/concepts/add', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const bookId = parseInt(req.params.id, 10);
    const { concept_id, specific_definition, chapter_page } = req.body;

    if (!concept_id || !specific_definition) {
      return res.redirect(`/library/books/${bookId}?error=` + encodeURIComponent('El concepto y su definición específica son obligatorios.'));
    }

    await db.query(
      `INSERT INTO book_concepts (book_id, concept_id, specific_definition, chapter_page)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (book_id, concept_id) 
       DO UPDATE SET specific_definition = EXCLUDED.specific_definition, chapter_page = EXCLUDED.chapter_page`,
      [bookId, parseInt(concept_id, 10), specific_definition.trim(), chapter_page ? chapter_page.trim() : null]
    );

    return res.redirect(`/library/books/${bookId}?success=` + encodeURIComponent('Concepto registrado correctamente en el libro.'));
  } catch (error) {
    next(error);
  }
});

// Desasociar concepto de un libro
router.post('/admin/books/:id/concepts/delete/:concept_id', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const bookId = parseInt(req.params.id, 10);
    const conceptId = parseInt(req.params.concept_id, 10);

    await db.query('DELETE FROM book_concepts WHERE book_id = $1 AND concept_id = $2', [bookId, conceptId]);
    return res.redirect(`/library/books/${bookId}?success=` + encodeURIComponent('Concepto removido del libro.'));
  } catch (error) {
    next(error);
  }
});

// ==============================================================================
// GESTIÓN Y CARGA DE IMÁGENES
// ==============================================================================

// Cargar imagen adicional para un libro
router.post('/admin/books/:id/images/upload', isAuthenticated, isAdmin, upload.single('book_image'), async (req, res, next) => {
  try {
    const bookId = parseInt(req.params.id, 10);
    const { alt_text, is_cover } = req.body;

    if (!req.file) {
      return res.redirect(`/library/books/${bookId}?error=` + encodeURIComponent('Debe seleccionar un archivo de imagen válido.'));
    }

    const imageUrl = `/library/uploads/${req.file.filename}`;
    const makeCover = is_cover === 'true' || is_cover === 'on';

    if (makeCover) {
      await db.query('UPDATE book_images SET is_cover = FALSE WHERE book_id = $1', [bookId]);
    }

    await db.query(
      'INSERT INTO book_images (book_id, image_url, alt_text, is_cover) VALUES ($1, $2, $3, $4)',
      [bookId, imageUrl, alt_text ? alt_text.trim() : 'Imagen de libro', makeCover]
    );

    return res.redirect(`/library/books/${bookId}?success=` + encodeURIComponent('Imagen cargada con éxito.'));
  } catch (error) {
    next(error);
  }
});

// Establecer imagen como portada principal
router.post('/admin/books/:id/images/:image_id/cover', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const bookId = parseInt(req.params.id, 10);
    const imageId = parseInt(req.params.image_id, 10);

    await db.query('UPDATE book_images SET is_cover = FALSE WHERE book_id = $1', [bookId]);
    await db.query('UPDATE book_images SET is_cover = TRUE WHERE id = $1 AND book_id = $2', [imageId, bookId]);

    return res.redirect(`/library/books/${bookId}?success=` + encodeURIComponent('Portada actualizada exitosamente.'));
  } catch (error) {
    next(error);
  }
});

// Eliminar imagen de un libro
router.post('/admin/books/:id/images/:image_id/delete', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const bookId = parseInt(req.params.id, 10);
    const imageId = parseInt(req.params.image_id, 10);

    const imgResult = await db.query('SELECT image_url FROM book_images WHERE id = $1 AND book_id = $2', [imageId, bookId]);
    if (imgResult.rows.length > 0) {
      const imgPath = imgResult.rows[0].image_url;
      // Eliminar registro
      await db.query('DELETE FROM book_images WHERE id = $1', [imageId]);

      // Eliminar archivo físico si está en uploads
      if (imgPath.startsWith('/library/uploads/')) {
        const filename = imgPath.replace('/library/uploads/', '');
        const physicalPath = path.join(uploadsDir, filename);
        if (fs.existsSync(physicalPath)) {
          fs.unlinkSync(physicalPath);
        }
      }
    }

    return res.redirect(`/library/books/${bookId}?success=` + encodeURIComponent('Imagen eliminada.'));
  } catch (error) {
    next(error);
  }
});

// ==============================================================================
// CRUD DE CATÁLOGOS AUXILIARES (Autores, Géneros, Formatos, Categorías, Conceptos)
// ==============================================================================

// Autores
router.post('/admin/authors/new', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const { name, biography, country } = req.body;
    if (!name) return res.redirect('/library/admin/catalog?error=' + encodeURIComponent('El nombre del autor es obligatorio.'));
    await db.query('INSERT INTO authors (name, biography, country) VALUES ($1, $2, $3)', [name.trim(), biography ? biography.trim() : null, country ? country.trim() : null]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Autor agregado correctamente.'));
  } catch (error) {
    next(error);
  }
});

router.post('/admin/authors/delete/:id', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const id = parseInt(req.params.id, 10);
    await db.query('DELETE FROM authors WHERE id = $1', [id]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Autor eliminado.'));
  } catch (error) {
    res.redirect('/library/admin/catalog?error=' + encodeURIComponent('No se puede eliminar el autor porque tiene libros vinculados.'));
  }
});

// Géneros
router.post('/admin/genres/new', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const { name } = req.body;
    if (!name) return res.redirect('/library/admin/catalog?error=' + encodeURIComponent('El nombre del género es obligatorio.'));
    await db.query('INSERT INTO genres (name) VALUES ($1)', [name.trim()]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Género agregado.'));
  } catch (error) {
    next(error);
  }
});

router.post('/admin/genres/delete/:id', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const id = parseInt(req.params.id, 10);
    await db.query('DELETE FROM genres WHERE id = $1', [id]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Género eliminado.'));
  } catch (error) {
    res.redirect('/library/admin/catalog?error=' + encodeURIComponent('No se puede eliminar el género porque tiene libros vinculados.'));
  }
});

// Formatos
router.post('/admin/formats/new', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const { name, description } = req.body;
    if (!name) return res.redirect('/library/admin/catalog?error=' + encodeURIComponent('El nombre del formato es obligatorio.'));
    await db.query('INSERT INTO formats (name, description) VALUES ($1, $2)', [name.trim(), description ? description.trim() : null]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Formato agregado.'));
  } catch (error) {
    next(error);
  }
});

router.post('/admin/formats/delete/:id', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const id = parseInt(req.params.id, 10);
    await db.query('DELETE FROM formats WHERE id = $1', [id]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Formato eliminado.'));
  } catch (error) {
    res.redirect('/library/admin/catalog?error=' + encodeURIComponent('No se puede eliminar el formato porque está siendo utilizado por uno o más libros.'));
  }
});

// Categorías
router.post('/admin/categories/new', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const { name, description } = req.body;
    if (!name) return res.redirect('/library/admin/catalog?error=' + encodeURIComponent('El nombre de la categoría es obligatorio.'));
    await db.query('INSERT INTO categories (name, description) VALUES ($1, $2)', [name.trim(), description ? description.trim() : null]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Categoría agregada.'));
  } catch (error) {
    next(error);
  }
});

router.post('/admin/categories/delete/:id', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const id = parseInt(req.params.id, 10);
    await db.query('DELETE FROM categories WHERE id = $1', [id]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Categoría eliminada.'));
  } catch (error) {
    res.redirect('/library/admin/catalog?error=' + encodeURIComponent('No se puede eliminar la categoría porque está siendo utilizada por uno o más libros.'));
  }
});

// Conceptos (Catálogo Global)
router.post('/admin/concepts/new', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const { name, general_summary } = req.body;
    if (!name) return res.redirect('/library/admin/catalog?error=' + encodeURIComponent('El nombre del concepto es obligatorio.'));
    await db.query('INSERT INTO concepts (name, general_summary) VALUES ($1, $2)', [name.trim(), general_summary ? general_summary.trim() : null]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Concepto agregado al catálogo.'));
  } catch (error) {
    next(error);
  }
});

router.post('/admin/concepts/delete/:id', isAuthenticated, isAdmin, async (req, res, next) => {
  try {
    const id = parseInt(req.params.id, 10);
    await db.query('DELETE FROM concepts WHERE id = $1', [id]);
    res.redirect('/library/admin/catalog?success=' + encodeURIComponent('Concepto eliminado.'));
  } catch (error) {
    res.redirect('/library/admin/catalog?error=' + encodeURIComponent('No se puede eliminar el concepto porque está vinculado a definiciones de libros.'));
  }
});

module.exports = router;
