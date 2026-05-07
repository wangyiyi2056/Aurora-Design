import { app, BrowserWindow, ipcMain, dialog } from "electron"
import path from "path"
import { spawn, ChildProcess } from "child_process"
import fs from "fs"

const isDev = !app.isPackaged

let backendProcess: ChildProcess | null = null
let backendPort: number | null = null

function findProjectRoot(): string {
  if (isDev) {
    return path.resolve(__dirname, "../..")
  }
  // In production, project is bundled as extraResources
  const resourcesPath = process.resourcesPath
  const bundledProject = path.join(resourcesPath, "aurora-project")
  if (fs.existsSync(bundledProject)) {
    return bundledProject
  }
  // Fallback: try to find from working directory
  return process.cwd()
}

function commandExists(cmd: string): boolean {
  try {
    const result = require("child_process").execSync(`which ${cmd}`, { stdio: "pipe" })
    return result.toString().trim().length > 0
  } catch {
    return false
  }
}

function startBackend(): Promise<number> {
  return new Promise((resolve, reject) => {
    const projectRoot = findProjectRoot()
    const configPath = path.join(projectRoot, "configs", "aurora.toml")

    let command: string
    let args: string[]

    // 1. Prefer bundled .venv/uv if available (for fully bundled builds)
    const bundledUv = path.join(projectRoot, ".venv", "bin", "uv")
    if (fs.existsSync(bundledUv)) {
      command = bundledUv
      args = ["run", "uvicorn", "aurora_app.main:app", "--port", "0", "--host", "127.0.0.1"]
    }
    // 2. Fall back to system uv
    else if (commandExists("uv")) {
      command = "uv"
      args = ["run", "uvicorn", "aurora_app.main:app", "--port", "0", "--host", "127.0.0.1"]
    }
    // 3. Fall back to system python with uvicorn
    else if (commandExists("python3")) {
      command = "python3"
      args = ["-m", "uvicorn", "aurora_app.main:app", "--port", "0", "--host", "127.0.0.1"]
    } else if (commandExists("python")) {
      command = "python"
      args = ["-m", "uvicorn", "aurora_app.main:app", "--port", "0", "--host", "127.0.0.1"]
    } else {
      reject(
        new Error(
          "Cannot find uv or python on this system.\n" +
            "Please install uv: https://docs.astral.sh/uv\n" +
            "Or install Python 3.10+ and run: pip install uvicorn fastapi"
        )
      )
      return
    }

    console.log(`[Electron] Starting backend: ${command} ${args.join(" ")} in ${projectRoot}`)

    backendProcess = spawn(command, args, {
      cwd: projectRoot,
      env: {
        ...process.env,
        AURORA_CONFIG: configPath,
      },
      stdio: ["ignore", "pipe", "pipe"],
    })

    let stdoutBuffer = ""
    let stderrBuffer = ""

    function tryExtractPort(text: string) {
      // Uvicorn prints: Uvicorn running on http://127.0.0.1:PORT
      const match = text.match(/Uvicorn running on http:\/\/127\.0\.0\.1:(\d+)/)
      if (match && !backendPort) {
        backendPort = parseInt(match[1], 10)
        console.log(`[Electron] Backend started on port ${backendPort}`)
        resolve(backendPort)
      }
    }

    backendProcess.stdout?.on("data", (data) => {
      const text = data.toString()
      stdoutBuffer += text
      console.log(`[Backend stdout] ${text.trim()}`)
      tryExtractPort(text)
    })

    backendProcess.stderr?.on("data", (data) => {
      const text = data.toString()
      stderrBuffer += text
      console.error(`[Backend stderr] ${text.trim()}`)
      tryExtractPort(text)
    })

    backendProcess.on("error", (err) => {
      console.error("[Electron] Backend process error:", err)
      reject(err)
    })

    backendProcess.on("exit", (code) => {
      if (!backendPort) {
        reject(new Error(`Backend exited with code ${code}. Stderr: ${stderrBuffer}`))
      }
    })

    // Timeout if backend doesn't start within 30 seconds
    setTimeout(() => {
      if (!backendPort) {
        backendProcess?.kill()
        reject(new Error("Backend failed to start within 30 seconds"))
      }
    }, 30000)
  })
}

function waitForBackend(port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const maxAttempts = 30
    let attempts = 0

    const check = () => {
      attempts++
      const http = require("http")
      const req = http.get(`http://127.0.0.1:${port}/api/v1/health`, (res: any) => {
        if (res.statusCode === 200) {
          resolve()
        } else {
          retry()
        }
      })

      req.on("error", retry)
      req.setTimeout(1000, () => {
        req.destroy()
        retry()
      })
    }

    const retry = () => {
      if (attempts >= maxAttempts) {
        reject(new Error("Backend health check failed after 30 attempts"))
        return
      }
      setTimeout(check, 1000)
    }

    check()
  })
}

async function createWindow() {
  try {
    const port = backendPort || await startBackend()
    await waitForBackend(port)

    const win = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 900,
      minHeight: 600,
      titleBarStyle: "hiddenInset",
      webPreferences: {
        preload: path.join(__dirname, "preload.cjs"),
        contextIsolation: true,
        nodeIntegration: false,
      },
    })

    // Expose backend port via IPC
    ipcMain.handle("get-backend-url", () => `http://127.0.0.1:${port}/api`)

    if (isDev) {
      win.loadURL("http://localhost:3000")
      win.webContents.openDevTools()
    } else {
      win.loadFile(path.join(__dirname, "../dist/index.html"))
    }

    win.on("closed", () => {
      if (backendProcess) {
        console.log("[Electron] Killing backend process")
        backendProcess.kill()
        backendProcess = null
      }
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    console.error("[Electron] Failed to start:", message)
    dialog.showErrorBox("Aurora Design Backend Error", message)
    app.quit()
  }
}

app.whenReady().then(createWindow)

app.on("window-all-closed", () => {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
  if (process.platform !== "darwin") {
    app.quit()
  }
})

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})
