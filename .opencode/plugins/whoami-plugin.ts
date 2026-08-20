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
  name: "whoami",
  description: "Show current user information",
  commands: [
    {
      name: "whoami",
      description: "Show current user info",
      handler: () => {
        const result = runCommand("whoami /all")
        return result || "Could not get user info"
      },
    },
    {
      name: "whoami groups",
      description: "Show current user's group memberships",
      handler: () => {
        const result = runCommand("whoami /groups")
        return result || "Could not get group info"
      },
    },
  ],
} satisfies Plugin
