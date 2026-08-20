import type { Plugin } from "@opencode-ai/plugin"
import { execSync, writeFileSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

const PS1_FILE = "C:\\Users\\mr_ali7685\\AppData\\Local\\Temp\\opencode-notify.ps1"

export default {
  name: "notification",
  description: "Send Windows desktop notifications",
  commands: [
    {
      name: "notify",
      description: "Send a Windows toast notification. Usage: notify <title> <message>",
      handler: (args: string) => {
        if (!args || args.trim() === "") {
          return "Usage: notify <title> <message>\nExample: notify 'Build Complete' 'Your project compiled successfully'"
        }

        const parts = args.trim().split(/\s+/)
        const title = parts[0] || "Notification"
        const message = parts.slice(1).join(" ") || ""

        const ps1Content = `
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.BalloonTipTitle = "${title.replace(/"/g, '""')}"
$notify.BalloonTipText = "${message.replace(/"/g, '""')}"
$notify.BalloonTipIcon = "Info"
$notify.ShowBalloonTip(5000)
Start-Sleep -Seconds 3
$notify.Dispose()
`
        writeFileSync(PS1_FILE, ps1Content)
        const result = runCommand(`powershell -ExecutionPolicy Bypass -File "${PS1_FILE}"`)

        if (result && result.includes("Error")) {
          const fallback = runCommand(
            `powershell -Command "msg * '${title.replace(/'/g, "''")} : ${message.replace(/'/g, "''")}'"`
          )
          return `Notification sent (fallback): ${title} - ${message}`
        }

        return `Notification sent: ${title} - ${message}`
      },
    },
  ],
} satisfies Plugin
