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
  name: "event-log",
  description: "View Windows event logs",
  commands: [
    {
      name: "events",
      description: "Show recent error events from Windows Event Log",
      handler: (args: string) => {
        const count = parseInt(args) || 20
        const script = `
$events = Get-EventLog -LogName System -EntryType Error -Newest ${count} | Select-Object TimeGenerated, Source, Message
foreach ($e in $events) {
    Write-Output "---"
    Write-Output "Time: $($e.TimeGenerated)"
    Write-Output "Source: $($e.Source)"
    Write-Output "Message: $($e.Message.Substring(0, [math]::Min(200, $e.Message.Length)))"
}`
        const tmpFile = `${process.env.TEMP}\\events_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No recent error events found"
      },
    },
    {
      name: "events warnings",
      description: "Show recent warning events",
      handler: () => {
        const script = `
$events = Get-EventLog -LogName System -EntryType Warning -Newest 20 | Select-Object TimeGenerated, Source, Message
foreach ($e in $events) {
    Write-Output "---"
    Write-Output "Time: $($e.TimeGenerated)"
    Write-Output "Source: $($e.Source)"
    Write-Output "Message: $($e.Message.Substring(0, [math]::Min(200, $e.Message.Length)))"
}`
        const tmpFile = `${process.env.TEMP}\\events_warn.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No recent warning events found"
      },
    },
  ],
} satisfies Plugin
