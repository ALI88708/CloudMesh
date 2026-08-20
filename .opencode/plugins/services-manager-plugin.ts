import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { platform } from "os"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e) {
    return ""
  }
}

function listServices(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`🔧 System Services`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const result = runCommand('powershell -Command "Get-Service | Where-Object {$_.Status -eq \'Running\'} | Select-Object -First 20 Name, Status, DisplayName | Format-Table -AutoSize"')
    lines.push("Running Services:\n")
    lines.push(result)
  } else {
    const result = runCommand("systemctl list-units --type=service --state=running --no-pager | head -25")
    lines.push(result)
  }

  return lines.join("\n")
}

function listStoppedServices(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`⏸️ Stopped Services`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const result = runCommand('powershell -Command "Get-Service | Where-Object {$_.Status -eq \'Stopped\'} | Select-Object -First 20 Name, DisplayName | Format-Table -AutoSize"')
    lines.push("Stopped Services:\n")
    lines.push(result)
  } else {
    const result = runCommand("systemctl list-units --type=service --state=inactive --no-pager | head -25")
    lines.push(result)
  }

  return lines.join("\n")
}

function getServiceInfo(name: string): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`📋 Service: ${name}`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const result = runCommand(`powershell -Command "Get-Service '${name}' | Format-List *"`)
    lines.push(result)
  } else {
    const result = runCommand(`systemctl status ${name} --no-pager`)
    lines.push(result)
  }

  return lines.join("\n")
}

function stopService(name: string): string {
  const os = platform()
  if (os === "win32") {
    return runCommand(`powershell -Command "Stop-Service '${name}' -Force"`) || `Stopped service: ${name}`
  } else {
    return runCommand(`systemctl stop ${name}`) || `Stopped service: ${name}`
  }
}

function startService(name: string): string {
  const os = platform()
  if (os === "win32") {
    return runCommand(`powershell -Command "Start-Service '${name}'"`) || `Started service: ${name}`
  } else {
    return runCommand(`systemctl start ${name}`) || `Started service: ${name}`
  }
}

function restartService(name: string): string {
  const os = platform()
  if (os === "win32") {
    return runCommand(`powershell -Command "Restart-Service '${name}' -Force"`) || `Restarted service: ${name}`
  } else {
    return runCommand(`systemctl restart ${name}`) || `Restarted service: ${name}`
  }
}

function getSystemBootInfo(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`⏪ Boot Info`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const result = runCommand("systeminfo | findstr Boot")
    lines.push(result)
  } else {
    const result = runCommand("uptime -s && uptime")
    lines.push(result)
  }

  return lines.join("\n")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""

        // List running services
        if (command.match(/^services|svc$/)) {
          console.log(`\n${listServices()}\n`)
        }

        // List stopped services
        if (command.match(/^services\s+stopped|svc\s+stopped$/)) {
          console.log(`\n${listStoppedServices()}\n`)
        }

        // Service info
        const svcInfoMatch = command.match(/^svc\s+info\s+(.+)$/)
        if (svcInfoMatch) {
          console.log(`\n${getServiceInfo(svcInfoMatch[1])}\n`)
        }

        // Stop service
        const svcStopMatch = command.match(/^svc\s+stop\s+(.+)$/)
        if (svcStopMatch) {
          console.log(`\n${stopService(svcStopMatch[1])}\n`)
        }

        // Start service
        const svcStartMatch = command.match(/^svc\s+start\s+(.+)$/)
        if (svcStartMatch) {
          console.log(`\n${startService(svcStartMatch[1])}\n`)
        }

        // Restart service
        const svcRestartMatch = command.match(/^svc\s+restart\s+(.+)$/)
        if (svcRestartMatch) {
          console.log(`\n${restartService(svcRestartMatch[1])}\n`)
        }

        // Boot info
        if (command.match(/^boot|uptime\s+info$/)) {
          console.log(`\n${getSystemBootInfo()}\n`)
        }
      }
    }
  }
}) satisfies Plugin