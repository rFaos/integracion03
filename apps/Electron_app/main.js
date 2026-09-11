/**
 * ==============================================================================
 * PROYECTO: INTEGRACION03 - PROMPT 04 (CLIENTE DE ESCRITORIO ELECTRON)
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
  const mainWindow = new BrowserWindow({
    width: 1120,
    height: 840,
    minWidth: 880,
    minHeight: 640,
    title: 'Clasificador Cloud Computing - Cliente Electron XML (SC-2236)',
    backgroundColor: '#0b0f19',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false // Permite peticiones directas HTTP cross-origin al microservicio cloud en GCP
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  // Menú básico o sin barra de menú estándar para aspecto nativo pulido
  mainWindow.setMenuBarVisibility(false);
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});
