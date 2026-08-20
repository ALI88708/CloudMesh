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
  name: "keyboard-shortcuts",
  description: "Keyboard shortcut reference and key press simulator",
  commands: [
    {
      name: "shortcuts",
      description: "Show common Windows keyboard shortcuts",
      handler: () => {
        return [
          "Common Windows Keyboard Shortcuts:",
          "  Ctrl+C / Ctrl+V     - Copy / Paste",
          "  Ctrl+X               - Cut",
          "  Ctrl+Z               - Undo",
          "  Ctrl+Y               - Redo",
          "  Ctrl+A               - Select All",
          "  Ctrl+S               - Save",
          "  Ctrl+P               - Print",
          "  Ctrl+F               - Find",
          "  Ctrl+H               - Find & Replace",
          "  Ctrl+N               - New Window",
          "  Ctrl+W               - Close Window",
          "  Ctrl+Tab             - Switch Tabs",
          "  Alt+Tab              - Switch Windows",
          "  Alt+F4               - Close App",
          "  Win+D                - Show Desktop",
          "  Win+E                - Open Explorer",
          "  Win+L                - Lock Screen",
          "  Win+R                - Run Dialog",
          "  Win+I                - Settings",
          "  Win+Shift+S          - Screenshot",
          "  Ctrl+Shift+Esc       - Task Manager",
        ].join("\n")
      },
    },
    {
      name: "shortcut press",
      description: "Simulate pressing a key combo (e.g. shortcut press ctrl+alt+delete)",
      handler: (args: string) => {
        if (!args) return "Usage: shortcut press <combo>\nExample: shortcut press ctrl+c"
        const keys = args.toLowerCase().split("+").map((k) => k.trim())
        const keyMap: Record<string, string> = {
          ctrl: "^(+)", alt: "%(+)", shift: "+(^)",
          enter: "{ENTER}", tab: "{TAB}", esc: "{ESC}", escape: "{ESC}",
          delete: "{DELETE}", backspace: "{BACKSPACE}", space: " ",
          up: "{UP}", down: "{DOWN}", left: "{LEFT}", right: "{RIGHT}",
          home: "{HOME}", end: "{END}", pageup: "{PGUP}", pagedown: "{PGDN}",
          f1: "{F1}", f2: "{F2}", f3: "{F3}", f4: "{F4}", f5: "{F5}",
          f6: "{F6}", f7: "{F7}", f8: "{F8}", f9: "{F9}", f10: "{F10}",
          f11: "{F11}", f12: "{F12}",
        }
        let sendKeys = ""
        for (const key of keys) {
          if (keyMap[key]) sendKeys += keyMap[key]
          else if (key.length === 1) sendKeys += key.toUpperCase()
          else sendKeys += `{${key.toUpperCase()}}`
        }
        const script = `
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("${sendKeys}")`
        const tmpFile = `${process.env.TEMP}\\sendkeys_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`)
        return `Pressed: ${args}`
      },
    },
  ],
} satisfies Plugin
