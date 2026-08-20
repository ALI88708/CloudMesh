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
  name: "scheduled-tasks",
  description: "View and manage scheduled tasks",
  commands: [
    {
      name: "tasks",
      description: "List scheduled tasks",
      handler: () => {
        const result = runCommand('schtasks /query /fo TABLE /nh')
        return result || "No scheduled tasks found"
      },
    },
    {
      name: "task info",
      description: "Show info for a specific task (e.g. task info \\Microsoft\\Windows\\Defrag)",
      handler: (args: string) => {
        if (!args) return "Usage: task info <task-name>"
        const result = runCommand(`schtasks /query /tn "${args}" /fo LIST /v`)
        return result || `Task not found: ${args}`
      },
    },
    {
      name: "task run",
      description: "Run a scheduled task immediately (e.g. task run \\MyTask)",
      handler: (args: string) => {
        if (!args) return "Usage: task run <task-name>"
        const result = runCommand(`schtasks /run /tn "${args}"`)
        return result || `Task '${args}' started`
      },
    },
  ],
} satisfies Plugin
