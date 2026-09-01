<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" encoding="UTF-8" indent="yes" doctype-system="about:blank"/>

  <xsl:template match="/library">
    <html lang="en">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Academic Library - XSLT Transformed GUI (INTEGRACION03)</title>
        <link rel="preconnect" href="https://fonts.googleapis.com"/>
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous"/>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&amp;family=Outfit:wght@400;600;700;800&amp;display=swap" rel="stylesheet"/>
        <link rel="stylesheet" href="estilo03.css"/>
      </head>
      <body>
        <!-- Header Principal -->
        <header class="app-header">
          <div class="header-container">
            <div class="brand">
              <span class="logo-icon">📚</span>
              <span class="logo-text">Academic<strong>Library</strong></span>
              <span class="badge-tag">XSLT 1.0 Engine</span>
            </div>
            <div class="academic-badge">
              <span>UDEM • SC-2236 Integración de Aplicaciones</span>
            </div>
          </div>
        </header>

        <!-- Contenido Central -->
        <main class="main-container">
          <section class="hero-section">
            <h1>Bibliographic Catalog &amp; Cloud Concepts</h1>
            <p>XML data dynamically transformed to a modern responsive interface via XSLT stylesheet.</p>

            <!-- Métricas de Inventario -->
            <div class="stats-row">
              <div class="stat-card">
                <span class="stat-label">Total Titles</span>
                <span class="stat-value"><xsl:value-of select="count(book)"/></span>
              </div>
              <div class="stat-card">
                <span class="stat-label">In Stock (&gt;5)</span>
                <span class="stat-value text-green"><xsl:value-of select="count(book[stock &gt; 5])"/></span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Low Stock (1-5)</span>
                <span class="stat-value text-yellow"><xsl:value-of select="count(book[stock &gt; 0 and stock &lt;= 5])"/></span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Out of Stock</span>
                <span class="stat-value text-red"><xsl:value-of select="count(book[stock = 0])"/></span>
              </div>
            </div>
          </section>

          <!-- Rejilla de Libros -->
          <section class="catalog-grid">
            <xsl:for-each select="book">
              <article class="book-card">
                <div class="cover-wrapper">
                  <img src="{cover_image}" alt="{title}" class="cover-image" onerror="this.src='https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400'"/>
                  <span class="badge-format"><xsl:value-of select="format"/></span>
                </div>

                <div class="card-body">
                  <span class="badge-category"><xsl:value-of select="category"/></span>
                  <h2 class="book-title"><xsl:value-of select="title"/></h2>
                  
                  <p class="book-meta">
                    <span class="meta-authors">✍️ <xsl:for-each select="authors/author"><xsl:value-of select="."/><xsl:if test="position() != last()">, </xsl:if></xsl:for-each></span>
                  </p>

                  <div class="book-submeta">
                    <span class="meta-isbn"><code>ISBN: <xsl:value-of select="@isbn"/></code></span>
                    <span class="meta-year">📅 <xsl:value-of select="publication_year"/></span>
                  </div>

                  <div class="pricing-stock-row">
                    <div class="price-box">
                      <span class="price-val">$<xsl:value-of select="price"/> <xsl:value-of select="price/@currency"/></span>
                    </div>

                    <!-- Indicador Condicional de Stock con Reglas XSLT -->
                    <div class="stock-box">
                      <xsl:choose>
                        <xsl:when test="stock &gt; 5">
                          <span class="stock-badge in-stock">🟢 In Stock (<xsl:value-of select="stock"/>)</span>
                        </xsl:when>
                        <xsl:when test="stock &gt; 0">
                          <span class="stock-badge low-stock">🟡 Low Stock (<xsl:value-of select="stock"/>)</span>
                        </xsl:when>
                        <xsl:otherwise>
                          <span class="stock-badge out-stock">🔴 Out of Stock (0)</span>
                        </xsl:otherwise>
                      </xsl:choose>
                    </div>
                  </div>

                  <!-- Géneros -->
                  <div class="genres-row">
                    <xsl:for-each select="genres/genre">
                      <span class="genre-tag"><xsl:value-of select="."/></span>
                    </xsl:for-each>
                  </div>

                  <!-- Conceptos Contextuales 4FN -->
                  <xsl:if test="count(concepts/concept) &gt; 0">
                    <div class="concepts-box">
                      <span class="concepts-header">🧠 Associated Concepts (4FN):</span>
                      <ul class="concepts-list">
                        <xsl:for-each select="concepts/concept">
                          <li>
                            <strong><xsl:value-of select="@name"/>:</strong>
                            <span class="concept-def"><xsl:value-of select="definition"/></span>
                            <span class="concept-ref"><xsl:value-of select="chapter_page"/></span>
                          </li>
                        </xsl:for-each>
                      </ul>
                    </div>
                  </xsl:if>
                </div>
              </article>
            </xsl:for-each>
          </section>
        </main>

        <!-- Footer -->
        <footer class="app-footer">
          <p>© 2026 Fabián Azaed Orta Singlaterry (613504) • Universidad de Monterrey (UDEM)</p>
          <p class="footer-sub">INTEGRACION03 • XSLT 1.0 Client/Server-Side Transformation Engine</p>
        </footer>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
