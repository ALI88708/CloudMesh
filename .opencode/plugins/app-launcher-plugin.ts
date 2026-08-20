import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

export default {
  name: "app-launcher",
  description: "Launch applications and open URLs/folders",
  commands: [
    {
      name: "open",
      description: "Open an app, URL, or folder. Usage: open <app> | open url <url> | open folder <path> | apps list",
      handler: (args: string) => {
        if (!args || args.trim() === "") {
          return `Usage:
  open <app>        - Launch app (notepad, calc, explorer, msedge, chrome, firefox, code, etc.)
  open url <url>    - Open URL in default browser
  open folder <path> - Open folder in Explorer
  apps list          - List installed apps from Start Menu`
        }

        const trimmed = args.trim()

        if (trimmed.toLowerCase() === "apps list") {
          const ps1 = `
$startMenu = [Environment]::GetFolderPath("StartMenu") + "\\Programs"
$startMenuCommon = [Environment]::GetFolderPath("CommonStartMenu") + "\\Programs"
$apps = @()
if (Test-Path $startMenu) {
    $apps += Get-ChildItem -Path $startMenu -Recurse -Filter "*.lnk" | Select-Object -ExpandProperty BaseName
}
if (Test-Path $startMenuCommon) {
    $apps += Get-ChildItem -Path $startMenuCommon -Recurse -Filter "*.lnk" | Select-Object -ExpandProperty BaseName
}
$apps | Sort-Object -Unique | Select-Object -First 50
`
          const result = runCommand(`powershell -Command "${ps1.replace(/"/g, '\\"').replace(/\n/g, " ")}"`)
          return result || "No apps found in Start Menu."
        }

        if (trimmed.toLowerCase().startsWith("url ")) {
          const url = trimmed.slice(4).trim()
          if (!url) return "Usage: open url <url>"
          runCommand(`start "" "${url}"`)
          return `Opening URL: ${url}`
        }

        if (trimmed.toLowerCase().startsWith("folder ")) {
          const folderPath = trimmed.slice(7).trim()
          if (!folderPath) return "Usage: open folder <path>"
          runCommand(`explorer "${folderPath}"`)
          return `Opening folder: ${folderPath}`
        }

        const appMap: Record<string, string> = {
          notepad: "notepad.exe",
          calc: "calc.exe",
          calculator: "calc.exe",
          explorer: "explorer.exe",
          msedge: "msedge.exe",
          edge: "msedge.exe",
          chrome: "chrome.exe",
          firefox: "firefox.exe",
          code: "code.exe",
          vscode: "code.exe",
          cmd: "cmd.exe",
          powershell: "powershell.exe",
          taskmgr: "taskmgr.exe",
          control: "control.exe",
          paint: "mspaint.exe",
          mspaint: "mspaint.exe",
          wordpad: "write.exe",
          regedit: "regedit.exe",
          cleanmgr: "cleanmgr.exe",
          snippingtool: "SnippingTool.exe",
        }

        const appName = trimmed.toLowerCase()
        const appPath = appMap[appName]
        if (appPath) {
          runCommand(`start "" "${appPath}"`)
          return `Launching: ${appName}`
        }

        runCommand(`start "" "${trimmed}"`)
        return `Launching: ${trimmed}`
      },
    },
  ],
} satisfies Plugin
