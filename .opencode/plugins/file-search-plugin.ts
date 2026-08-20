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
  name: "file-search",
  description: "Search for files and file contents",
  commands: [
    {
      name: "search",
      description: "Find files by name pattern (e.g. search *.ts, search readme)",
      handler: (args: string) => {
        if (!args) return "Usage: search <pattern> or search content <text>"
        if (args.toLowerCase().startsWith("content ")) {
          const text = args.substring(8).trim()
          if (!text) return "Usage: search content <text>"
          const result = runCommand(`powershell -Command "Get-ChildItem -Recurse -File | Select-String -Pattern '${text.replace(/'/g, "''")}' | Select-Object Path, LineNumber, Line | Format-Table -AutoSize -Wrap"`)
          return result || `No files containing '${text}' found`
        }
        const result = runCommand(`powershell -Command "Get-ChildItem -Recurse -Filter '${args.replace(/'/g, "''")}' -File | Select-Object FullName, Length, LastWriteTime | Format-Table -AutoSize"`)
        return result || `No files matching '${args}' found`
      },
    },
    {
      name: "search content",
      description: "Search file contents for text (e.g. search content 'TODO')",
      handler: (args: string) => {
        if (!args) return "Usage: search content <text>"
        const result = runCommand(`powershell -Command "Get-ChildItem -Recurse -File | Select-String -Pattern '${args.replace(/'/g, "''")}' | Select-Object Path, LineNumber, Line | Format-Table -AutoSize -Wrap"`)
        return result || `No files containing '${args}' found`
      },
    },
  ],
} satisfies Plugin
