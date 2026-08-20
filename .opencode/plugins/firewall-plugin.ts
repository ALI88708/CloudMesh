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
  name: "firewall",
  description: "Manage Windows Firewall settings",
  commands: [
    {
      name: "firewall",
      description: "Show firewall status",
      handler: () => {
        const result = runCommand('netsh advfirewall show allprofiles state')
        return result || "Could not get firewall status"
      },
    },
    {
      name: "firewall block",
      description: "Block an application through the firewall (e.g. firewall block MyApp.exe)",
      handler: (args: string) => {
        if (!args) return "Usage: firewall block <app.exe>"
        const result = runCommand(`netsh advfirewall firewall add rule name="Block ${args}" dir=out action=block program="${args}" enable=yes`)
        return result !== "" ? `Error: ${result}` : `Blocked ${args} through firewall`
      },
    },
    {
      name: "firewall allow",
      description: "Allow an application through the firewall (e.g. firewall allow MyApp.exe)",
      handler: (args: string) => {
        if (!args) return "Usage: firewall allow <app.exe>"
        const result = runCommand(`netsh advfirewall firewall add rule name="Allow ${args}" dir=out action=allow program="${args}" enable=yes`)
        return result !== "" ? `Error: ${result}` : `Allowed ${args} through firewall`
      },
    },
  ],
} satisfies Plugin
