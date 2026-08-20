import type { Plugin } from "@opencode-ai/plugin"
import { execSync, writeFileSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

const PS1_FILE = "C:\\Users\\mr_ali7685\\AppData\\Local\\Temp\\opencode-sysaction.ps1"

export default {
  name: "system-actions",
  description: "Quick system actions - lock, sleep, shutdown, restart, etc.",
  commands: [
    {
      name: "lock",
      description: "Lock the computer immediately",
      handler: () => {
        runCommand("rundll32.exe user32.dll,LockWorkStation")
        return "Computer locked."
      },
    },
    {
      name: "sleep",
      description: "Put computer to sleep/standby",
      handler: () => {
        runCommand("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return "Computer going to sleep..."
      },
    },
    {
      name: "hibernate",
      description: "Hibernate the computer",
      handler: () => {
        runCommand("rundll32.exe powrprof.dll,SetSuspendState 1,1,0")
        return "Computer hibernating..."
      },
    },
    {
      name: "restart",
      description: "Restart the computer (10 second delay)",
      handler: () => {
        runCommand("shutdown /r /t 10 /c \"Restarting via opencode\"")
        return "Restart scheduled in 10 seconds. Cancel with: sys cancel"
      },
    },
    {
      name: "shutdown",
      description: "Shutdown the computer (10 second delay)",
      handler: () => {
        runCommand("shutdown /s /t 10 /c \"Shutdown via opencode\"")
        return "Shutdown scheduled in 10 seconds. Cancel with: sys cancel"
      },
    },
    {
      name: "logoff",
      description: "Log off current user immediately",
      handler: () => {
        runCommand("shutdown /l")
        return "Logging off..."
      },
    },
    {
      name: "empty trash",
      description: "Empty the recycle bin",
      handler: () => {
        const ps1Content = `
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class RecycleBin {
    [DllImport("Shell32.dll", CharSet = CharSet.Unicode)]
    public static extern uint SHEmptyRecycleBin(IntPtr hwnd, string pszRootPath, uint dwFlags);
}
"@
$result = [RecycleBin]::SHEmptyRecycleBin([IntPtr]::Zero, $null, 7)
if ($result -eq 0) { Write-Host "Recycle bin emptied successfully." }
else { Write-Host "Recycle bin is already empty or an error occurred." }
`
        writeFileSync(PS1_FILE, ps1Content)
        const result = runCommand(`powershell -ExecutionPolicy Bypass -File "${PS1_FILE}"`)
        return result || "Recycle bin emptied."
      },
    },
  ],
} satisfies Plugin
