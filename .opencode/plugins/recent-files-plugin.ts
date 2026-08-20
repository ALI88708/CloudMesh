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
  name: "recent-files",
  description: "Show recently accessed files",
  commands: [
    {
      name: "recent",
      description: "Show recently modified files in the current directory",
      handler: () => {
        const script = `
Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 20 |
    ForEach-Object {
        "$($_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))  $($_.FullName)"
    }`
        const tmpFile = `${process.env.TEMP}\\recent_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No recent files found"
      },
    },
    {
      name: "recent downloads",
      description: "Show recent files in Downloads folder",
      handler: () => {
        const script = `
$dlPath = [Environment]::GetFolderPath('UserProfile') + '\\Downloads'
if (Test-Path $dlPath) {
    Get-ChildItem -Path $dlPath -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 20 |
        ForEach-Object {
            "$($_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))  $($_.Name)  ($([math]::Round($_.Length/1KB, 1)) KB)"
        }
} else {
    Write-Output "Downloads folder not found"
}`
        const tmpFile = `${process.env.TEMP}\\recent_dl.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No recent downloads found"
      },
    },
    {
      name: "recent docs",
      description: "Show recent files in Documents folder",
      handler: () => {
        const script = `
$docsPath = [Environment]::GetFolderPath('UserProfile') + '\\Documents'
if (Test-Path $docsPath) {
    Get-ChildItem -Path $docsPath -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 20 |
        ForEach-Object {
            "$($_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))  $($_.Name)  ($([math]::Round($_.Length/1KB, 1)) KB)"
        }
} else {
    Write-Output "Documents folder not found"
}`
        const tmpFile = `${process.env.TEMP}\\recent_docs.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No recent documents found"
      },
    },
  ],
} satisfies Plugin
