import type { Plugin } from "@opencode-ai/plugin"
import { execSync, writeFileSync, readFileSync, existsSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

const STATE_FILE = "C:\\Users\\mr_ali7685\\AppData\\Local\\Temp\\opencode-clipwatch.json"
const PS1_FILE = "C:\\Users\\mr_ali7685\\AppData\\Local\\Temp\\opencode-clipwatch.ps1"

interface ClipboardEntry {
  content: string
  timestamp: string
}

interface ClipWatchState {
  status: "running" | "stopped"
  entries: ClipboardEntry[]
}

function getState(): ClipWatchState {
  try {
    if (existsSync(STATE_FILE)) {
      return JSON.parse(readFileSync(STATE_FILE, "utf-8"))
    }
  } catch {}
  return { status: "stopped", entries: [] }
}

function saveState(state: ClipWatchState) {
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2))
}

export default {
  name: "clipboard-watcher",
  description: "Monitor clipboard changes and keep history",
  commands: [
    {
      name: "clipwatch",
      description: "Watch clipboard. Usage: clipwatch | clipwatch stop | clipwatch list",
      handler: (args: string) => {
        const state = getState()

        if (!args || args.trim() === "") {
          if (state.status === "running") {
            return "Clipboard watcher is already running.\nUse 'clipwatch list' to see history or 'clipwatch stop' to stop."
          }

          const ps1Content = `
$stateFile = "${STATE_FILE.replace(/\\/g, "\\\\")}"
Add-Type -AssemblyName System.Windows.Forms
$lastText = [System.Windows.Forms.Clipboard]::GetText()
$entries = @()
if (Test-Path $stateFile) {
    $saved = Get-Content $stateFile -Raw | ConvertFrom-Json
    if ($saved.entries) { $entries = @($saved.entries) }
}
Write-Host "Clipboard watcher started..."
Write-Host "Press Ctrl+C to stop."
try {
    while ($true) {
        Start-Sleep -Seconds 2
        $currentText = [System.Windows.Forms.Clipboard]::GetText()
        if ($currentText -and $currentText -ne $lastText -and $currentText.Trim() -ne "") {
            $lastText = $currentText
            $entry = @{
                content = $currentText.Substring(0, [Math]::Min($currentText.Length, 500))
                timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
            }
            $entries = @($entry) + $entries
            if ($entries.Count -gt 10) { $entries = $entries[0..9] }
            $state = @{ status = "running"; entries = $entries }
            $state | ConvertTo-Json -Depth 5 | Set-Content $stateFile
            Write-Host "[$($entry.timestamp)] Captured: $($currentText.Substring(0, [Math]::Min($currentText.Length, 80)))"
        }
    }
} finally {
    $state = @{ status = "stopped"; entries = $entries }
    $state | ConvertTo-Json -Depth 5 | Set-Content $stateFile
    Write-Host "Clipboard watcher stopped."
}
`
          writeFileSync(PS1_FILE, ps1Content)
          state.status = "running"
          saveState(state)
          runCommand(`powershell -ExecutionPolicy Bypass -File "${PS1_FILE}"`)
          return "Clipboard watcher started. Monitoring for changes..."
        }

        const action = args.trim().toLowerCase()

        if (action === "stop") {
          state.status = "stopped"
          saveState(state)
          return "Clipboard watcher stopped."
        }

        if (action === "list") {
          if (state.entries.length === 0) return "No clipboard entries captured yet."
          return state.entries
            .map((e, i) => `[${i + 1}] (${e.timestamp}) ${e.content.substring(0, 100)}`)
            .join("\n")
        }

        return "Usage: clipwatch | clipwatch stop | clipwatch list"
      },
    },
  ],
} satisfies Plugin
