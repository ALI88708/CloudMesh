import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

let stopwatchInterval: ReturnType<typeof setInterval> | null = null
let stopwatchSeconds = 0

export default {
  name: "timer",
  description: "Timer and stopwatch utilities",
  commands: [
    {
      name: "timer",
      description: "Start a countdown timer (e.g. timer 30 for 30 seconds)",
      handler: (args: string) => {
        const seconds = parseInt(args)
        if (isNaN(seconds) || seconds <= 0) return "Usage: timer <seconds>"
        if (seconds > 3600) return "Maximum timer is 3600 seconds (1 hour)"

        const script = `
Add-Type -AssemblyName System.Windows.Forms
$seconds = ${seconds}
for ($i = $seconds; $i -ge 0; $i--) {
    $min = [math]::Floor($i / 60)
    $sec = $i % 60
    Write-Host "`r$([string]::Format('{0:D2}:{1:D2}', $min, $sec))" -NoNewline
    if ($i -gt 0) { Start-Sleep -Seconds 1 }
}
Write-Host ""
[System.Media.SystemSounds]::Asterisk.Play()
Write-Output "Timer finished!"`
        const tmpFile = `${process.env.TEMP}\\timer_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`)
        return `Timer started for ${seconds} seconds`
      },
    },
    {
      name: "stopwatch",
      description: "Start/stop a stopwatch (toggle)",
      handler: () => {
        if (stopwatchInterval) {
          clearInterval(stopwatchInterval)
          stopwatchInterval = null
          const mins = Math.floor(stopwatchSeconds / 60)
          const secs = stopwatchSeconds % 60
          const result = `Stopwatch stopped: ${mins}m ${secs}s (${stopwatchSeconds}s total)`
          stopwatchSeconds = 0
          return result
        }

        stopwatchSeconds = 0
        stopwatchInterval = setInterval(() => {
          stopwatchSeconds++
          const mins = Math.floor(stopwatchSeconds / 60)
          const secs = stopwatchSeconds % 60
          process.stdout.write(`\rStopwatch: ${mins}m ${secs}s`)
        }, 1000)
        return "Stopwatch started. Run 'stopwatch' again to stop."
      },
    },
  ],
} satisfies Plugin
