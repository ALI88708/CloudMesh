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
  name: "hostname",
  description: "Show or set computer hostname",
  commands: [
    {
      name: "hostname",
      description: "Show the computer name",
      handler: () => {
        return runCommand("hostname") || "Could not get hostname"
      },
    },
    {
      name: "hostname set",
      description: "Set a new computer name (requires admin, e.g. hostname set MyPC)",
      handler: (args: string) => {
        if (!args) return "Usage: hostname set <new-name>\nNote: Requires administrator privileges and a restart."
        const result = runCommand(`powershell -Command "Rename-Computer -NewName '${args.replace(/'/g, "''")}' -Force -PassThru | Select-Object Name, Domain"`)
        return result ? `Computer renamed to: ${args}\nRestart required for changes to take effect.` : "Failed to rename computer (try running as admin)"
      },
    },
  ],
} satisfies Plugin
