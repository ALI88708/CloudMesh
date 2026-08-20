import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 30000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

export default {
  name: "git-quick",
  description: "Quick Git commands",
  commands: [
    {
      name: "gq status",
      description: "Quick git status",
      handler: () => {
        return runCommand("git status") || "Not a git repository or git not found"
      },
    },
    {
      name: "gq push",
      description: "Quick git push to origin current branch",
      handler: () => {
        const branch = runCommand("git rev-parse --abbrev-ref HEAD")
        if (!branch) return "Could not determine current branch"
        const result = runCommand(`git push origin ${branch}`)
        return result || `Pushed to origin/${branch}`
      },
    },
    {
      name: "gq pull",
      description: "Quick git pull from origin current branch",
      handler: () => {
        const branch = runCommand("git rev-parse --abbrev-ref HEAD")
        if (!branch) return "Could not determine current branch"
        const result = runCommand(`git pull origin ${branch}`)
        return result || `Pulled from origin/${branch}`
      },
    },
    {
      name: "gq log",
      description: "Show last 10 git log entries",
      handler: () => {
        return runCommand("git log --oneline -10") || "No commits found"
      },
    },
  ],
} satisfies Plugin
