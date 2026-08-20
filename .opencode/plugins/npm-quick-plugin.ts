import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 60000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

export default {
  name: "npm-quick",
  description: "Quick npm commands",
  commands: [
    {
      name: "nq install",
      description: "Run npm install",
      handler: () => {
        const result = runCommand("npm install")
        return result || "npm install completed"
      },
    },
    {
      name: "nq run",
      description: "Run an npm script (e.g. nq run dev)",
      handler: (args: string) => {
        if (!args) return "Usage: nq run <script-name>"
        const result = runCommand(`npm run ${args}`)
        return result || `Script '${args}' executed`
      },
    },
    {
      name: "nq list",
      description: "List installed npm packages",
      handler: () => {
        return runCommand("npm list --depth=0") || "No packages found or not in a Node.js project"
      },
    },
    {
      name: "nq outdated",
      description: "Show outdated npm packages",
      handler: () => {
        return runCommand("npm outdated") || "All packages are up to date"
      },
    },
  ],
} satisfies Plugin
