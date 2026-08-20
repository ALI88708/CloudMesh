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
  name: "network-speed",
  description: "Test network speed",
  commands: [
    {
      name: "speed",
      description: "Test internet download speed using a 10MB file",
      handler: () => {
        const script = `
Write-Output "Testing download speed..."
$url = "http://speedtest.tele2.net/10MB.zip"
$dest = Join-Path $env:TEMP "speedtest_10mb.zip"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($url, $dest)
    $sw.Stop()
    $size = (Get-Item $dest).Length
    $speedMbps = [math]::Round(($size / $sw.Elapsed.TotalSeconds / 1MB) * 8, 2)
    Write-Output "Download Speed: $speedMbps Mbps"
    Write-Output "Time: $([math]::Round($sw.Elapsed.TotalSeconds, 2))s"
    Write-Output "Size: $([math]::Round($size / 1MB, 2)) MB"
    Remove-Item $dest -Force -ErrorAction SilentlyContinue
} catch {
    Write-Output "Speed test failed: $_"
}`
        const tmpFile = `${process.env.TEMP}\\speed_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Speed test failed"
      },
    },
    {
      name: "speed local",
      description: "Test local network latency to common addresses",
      handler: () => {
        const targets = ["127.0.0.1", "8.8.8.8", "1.1.1.1"]
        const results: string[] = ["Local Network Latency Test:"]
        for (const target of targets) {
          const result = runCommand(`ping -n 4 ${target}`)
          const match = result.match(/Average = (\d+)ms/)
          results.push(`  ${target}: ${match ? match[1] + "ms avg" : "timeout"}`)
        }
        return results.join("\n")
      },
    },
  ],
} satisfies Plugin
