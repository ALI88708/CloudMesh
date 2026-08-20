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
  name: "file-hash",
  description: "Calculate file hashes (MD5, SHA256)",
  commands: [
    {
      name: "hash",
      description: "Calculate MD5 and SHA256 hashes for a file (e.g. hash C:\\file.txt)",
      handler: (args: string) => {
        if (!args) return "Usage: hash <file> [md5|sha256]"
        const parts = args.split(/\s+/)
        const file = parts[0]
        const algo = parts[1]?.toLowerCase()

        if (algo === "md5") {
          const result = runCommand(`powershell -Command "(Get-FileHash -Path '${file.replace(/'/g, "''")}' -Algorithm MD5).Hash"`)
          return result ? `MD5: ${result}` : `Could not hash file: ${file}`
        }
        if (algo === "sha256") {
          const result = runCommand(`powershell -Command "(Get-FileHash -Path '${file.replace(/'/g, "''")}' -Algorithm SHA256).Hash"`)
          return result ? `SHA256: ${result}` : `Could not hash file: ${file}`
        }

        const md5 = runCommand(`powershell -Command "(Get-FileHash -Path '${file.replace(/'/g, "''")}' -Algorithm MD5).Hash"`)
        const sha256 = runCommand(`powershell -Command "(Get-FileHash -Path '${file.replace(/'/g, "''")}' -Algorithm SHA256).Hash"`)
        if (!md5 && !sha256) return `Could not hash file: ${file}`
        return [
          `File: ${file}`,
          md5 ? `MD5:    ${md5}` : "",
          sha256 ? `SHA256: ${sha256}` : "",
        ].filter(Boolean).join("\n")
      },
    },
  ],
} satisfies Plugin
