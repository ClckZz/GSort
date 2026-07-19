const { app, BrowserWindow, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('node:path');
const fs = require('node:fs');

if (require('electron-squirrel-startup')) {
  app.quit();
}

let pyProcess = null;
let mainWindow = null;

function getPythonPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'python-runtime', 'python', 'python.exe');
  }
  return path.join(__dirname, '..', 'python-runtime', 'python', 'python.exe');
}

function getBackendScript() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'main.py');
  }
  return path.join(__dirname, '..', 'main.py');
}

function getBackendCwd() {
  return app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');
}

function startBackend() {
  const pythonPath = getPythonPath();
  const backendScriptPath = getBackendScript();

  const logPath = path.join(app.getPath('userData'), 'backend.log');
  const logStream = fs.createWriteStream(logPath, { flags: 'a' });

  logStream.write(`\n\n=== Neuer Start: ${new Date().toISOString()} ===\n`);
  logStream.write(`Python-Pfad existiert: ${fs.existsSync(pythonPath)} (${pythonPath})\n`);
  logStream.write(`Backend-Script existiert: ${fs.existsSync(backendScriptPath)} (${backendScriptPath})\n`);

  console.log('[main] Python-Pfad:', pythonPath, 'existiert:', fs.existsSync(pythonPath));
  console.log('[main] Backend-Script:', backendScriptPath, 'existiert:', fs.existsSync(backendScriptPath));
  console.log('[main] Log-Datei:', logPath);

  pyProcess = spawn(pythonPath, [backendScriptPath], {
    cwd: getBackendCwd(),
    env: {
      ...process.env,
      APP_DATA_DIR: app.getPath('userData'),
      PYTHONUNBUFFERED: '1',
    },
  });

  let started = false;

  pyProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log('[backend]', output);
    logStream.write(`[stdout] ${output}`);

    // TODO: change to lazy load --> visual startup doesnt require that long
    if (!started && output.includes('API_READY')) {
      started = true;
      createWindow();
    }
  });

  pyProcess.stderr.on('data', (data) => {
    const output = data.toString();
    console.error('[backend-error]', output);
    logStream.write(`[stderr] ${output}`);
  });

  pyProcess.on('error', (err) => {
    console.error('[main] Backend konnte nicht gestartet werden:', err);
    logStream.write(`[spawn-error] ${err.message}\n`);
  });

  pyProcess.on('exit', (code) => {
    console.log('[main] Backend beendet mit Code', code);
    logStream.write(`[exit] Code ${code}\n`);
  });

  setTimeout(() => {
    if (!started) {
      console.error('[main] Backend-Timeout, öffne Fenster trotzdem');
      logStream.write(`[timeout] Backend hat nach 30s kein API_READY gesendet\n`);
      createWindow();
    }
  }, 120000);
}

const createWindow = () => {
  if (mainWindow) return;

  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
};

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);

  startBackend();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pyProcess) pyProcess.kill();
});

app.on('will-quit', () => {
  if (pyProcess && process.platform === 'win32') {
    spawn('taskkill', ['/pid', pyProcess.pid, '/f', '/t']);
  }
});