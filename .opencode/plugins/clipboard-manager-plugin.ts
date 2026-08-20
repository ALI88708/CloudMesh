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
  name: "clipboard-manager",
  description: "Manage Windows clipboard contents",
  commands: [
    {
      name: "clip",
      description: "Show current clipboard contents",
      handler: () => {
        const result = runCommand("powershell -Command \"Get-Clipboard\"")
        return result || "(clipboard is empty)"
      },
    },
    {
      name: "clip set",
      description: "Set clipboard to specified text",
      handler: (args: string) => {
        if (!args) return "Usage: clip set <text>"
        runCommand(`powershell -Command "Set-Clipboard -Value '${args.replace(/'/g, "''")}'"`)
        return `Clipboard set to: ${args}`
      },
    },
    {
      name: "clip clear",
      description: "Clear the clipboard",
      handler: () => {
        runCommand("powershell -Command \"Set-Clipboard -Value $null\"")
        return "Clipboard cleared"
      },
    },
  ],
} satisfies Plugin
