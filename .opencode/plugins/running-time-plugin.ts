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
  name: "running-time",
  description: "Show system and process uptime",
  commands: [
    {
      name: "uptime",
      description: "Show system uptime",
      handler: () => {
        const script = `
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$uptime = (Get-Date) - $boot
$days = $uptime.Days
$hours = $uptime.Hours
$mins = $uptime.Minutes
$secs = $uptime.Seconds
Write-Output "System Uptime: ${days}d ${hours}h ${mins}m ${secs}s"
Write-Output "Last Boot: $boot"`
        const tmpFile = `${process.env.TEMP}\\uptime_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not get uptime"
      },
    },
    {
      name: "uptime process",
      description: "Show uptime for a specific process (e.g. uptime chrome)",
      handler: (args: string) => {
        if (!args) return "Usage: uptime <process-name>"
        const result = runCommand(`powershell -Command "Get-Process -Name '${args.replace(/'/g, "''")}' -ErrorAction SilentlyContinue | Select-Object ProcessName, Id, StartTime | Format-Table -AutoSize"`)
        if (!result) return `Process '${args}' not found`
        return result
      },
    },
  ],
} satisfies Plugin
