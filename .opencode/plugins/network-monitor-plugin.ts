import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { platform } from "os"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 10000 }).trim()
  } catch (e) {
    return ""
  }
}

function getNetworkInterfaces(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`🌐 Network Interfaces`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const result = runCommand("ipconfig")
    lines.push(result)
  } else {
    const result = runCommand("ip addr show 2>/dev/null || ifconfig")
    lines.push(result)
  }

  return lines.join("\n")
}

function getActiveConnections(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`🔌 Active Connections`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const result = runCommand("netstat -ano | findstr ESTABLISHED")
    const connections = result.split("\n").filter(l => l.trim()).slice(0, 15)
    lines.push(`Active: ${connections.length}+ connections\n`)
    connections.forEach(conn => {
      const parts = conn.trim().split(/\s+/)
      if (parts.length >= 5) {
        lines.push(`${parts[0]} ${parts[1]} -> ${parts[2]} [${parts[4]}]`)
      }
    })
  } else {
    const result = runCommand("ss -tunap 2>/dev/null | grep ESTAB || netstat -tunap 2>/dev/null | grep ESTAB")
    const connections = result.split("\n").filter(l => l.trim()).slice(0, 15)
    lines.push(`Active: ${connections.length}+ connections\n`)
    connections.forEach(conn => {
      lines.push(`  ${conn.trim().substring(0, 80)}`)
    })
  }

  return lines.join("\n")
}

function getPing(host: string, count: number = 4): string {
  const os = platform()
  const flag = os === "win32" ? "-n" : "-c"
  return runCommand(`ping ${flag} ${count} ${host}`)
}

function getDNSServers(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`🔍 DNS Servers`)
  lines.push(`${"─".repeat(30)}`)

  if (os === "win32") {
    const result = runCommand("ipconfig /all | findstr DNS")
    lines.push(result)
  } else {
    const result = runCommand("cat /etc/resolv.conf | grep nameserver")
    lines.push(result)
  }

  return lines.join("\n")
}

function getPublicIP(): string {
  const result = runCommand("curl -s ifconfig.me 2>/dev/null || curl -s api.ipify.org 2>/dev/null")
  return result || "Could not get public IP"
}

function getListeningPorts(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`📡 Listening Ports`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const result = runCommand("netstat -ano | findstr LISTENING")
    const ports = result.split("\n").filter(l => l.trim()).slice(0, 15)
    lines.push(`Total: ${ports.length}+ listening\n`)
    ports.forEach(port => {
      const parts = port.trim().split(/\s+/)
      if (parts.length >= 4) {
        lines.push(`${parts[0]} ${parts[1]} [PID: ${parts[3]}]`)
      }
    })
  } else {
    const result = runCommand("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null")
    const ports = result.split("\n").filter(l => l.trim()).slice(0, 15)
    lines.push(`Total: ${ports.length}+ listening\n`)
    ports.forEach(port => {
      lines.push(`  ${port.trim().substring(0, 70)}`)
    })
  }

  return lines.join("\n")
}

function getWiFiInfo(): string {
  const os = platform()
  if (os === "win32") {
    return runCommand("netsh wlan show interfaces")
  } else {
    return runCommand("iwconfig 2>/dev/null || nmcli device wifi list 2>/dev/null")
  }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""

        // Network interfaces
        if (command.match(/^net(info|work|if)$/)) {
          console.log(`\n${getNetworkInterfaces()}\n`)
        }

        // Active connections
        if (command.match(/^net\s+conn|connections$/)) {
          console.log(`\n${getActiveConnections()}\n`)
        }

        // Ping
        const pingMatch = command.match(/^ping\s+(.+?)(?:\s+(\d+))?$/)
        if (pingMatch) {
          const count = pingMatch[2] ? parseInt(pingMatch[2]) : 4
          console.log(`\n📡 Pinging ${pingMatch[1]}:\n`)
          console.log(getPing(pingMatch[1], count))
          console.log("")
        }

        // DNS
        if (command.match(/^dns$/)) {
          console.log(`\n${getDNSServers()}\n`)
        }

        // Public IP
        if (command.match(/^myip|publicip$/)) {
          console.log(`\n🌍 Public IP: ${getPublicIP()}\n`)
        }

        // Listening ports
        if (command.match(/^ports$/)) {
          console.log(`\n${getListeningPorts()}\n`)
        }

        // WiFi info
        if (command.match(/^wifi$/)) {
          console.log(`\n📶 WiFi Info:\n${getWiFiInfo()}\n`)
        }
      }
    }
  }
}) satisfies Plugin