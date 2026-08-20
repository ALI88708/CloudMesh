import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import * as fs from "fs"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

export default {
  name: "startup-manager",
  description: "Manage Windows startup programs",
  commands: [
    {
      name: "startup",
      description: "List startup programs",
      handler: () => {
        const script = `
$regPaths = @(
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
    "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"
)
foreach ($path in $regPaths) {
    if (Test-Path $path) {
        Write-Output "=== $path ==="
        Get-ItemProperty -Path $path | Format-List
    }
}`
        const tmpFile = `${process.env.TEMP}\\startup_list.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No startup programs found"
      },
    },
    {
      name: "startup add",
      description: "Add a program to startup (e.g. startup add C:\\path\\app.exe)",
      handler: (args: string) => {
        if (!args) return "Usage: startup add <path-to-executable>"
        const script = `
$path = "${args.replace(/\\/g, "\\\\")}"
$name = [System.IO.Path]::GetFileNameWithoutExtension($path)
Set-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run" -Name $name -Value "`"$path`""
Write-Output "Added '$name' to startup"`
        const tmpFile = `${process.env.TEMP}\\startup_add.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || `Added ${args} to startup`
      },
    },
    {
      name: "startup remove",
      description: "Remove a startup program by name (e.g. startup remove MyApp)",
      handler: (args: string) => {
        if (!args) return "Usage: startup remove <name>"
        const script = `
$name = "${args.replace(/"/g, '`"')}"
Remove-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run" -Name $name -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run" -Name $name -Force -ErrorAction SilentlyContinue
Write-Output "Removed '$name' from startup"`
        const tmpFile = `${process.env.TEMP}\\startup_remove.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || `Removed ${args} from startup`
      },
    },
  ],
} satisfies Plugin
