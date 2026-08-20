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
  name: "zip-manager",
  description: "Create and extract ZIP archives",
  commands: [
    {
      name: "zip",
      description: "Create a zip archive (e.g. zip C:\\folder\\archive.zip C:\\folder\\files)",
      handler: (args: string) => {
        const parts = args.split(/\s+/)
        if (parts.length < 2) return "Usage: zip <destination.zip> <source-path>"
        const dest = parts[0]
        const source = parts.slice(1).join(" ")
        const script = `
if (Test-Path "${dest.replace(/\\/g, "\\\\")}") { Remove-Item "${dest.replace(/\\/g, "\\\\")}" -Force }
Compress-Archive -Path "${source.replace(/\\/g, "\\\\")}" -DestinationPath "${dest.replace(/\\/g, "\\\\")}" -Force
Write-Output "Created: ${dest}"`
        const tmpFile = `${process.env.TEMP}\\zip_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || `Created ${dest}`
      },
    },
    {
      name: "unzip",
      description: "Extract a zip archive (e.g. unzip C:\\archive.zip C:\\destination)",
      handler: (args: string) => {
        const parts = args.split(/\s+/)
        if (parts.length < 2) return "Usage: unzip <archive.zip> <destination-path>"
        const archive = parts[0]
        const dest = parts.slice(1).join(" ")
        const script = `
if (!(Test-Path "${dest.replace(/\\/g, "\\\\")}")) { New-Item -ItemType Directory -Path "${dest.replace(/\\/g, "\\\\")}" -Force | Out-Null }
Expand-Archive -Path "${archive.replace(/\\/g, "\\\\")}" -DestinationPath "${dest.replace(/\\/g, "\\\\")}" -Force
Write-Output "Extracted to: ${dest}"`
        const tmpFile = `${process.env.TEMP}\\unzip_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || `Extracted to ${dest}`
      },
    },
  ],
} satisfies Plugin
