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
  name: "color-picker",
  description: "Pick colors from screen and convert color formats",
  commands: [
    {
      name: "color pick",
      description: "Pick the color at the center of the primary screen",
      handler: () => {
        const script = `
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$x = [int]($bounds.Width / 2)
$y = [int]($bounds.Height / 2)
$bmp = New-Object System.Drawing.Bitmap(1, 1)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($x, $y, 0, 0, [System.Drawing.Size]::Empty)
$pixel = $bmp.GetPixel(0, 0)
$hex = "#{0:X2}{1:X2}{2:X2}" -f $pixel.R, $pixel.G, $pixel.B
Write-Output "RGB($($pixel.R), $($pixel.G), $($pixel.B))"
Write-Output "HEX: $hex"
$gfx.Dispose()
$bmp.Dispose()`
        const tmpFile = `${process.env.TEMP}\\colorpick_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not pick color"
      },
    },
    {
      name: "color hex",
      description: "Show info for a hex color (e.g. color hex #FF5733)",
      handler: (args: string) => {
        if (!args) return "Usage: color hex <#RRGGBB>"
        const hex = args.replace("#", "")
        if (!/^[0-9A-Fa-f]{6}$/.test(hex)) return "Invalid hex color. Use format: #RRGGBB"
        const r = parseInt(hex.substring(0, 2), 16)
        const g = parseInt(hex.substring(2, 4), 16)
        const b = parseInt(hex.substring(4, 6), 16)
        const max = Math.max(r, g, b) / 255
        const min = Math.min(r, g, b) / 255
        const l = (max + min) / 2
        let h = 0, s = 0
        if (max !== min) {
          const d = max - min
          s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
          if (max === r / 255) h = ((g / 255 - b / 255) / d + (g / 255 < b / 255 ? 6 : 0)) / 6
          else if (max === g / 255) h = ((b / 255 - r / 255) / d + 2) / 6
          else h = ((r / 255 - g / 255) / d + 4) / 6
        }
        return [
          `Color: #${hex.toUpperCase()}`,
          `RGB: (${r}, ${g}, ${b})`,
          `HSL: (${Math.round(h * 360)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`,
          `CSS: rgb(${r}, ${g}, ${b})`,
        ].join("\n")
      },
    },
  ],
} satisfies Plugin
