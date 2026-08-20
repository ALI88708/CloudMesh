import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import * as fs from "fs"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

export default {
  name: "environment-vars",
  description: "Manage environment variables",
  commands: [
    {
      name: "env",
      description: "List all environment variables",
      handler: () => {
        const script = `
Get-ChildItem Env: | Sort-Object Name | Format-Table Name, Value -AutoSize`
        const tmpFile = `${process.env.TEMP}\\env_list.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No environment variables found"
      },
    },
    {
      name: "env get",
      description: "Get a specific environment variable (e.g. env get PATH)",
      handler: (args: string) => {
        if (!args) return "Usage: env get <name>"
        const result = runCommand(`powershell -Command "[System.Environment]::GetEnvironmentVariable('${args.replace(/'/g, "''")}')"` )
        return result ? `${args} = ${result}` : `Variable '${args}' not found`
      },
    },
    {
      name: "env set",
      description: "Set an environment variable (e.g. env set MY_VAR hello)",
      handler: (args: string) => {
        const parts = args.split(/\s+/)
        if (parts.length < 2) return "Usage: env set <name> <value>"
        const name = parts[0]
        const value = parts.slice(1).join(" ")
        runCommand(`powershell -Command "[System.Environment]::SetEnvironmentVariable('${name.replace(/'/g, "''")}', '${value.replace(/'/g, "''")}', 'User')"`)
        return `Set ${name} = ${value}`
      },
    },
    {
      name: "env delete",
      description: "Delete an environment variable (e.g. env delete MY_VAR)",
      handler: (args: string) => {
        if (!args) return "Usage: env delete <name>"
        runCommand(`powershell -Command "[System.Environment]::SetEnvironmentVariable('${args.replace(/'/g, "''")}', $null, 'User')"`)
        return `Deleted variable: ${args}`
      },
    },
  ],
} satisfies Plugin
