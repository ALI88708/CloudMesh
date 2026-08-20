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
  name: "process-killer",
  description: "Kill processes by name or PID",
  commands: [
    {
      name: "kill",
      description: "Kill a process by name (e.g. kill notepad)",
      handler: (args: string) => {
        if (!args) return "Usage: kill <process-name> or kill id <pid>"
        if (args.toLowerCase().startsWith("id ")) {
          const pid = args.substring(3).trim()
          if (isNaN(parseInt(pid))) return "Invalid PID"
          const result = runCommand(`taskkill /PID ${pid} /F`)
          return result || `Process ${pid} killed`
        }
        const result = runCommand(`taskkill /IM "${args}.exe" /F`)
        return result || `Process ${args} killed`
      },
    },
    {
      name: "kill id",
      description: "Kill a process by PID (e.g. kill id 1234)",
      handler: (args: string) => {
        if (!args) return "Usage: kill id <pid>"
        const pid = args.trim()
        if (isNaN(parseInt(pid))) return "Invalid PID"
        const result = runCommand(`taskkill /PID ${pid} /F`)
        return result || `Process ${pid} killed`
      },
    },
  ],
} satisfies Plugin
