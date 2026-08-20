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
  name: "wifi-manager",
  description: "Manage WiFi connections",
  commands: [
    {
      name: "wifi",
      description: "Show available WiFi networks",
      handler: () => {
        const result = runCommand('netsh wlan show networks mode=bssid')
        return result || "No WiFi networks found or WiFi is disabled"
      },
    },
    {
      name: "wifi connect",
      description: "Connect to a WiFi network (e.g. wifi connect MyNetwork)",
      handler: (args: string) => {
        if (!args) return "Usage: wifi connect <network-name>"
        const script = `
netsh wlan connect name="${args.replace(/"/g, '`"')}"
Start-Sleep -Seconds 3
$profile = netsh wlan show interfaces | Select-String "SSID"
Write-Output $profile`
        const tmpFile = `${process.env.TEMP}\\wifi_connect.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || `Connecting to ${args}...`
      },
    },
    {
      name: "wifi disconnect",
      description: "Disconnect from current WiFi",
      handler: () => {
        runCommand("netsh wlan disconnect")
        return "WiFi disconnected"
      },
    },
    {
      name: "wifi password",
      description: "Show WiFi password for connected network",
      handler: () => {
        const script = `
$profile = (netsh wlan show interfaces | Select-String "SSID\\s*:\\s*(.*)" | ForEach-Object { $_.Matches.Groups[1].Value.Trim() }) | Select-Object -First 1
if ($profile) {
    $result = netsh wlan show profile name="$profile" key=clear
    $key = $result | Select-String "Key Content\\s*:\\s*(.*)"
    if ($key) {
        Write-Output "Network: $profile"
        Write-Output "Password: $($key.Matches.Groups[1].Value.Trim())"
    } else {
        Write-Output "Network: $profile (no password or open network)"
    }
} else {
    Write-Output "Not connected to any WiFi network"
}`
        const tmpFile = `${process.env.TEMP}\\wifi_pass.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not get WiFi password"
      },
    },
  ],
} satisfies Plugin
