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
  name: "folder-size",
  description: "Calculate folder sizes",
  commands: [
    {
      name: "size",
      description: "Show size of a directory (e.g. size C:\\Users)",
      handler: (args: string) => {
        if (!args) return "Usage: size <directory>"
        const script = `
$dir = Get-Item -Path "${args.Replace('\\', '\\\\')}" -ErrorAction SilentlyContinue
if ($dir -and $dir.PSIsContainer) {
    $size = (Get-ChildItem -Path $dir.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    $sizeStr = if ($size -gt 1GB) { "$([math]::Round($size/1GB, 2)) GB" }
        elseif ($size -gt 1MB) { "$([math]::Round($size/1MB, 2)) MB" }
        elseif ($size -gt 1KB) { "$([math]::Round($size/1KB, 2)) KB" }
        else { "$size bytes" }
    Write-Output "Folder: $($dir.FullName)"
    Write-Output "Size: $sizeStr"
} else {
    Write-Output "Directory not found: ${args}"
}`
        const tmpFile = `${process.env.TEMP}\\size_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not calculate size"
      },
    },
    {
      name: "size top",
      description: "Show largest folders in current directory",
      handler: () => {
        const script = `
$folders = Get-ChildItem -Path . -Directory -ErrorAction SilentlyContinue
$results = @()
foreach ($f in $folders) {
    $size = (Get-ChildItem -Path $f.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    $results += [PSCustomObject]@{ Name = $f.Name; Size = $size }
}
$results | Sort-Object Size -Descending | Select-Object -First 15 | ForEach-Object {
    $sizeStr = if ($_.Size -gt 1GB) { "$([math]::Round($_.Size/1GB, 2)) GB" }
        elseif ($_.Size -gt 1MB) { "$([math]::Round($_.Size/1MB, 2)) MB" }
        elseif ($_.Size -gt 1KB) { "$([math]::Round($_.Size/1KB, 2)) KB" }
        else { "$($_.Size) bytes" }
    Write-Output "$($_.Name.PadRight(40)) $sizeStr"
}`
        const tmpFile = `${process.env.TEMP}\\sizetop_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No folders found"
      },
    },
  ],
} satisfies Plugin
