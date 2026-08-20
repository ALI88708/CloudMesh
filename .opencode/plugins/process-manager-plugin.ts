import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { platform } from "os"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 10000 }).trim()
  } catch (e) {
    return ""
  }
}

function formatMemory(kb: number): string {
  if (kb > 1048576) return (kb / 1048576).toFixed(1) + " GB"
  if (kb > 1024) return (kb / 1024).toFixed(1) + " MB"
  return kb + " KB"
}

function listProcesses(filter?: string): string {
  const os = platform()
  let cmd: string

  if (os === "win32") {
    cmd = "tasklist /FO CSV /NH"
    if (filter) {
      cmd = `tasklist /FI "IMAGENAME eq ${filter}*"`
    }
  } else {
    cmd = "ps aux --sort=-%mem | head -20"
    if (filter) {
      cmd = `ps aux | grep "${filter}" | grep -v grep | head -20`
    }
  }

  const result = runCommand(cmd)
  if (!result) return "No processes found"

  const lines: string[] = []
  lines.push(`⚙️ Processes${filter ? ` (filtered: ${filter})` : ""}`)
  lines.push(`${"─".repeat(50)}`)

  if (os === "win32") {
    const processLines = result.split("\n").filter(l => l.includes(","))
    lines.push(`Total: ${processLines.length} processes`)
    lines.push("")

    processLines.slice(0, 15).forEach(line => {
      const parts = line.split(",").map(p => p.replace(/"/g, "").trim())
      if (parts.length >= 5) {
        lines.push(`${parts[0].padEnd(25)} PID:${parts[1].padEnd(8)} Mem:${parts[4].padStart(8)}`)
      }
    })
  } else {
    const processLines = result.split("\n").filter(l => l.trim())
    lines.push(`${result.split("\n").length} processes`)
    lines.push("")

    processLines.forEach(line => {
      const parts = line.split(/\s+/)
      if (parts.length >= 11) {
        const user = parts[0]
        const pid = parts[1]
        const cpu = parts[2]
        const mem = parts[3]
        const cmd = parts.slice(10).join(" ").substring(0, 35)
        lines.push(`${cmd.padEnd(35)} PID:${pid.padEnd(7)} CPU:${cpu.padStart(5)}% MEM:${mem.padStart(5)}%`)
      }
    })
  }

  return lines.join("\n")
}

function getProcessInfo(pidOrName: string): string {
  const os = platform()
  let result: string

  if (os === "win32") {
    result = runCommand(`tasklist /FI "PID eq ${pidOrName}" /V /FO LIST 2>nul`)
    if (!result) {
      result = runCommand(`tasklist /FI "IMAGENAME eq ${pidOrName}*" /V /FO LIST 2>nul`)
    }
  } else {
    result = runCommand(`ps -p ${pidOrName} -o pid,user,%cpu,%mem,rss,vsz,comm,args 2>/dev/null || ps aux | grep "${pidOrName}" | grep -v grep`)
  }

  return result || "Process not found"
}

function killProcess(pidOrName: string): string {
  const os = platform()
  if (os === "win32") {
    const result = runCommand(`taskkill /PID ${pidOrName} /F 2>&1`)
    return result || `Killed process ${pidOrName}`
  } else {
    const result = runCommand(`kill -9 ${pidOrName} 2>&1`)
    return result || `Killed process ${pidOrName}`
  }
}

function getTopProcesses(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`🏆 Top Processes by Memory`)
  lines.push(`${"─".repeat(50)}`)

  if (os === "win32") {
    const result = runCommand("powershell -Command \"Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name, Id, @{N='Memory(MB)';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize\"")
    lines.push(result)
  } else {
    const result = runCommand("ps aux --sort=-%mem | head -11 | tail -10")
    const processLines = result.split("\n").filter(l => l.trim())
    processLines.forEach(line => {
      const parts = line.split(/\s+/)
      if (parts.length >= 11) {
        const name = parts[10]
        const mem = parts[3]
        const cpu = parts[2]
        lines.push(`${name.padEnd(25)} MEM:${mem.padStart(5)}% CPU:${cpu.padStart(5)}%`)
      }
    })
  }

  return lines.join("\n")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""

        // List processes
        if (command.match(/^ps$/)) {
          console.log(`\n${listProcesses()}\n`)
        }

        // Filter processes
        const psFilterMatch = command.match(/^ps\s+find\s+(.+)$/)
        if (psFilterMatch) {
          console.log(`\n${listProcesses(psFilterMatch[1])}\n`)
        }

        // Process info
        const psInfoMatch = command.match(/^ps\s+info\s+(.+)$/)
        if (psInfoMatch) {
          console.log(`\n${getProcessInfo(psInfoMatch[1])}\n`)
        }

        // Kill process
        const psKillMatch = command.match(/^ps\s+kill\s+(.+)$/)
        if (psKillMatch) {
          console.log(`\n${killProcess(psKillMatch[1])}\n`)
        }

        // Top processes
        if (command.match(/^top$/)) {
          console.log(`\n${getTopProcesses()}\n`)
        }
      }
    }
  }
}) satisfies Plugin