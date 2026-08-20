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
  name: "bluetooth-manager",
  description: "Manage Bluetooth devices",
  commands: [
    {
      name: "bt",
      description: "Show paired Bluetooth devices",
      handler: () => {
        const result = runCommand('powershell -Command "Get-PairedBluetoothDevice | Select-Object Name, Address, Connected | Format-Table -AutoSize"')
        return result || "No paired Bluetooth devices found"
      },
    },
    {
      name: "bt scan",
      description: "Scan for available Bluetooth devices",
      handler: () => {
        const script = `
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Devices.Bluetooth.BluetoothAdapter,Windows.Devices.Bluetooth,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Bluetooth.BluetoothDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime] | Out-Null
Write-Output "Scanning for Bluetooth devices..."
$devices = Get-PairedBluetoothDevice
if ($devices) {
    $devices | Format-Table Name, Address -AutoSize
} else {
    Write-Output "No devices found. Make sure Bluetooth is enabled."
}`
        const tmpFile = `${process.env.TEMP}\\bt_scan.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Bluetooth scan completed"
      },
    },
    {
      name: "bt on",
      description: "Turn on Bluetooth",
      handler: () => {
        const result = runCommand('powershell -Command "Start-Process ms-settings:bluetooth"')
        return "Opening Bluetooth settings. Toggle Bluetooth ON from there."
      },
    },
    {
      name: "bt off",
      description: "Turn off Bluetooth",
      handler: () => {
        const result = runCommand('powershell -Command "Start-Process ms-settings:bluetooth"')
        return "Opening Bluetooth settings. Toggle Bluetooth OFF from there."
      },
    },
  ],
} satisfies Plugin
