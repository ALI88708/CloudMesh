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
  name: "ip-info",
  description: "Show IP address information",
  commands: [
    {
      name: "ip",
      description: "Show local IP addresses",
      handler: () => {
        const result = runCommand('powershell -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne \'127.0.0.1\'} | Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize"')
        return result || "No IP addresses found"
      },
    },
    {
      name: "ip public",
      description: "Show public IP address",
      handler: () => {
        const result = runCommand('curl -s "https://api.ipify.org"')
        return result ? `Public IP: ${result}` : "Could not get public IP"
      },
    },
    {
      name: "ip geo",
      description: "Show geolocation for public IP",
      handler: () => {
        const result = runCommand('curl -s "https://ipinfo.io"')
        if (result) {
          try {
            const info = JSON.parse(result)
            return [
              `IP: ${info.ip}`,
              `City: ${info.city}`,
              `Region: ${info.region}`,
              `Country: ${info.country}`,
              `Org: ${info.org}`,
              `Location: ${info.loc}`,
            ].join("\n")
          } catch {
            return result
          }
        }
        return "Could not get geolocation data"
      },
    },
  ],
} satisfies Plugin
