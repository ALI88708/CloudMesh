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
  name: "disk-space",
  description: "Show disk space information and cleanup",
  commands: [
    {
      name: "disk",
      description: "Show all drives and their space usage",
      handler: () => {
        const result = runCommand('powershell -Command "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N=\'Used(GB)\';E={[math]::Round($_.Used/1GB,2)}}, @{N=\'Free(GB)\';E={[math]::Round($_.Free/1GB,2)}}, @{N=\'Total(GB)\';E={[math]::Round(($_.Used+$_.Free)/1GB,2)}} | Format-Table -AutoSize"')
        return result || "Could not get disk information"
      },
    },
    {
      name: "disk detail",
      description: "Show details for a specific drive",
      handler: (args: string) => {
        const drive = args.trim().toUpperCase() || "C"
        const letter = drive.replace(":", "")
        const result = runCommand(`powershell -Command "Get-PSDrive ${letter} | Select-Object Name, @{N='Used(GB)';E={[math]::Round($_.Used/1GB,2)}}, @{N='Free(GB)';E={[math]::Round($_.Free/1GB,2)}}, @{N='Total(GB)';E={[math]::Round(($_.Used+$_.Free)/1GB,2)}} | Format-List"`)
        return result || `Could not get information for drive ${letter}`
      },
    },
    {
      name: "disk clean",
      description: "Run Windows Disk Cleanup utility",
      handler: () => {
        const script = `
Write-Output "Cleaning temporary files..."
Remove-Item -Path "$env:TEMP\\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "C:\\Windows\\Temp\\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "C:\\Windows\\Prefetch\\*" -Force -ErrorAction SilentlyContinue
Write-Output "Cleanup completed."
$before = (Get-PSDrive C).Free
Write-Output "Free space on C: $([math]::Round($before/1GB,2)) GB"`
        const tmpFile = `${process.env.TEMP}\\diskclean.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Cleanup completed"
      },
    },
  ],
} satisfies Plugin
