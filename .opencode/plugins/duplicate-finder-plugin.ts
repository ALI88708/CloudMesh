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
  name: "duplicate-finder",
  description: "Find duplicate files by hash",
  commands: [
    {
      name: "dupes",
      description: "Find duplicate files in a directory (e.g. dupes C:\\Users\\me\\Documents)",
      handler: (args: string) => {
        const dir = args.trim() || "."
        const script = `
Write-Output "Scanning for duplicates in: ${dir.Replace('\\', '\\\\')}"
$files = Get-ChildItem -Path "${dir.Replace('\\', '\\\\')}" -Recurse -File -ErrorAction SilentlyContinue
$hashGroups = @{}
$count = 0
foreach ($f in $files) {
    $count++
    if ($count % 100 -eq 0) { Write-Host "`rScanned $count files..." -NoNewline }
    try {
        $hash = (Get-FileHash -Path $f.FullName -Algorithm MD5).Hash
        if (-not $hashGroups.ContainsKey($hash)) { $hashGroups[$hash] = @() }
        $hashGroups[$hash] += $f.FullName
    } catch {}
}
Write-Host ""
$dupes = $hashGroups.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 }
if ($dupes) {
    Write-Output "Found $($dupes.Count) groups of duplicates:"
    foreach ($group in ($dupes | Sort-Object { $_.Value.Count } -Descending | Select-Object -First 20)) {
        Write-Output "---"
        foreach ($file in $group.Value) {
            Write-Output "  $file"
        }
    }
} else {
    Write-Output "No duplicate files found."
}`
        const tmpFile = `${process.env.TEMP}\\dupes_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "No duplicates found"
      },
    },
  ],
} satisfies Plugin
