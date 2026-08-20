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
  name: "dns-tools",
  description: "DNS lookup and management tools",
  commands: [
    {
      name: "dns",
      description: "DNS lookup for a domain (e.g. dns example.com)",
      handler: (args: string) => {
        if (!args) return "Usage: dns <domain>"
        const result = runCommand(`nslookup ${args}`)
        return result || `No DNS records found for ${args}`
      },
    },
    {
      name: "dns change",
      description: "Change DNS server for a network adapter (e.g. dns change Wi-Fi 8.8.8.8)",
      handler: (args: string) => {
        const parts = args.split(/\s+/)
        if (parts.length < 2) return "Usage: dns change <adapter-name> <dns-server>\nExample: dns change Wi-Fi 8.8.8.8"
        const adapter = parts[0]
        const server = parts[1]
        const result = runCommand(`netsh interface ip set dns "${adapter}" static ${server}`)
        return result !== "" ? `Error: ${result}` : `DNS server changed to ${server} for ${adapter}`
      },
    },
  ],
} satisfies Plugin
