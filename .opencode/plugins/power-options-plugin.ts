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
  name: "power-options",
  description: "Power and battery management",
  commands: [
    {
      name: "power",
      description: "Show battery and power status",
      handler: () => {
        const script = `
$battery = Get-WmiObject -Class Win32_Battery -ErrorAction SilentlyContinue
if ($battery) {
    $charge = $battery.EstimatedChargeRemaining
    $status = if ($battery.BatteryStatus -eq 2) { "Charging" } else { "On Battery" }
    Write-Output "Battery: $charge% ($status)"
    Write-Output "Status: $($battery.Status)"
} else {
    Write-Output "No battery detected (desktop PC)"
}
$powerPlan = powercfg /getactivescheme
Write-Output "Active Plan: $powerPlan"`
        const tmpFile = `${process.env.TEMP}\\power_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not get power info"
      },
    },
    {
      name: "power plan",
      description: "Show available power plans",
      handler: () => {
        return runCommand("powercfg /list") || "No power plans found"
      },
    },
    {
      name: "power save",
      description: "Activate power saver plan",
      handler: () => {
        const result = runCommand('powercfg /setactive a1841308-3541-4fab-bc81-fa79b1fa7d2e')
        return "Power saver plan activated"
      },
    },
    {
      name: "power performance",
      description: "Activate high performance plan",
      handler: () => {
        const result = runCommand('powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c')
        return "High performance plan activated"
      },
    },
  ],
} satisfies Plugin
