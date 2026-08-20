import type { Plugin } from "@opencode-ai/plugin"
import { execSync, writeFileSync, readFileSync, existsSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

const STATE_FILE = "C:\\Users\\mr_ali7685\\AppData\\Local\\Temp\\opencode-watch.json"
const PS1_FILE = "C:\\Users\\mr_ali7685\\AppData\\Local\\Temp\\opencode-watch.ps1"

interface WatchEntry {
  id: number
  path: string
  status: "running" | "stopped"
  startedAt: string
}

function getState(): WatchEntry[] {
  try {
    if (existsSync(STATE_FILE)) {
      return JSON.parse(readFileSync(STATE_FILE, "utf-8"))
    }
  } catch {}
  return []
}

function saveState(state: WatchEntry[]) {
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2))
}

export default {
  name: "file-watcher",
  description: "Watch directories for file changes",
  commands: [
    {
      name: "watch",
      description: "Watch a directory for changes. Usage: watch <dir> | watch stop | watch list",
      handler: (args: string) => {
        if (!args || args.trim() === "") {
          return "Usage: watch <directory>\n  watch stop - Stop the last watcher\n  watch list - List active watchers"
        }

        const state = getState()

        if (args.trim().toLowerCase() === "list") {
          if (state.length === 0) return "No active watchers."
          return state.map((w) => `[${w.id}] ${w.path} (${w.status}) - Started: ${w.startedAt}`).join("\n")
        }

        if (args.trim().toLowerCase() === "stop") {
          const running = state.filter((s) => s.status === "running")
          if (running.length === 0) return "No running watchers to stop."
          const last = running[running.length - 1]
          last.status = "stopped"
          saveState(state)
          return `Stopped watcher [${last.id}] for: ${last.path}`
        }

        const watchPath = args.trim()
        const id = state.length > 0 ? Math.max(...state.map((s) => s.id)) + 1 : 1
        const entry: WatchEntry = {
          id,
          path: watchPath,
          status: "running",
          startedAt: new Date().toISOString(),
        }
        state.push(entry)
        saveState(state)

        const ps1Content = `
$folder = "${watchPath.replace(/"/g, '""')}"
if (!(Test-Path $folder)) {
    Write-Host "Error: Path not found: $folder"
    exit 1
}
$filter = "*.*"
$fsw = New-Object System.IO.FileSystemWatcher
$fsw.Path = $folder
$fsw.Filter = $filter
$fsw.IncludeSubdirectories = $true
$fsw.EnableRaisingEvents = $true

$action = {
    $path = $Event.SourceEventArgs.FullPath
    $changeType = $Event.SourceEventArgs.ChangeType
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "$time - $changeType : $path"
}

Register-ObjectEvent $fsw "Created" -Action $action
Register-ObjectEvent $fsw "Changed" -Action $action
Register-ObjectEvent $fsw "Deleted" -Action $action
Register-ObjectEvent $fsw "Renamed" -Action $action

Write-Host "Watching: $folder"
Write-Host "Press Ctrl+C to stop..."
try { while ($true) { Start-Sleep -Seconds 1 } }
finally {
    Unregister-Event -SourceIdentifier "Created"
    Unregister-Event -SourceIdentifier "Changed"
    Unregister-Event -SourceIdentifier "Deleted"
    Unregister-Event -SourceIdentifier "Renamed"
    $fsw.Dispose()
    Write-Host "Watcher stopped."
}
`
        writeFileSync(PS1_FILE, ps1Content)
        const result = runCommand(`powershell -ExecutionPolicy Bypass -File "${PS1_FILE}"`)
        return `Watcher [${id}] started for: ${watchPath}\n${result || "Monitoring in background..."}` 
      },
    },
  ],
} satisfies Plugin
