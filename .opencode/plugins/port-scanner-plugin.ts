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
  name: "port-scanner",
  description: "Scan ports on a host",
  commands: [
    {
      name: "scan",
      description: "Scan common ports on a host (e.g. scan 192.168.1.1)",
      handler: (args: string) => {
        if (!args) return "Usage: scan <host> or scan <host> <port>"
        const parts = args.split(/\s+/)
        if (parts.length === 2) {
          const host = parts[0]
          const port = parts[1]
          const result = runCommand(`powershell -Command "Test-NetConnection -ComputerName '${host.replace(/'/g, "''")}' -Port ${port} -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded | Format-List"`)
          return result || `Could not scan ${host}:${port}`
        }

        const host = parts[0]
        const commonPorts = [21, 22, 25, 53, 80, 110, 143, 443, 993, 995, 3306, 3389, 5432, 8080, 8443]
        const results: string[] = [`Scanning ${host}...`]
        for (const port of commonPorts) {
          const result = runCommand(`powershell -Command "Test-NetConnection -ComputerName '${host.replace(/'/g, "''")}' -Port ${port} -WarningAction SilentlyContinue | Select-Object -ExpandProperty TcpTestSucceeded"`)
          if (result === "True") results.push(`  Port ${port}: OPEN`)
        }
        if (results.length === 1) results.push("  No open ports found")
        return results.join("\n")
      },
    },
    {
      name: "scan port",
      description: "Scan a specific port (e.g. scan 192.168.1.1 80)",
      handler: (args: string) => {
        const parts = args.split(/\s+/)
        if (parts.length < 2) return "Usage: scan <host> <port>"
        const host = parts[0]
        const port = parts[1]
        const result = runCommand(`powershell -Command "Test-NetConnection -ComputerName '${host.replace(/'/g, "''")}' -Port ${port} -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded | Format-List"`)
        return result || `Could not scan ${host}:${port}`
      },
    },
  ],
} satisfies Plugin
