/**
 * ==============================================================================
 * PROYECTO: INTEGRACION03 - CATALOGO DE LIBROS EN ELECTRON (WINDOWS 11)
 * ARCHIVO: main.js - Proceso Principal de Electron
 * AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
 * MATERIA: Integración de Aplicaciones Computacionales (SC-2236)
 * PROFESOR: Dr. Raúl Morales Salcedo
 * UNIVERSIDAD DE MONTERREY (UDEM) - PRIMAVERA 2026
 * ==============================================================================
 */

const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 1320,
    height: 900,
    minWidth: 980,
    minHeight: 680,
    title: 'Catálogo de Libros | Cliente Electron XML (Windows 11)',
    backgroundColor: '#0a0e17',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false // Permite peticiones directas HTTP/XML al microservicio en Google Cloud
    }
  });

  win.loadFile(path.join(__dirname, 'index.html'));
  win.setMenuBarVisibility(false);
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
