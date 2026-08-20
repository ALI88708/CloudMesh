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
  name: "python-quick",
  description: "Quick Python commands",
  commands: [
    {
      name: "pq run",
      description: "Run a Python file (e.g. pq run main.py)",
      handler: (args: string) => {
        if (!args) return "Usage: pq run <file.py>"
        const result = runCommand(`python ${args}`)
        return result || `Executed ${args}`
      },
    },
    {
      name: "pq install",
      description: "Install a Python package (e.g. pq install requests)",
      handler: (args: string) => {
        if (!args) return "Usage: pq install <package>"
        const result = runCommand(`pip install ${args}`)
        return result || `Installed ${args}`
      },
    },
    {
      name: "pq list",
      description: "List installed Python packages",
      handler: () => {
        return runCommand("pip list") || "No packages found"
      },
    },
    {
      name: "pq venv",
      description: "Create a Python virtual environment in ./venv",
      handler: () => {
        const result = runCommand("python -m venv venv")
        return result !== "" ? `Error: ${result}` : "Virtual environment created at ./venv\nActivate with: .\\venv\\Scripts\\Activate"
      },
    },
  ],
} satisfies Plugin
