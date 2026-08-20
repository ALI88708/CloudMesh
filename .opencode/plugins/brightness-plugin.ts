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
  name: "brightness",
  description: "Control screen brightness",
  commands: [
    {
      name: "brightness",
      description: "Show current brightness level",
      handler: () => {
        const result = runCommand("powershell -Command \"(Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightness).CurrentBrightness\"")
        return result ? `Brightness: ${result}%` : "Could not get brightness (may not be a laptop/monitor that supports it)"
      },
    },
    {
      name: "brightness up",
      description: "Increase brightness by 10%",
      handler: () => {
        const script = `
$current = (Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightness).CurrentBrightness
$new = [math]::Min(100, $current + 10)
$monitor = Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightnessMethods
$monitor.WmiSetBrightness(1, $new)
Write-Output "Brightness set to $new%"`
        const tmpFile = `${process.env.TEMP}\\brightup_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not set brightness"
      },
    },
    {
      name: "brightness down",
      description: "Decrease brightness by 10%",
      handler: () => {
        const script = `
$current = (Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightness).CurrentBrightness
$new = [math]::Max(0, $current - 10)
$monitor = Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightnessMethods
$monitor.WmiSetBrightness(1, $new)
Write-Output "Brightness set to $new%"`
        const tmpFile = `${process.env.TEMP}\\brightdown_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not set brightness"
      },
    },
  ],
} satisfies Plugin
