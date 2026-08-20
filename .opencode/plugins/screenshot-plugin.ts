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
  name: "screenshot",
  description: "Take screenshots of the screen",
  commands: [
    {
      name: "screenshot",
      description: "Take a full screenshot and save to temp folder",
      handler: () => {
        const script = `
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$path = Join-Path $env:TEMP "screenshot_$(Get-Date -Format 'yyyyMMdd_HHmmss').png"
$bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose()
$bmp.Dispose()
Write-Output $path`
        const tmpFile = `${process.env.TEMP}\\screenshot_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        const result = runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`)
        return result ? `Screenshot saved to: ${result}` : "Failed to take screenshot"
      },
    },
    {
      name: "screenshot area",
      description: "Take a screenshot of the primary screen (area capture)",
      handler: () => {
        const script = `
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$path = Join-Path $env:TEMP "screenshot_area_$(Get-Date -Format 'yyyyMMdd_HHmmss').png"
$bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose()
$bmp.Dispose()
Write-Output $path`
        const tmpFile = `${process.env.TEMP}\\screenshot_area_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        const result = runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`)
        return result ? `Screenshot saved to: ${result}` : "Failed to take screenshot"
      },
    },
  ],
} satisfies Plugin
