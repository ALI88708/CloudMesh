import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || ""
  }
}

function listOpenWindows(): string {
  const powershell = `powershell -Command "Get-Process | Where-Object {\\$_.MainWindowTitle -ne ''} | Select-Object ProcessName, Id, MainWindowTitle, @{Name='Memory(MB)';Expression={[math]::Round(\\$_.WorkingSet64/1MB,1)}} | Format-Table -AutoSize | Out-String -Width 200"`

  const result = runCommand(powershell)
  if (!result) return "No windows found"

  const lines: string[] = []
  lines.push("Open Windows")
  lines.push("─".repeat(60))

  const processLines = result.split("\n").filter(l => l.trim() && !l.includes("---") && !l.includes("ProcessName"))
  lines.push(`Total: ${processLines.length} windows`)
  lines.push("")

  processLines.forEach(line => {
    lines.push(line.trimEnd())
  })

  return lines.join("\n")
}

function getWindowList(): string {
  const powershell = `powershell -Command "Get-Process | Where-Object {\\$_.MainWindowTitle -ne ''} | Select-Object ProcessName, MainWindowTitle | ForEach-Object {\\$_.ProcessName + ': ' + \\$_.MainWindowTitle}"`

  const result = runCommand(powershell)
  if (!result) return "No windows found"

  const lines: string[] = []
  lines.push("Window Titles")
  lines.push("─".repeat(60))

  const entries = result.split("\n").filter(l => l.trim())
  lines.push(`Found: ${entries.length} windows`)
  lines.push("")

  entries.forEach(entry => {
    lines.push(entry.trimEnd())
  })

  return lines.join("\n")
}

export default {
  name: "window-manager",
  description: "View and manage open windows on the system",
  commands: [
    {
      name: "windows",
      description: "Show all open windows with details",
      handler: () => listOpenWindows(),
    },
    {
      name: "windows titles",
      description: "Show window titles only",
      handler: () => getWindowList(),
    },
  ],
} satisfies Plugin
