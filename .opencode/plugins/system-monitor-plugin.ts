import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { platform } from "os"

function getOS(): string {
  return platform()
}

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 10000 }).trim()
  } catch (e) {
    return `Error: ${e}`
  }
}

function getCPUInfo(): string {
  const os = getOS()
  if (os === "win32") {
    const usage = runCommand("wmic cpu get loadpercentage /value")
    const match = usage.match(/LoadPercentage=(\d+)/)
    const name = runCommand("wmic cpu get name /value")
    const nameMatch = name.match(/Name=(.+)/)
    const cores = runCommand("wmic cpu get numberofcores /value")
    const coresMatch = cores.match(/NumberOfCores=(\d+)/)
    const threads = runCommand("wmic cpu get numberoflogicalprocessors /value")
    const threadsMatch = threads.match(/NumberOfLogicalProcessors=(\d+)/)
    return `CPU: ${nameMatch?.[1]?.trim() || "Unknown"}
Cores: ${coresMatch?.[1] || "?"} | Threads: ${threadsMatch?.[1] || "?"}
Usage: ${match?.[1] || "?"}%`
  } else {
    const usage = runCommand("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    const name = runCommand("cat /proc/cpuinfo | grep 'model name' | head -1 | awk -F: '{print $2}'")
    const cores = runCommand("nproc")
    return `CPU: ${name.trim() || "Unknown"}
Cores: ${cores}
Usage: ${usage || "?"}%`
  }
}

function getMemoryInfo(): string {
  const os = getOS()
  if (os === "win32") {
    const total = runCommand("wmic OS get TotalVisibleMemorySize /value")
    const free = runCommand("wmic OS get FreePhysicalMemory /value")
    const totalMatch = total.match(/TotalVisibleMemorySize=(\d+)/)
    const freeMatch = free.match(/FreePhysicalMemory=(\d+)/)
    const totalMB = totalMatch ? Math.round(parseInt(totalMatch[1]) / 1024) : 0
    const freeMB = freeMatch ? Math.round(parseInt(freeMatch[1]) / 1024) : 0
    const usedMB = totalMB - freeMB
    const percent = totalMB > 0 ? Math.round((usedMB / totalMB) * 100) : 0
    const totalGB = (totalMB / 1024).toFixed(1)
    const usedGB = (usedMB / 1024).toFixed(1)
    const freeGB = (freeMB / 1024).toFixed(1)
    return `RAM: ${usedGB}GB / ${totalGB}GB (${percent}%)
Free: ${freeGB}GB`
  } else {
    const mem = runCommand("free -m | grep Mem")
    const parts = mem.split(/\s+/)
    const total = parts[1] || "?"
    const used = parts[2] || "?"
    const free = parts[3] || "?"
    return `RAM: ${used}MB / ${total}MB
Free: ${free}MB`
  }
}

function getDiskInfo(): string {
  const os = getOS()
  if (os === "win32") {
    const disks = runCommand("wmic logicaldisk get size,freespace,caption /format:csv")
    const lines = disks.split("\n").filter(l => l.includes(",") && !l.startsWith("Node"))
    const result: string[] = []
    lines.forEach(line => {
      const parts = line.split(",")
      if (parts.length >= 4) {
        const drive = parts[1]
        const free = parts[2] ? (parseInt(parts[2]) / 1073741824).toFixed(1) : "?"
        const total = parts[3] ? (parseInt(parts[3]) / 1073741824).toFixed(1) : "?"
        if (drive && total !== "?") result.push(`${drive} ${free}GB free / ${total}GB`)
      }
    })
    return result.length > 0 ? result.join("\n") : "No disk info"
  } else {
    const disks = runCommand("df -h --type=ext4 --type=xfs --type=btrfs 2>/dev/null | tail -n +2")
    return disks || "No disk info"
  }
}

function getUptime(): string {
  const os = getOS()
  if (os === "win32") {
    const boot = runCommand("wmic os get lastbootuptime /value")
    const match = boot.match(/LastBootUpTime=(\d{14})/)
    if (match) {
      const bootDate = new Date(
        parseInt(match[1].substring(0, 4)),
        parseInt(match[1].substring(4, 6)) - 1,
        parseInt(match[1].substring(6, 8)),
        parseInt(match[1].substring(8, 10)),
        parseInt(match[1].substring(10, 12)),
        parseInt(match[1].substring(12, 14))
      )
      const diff = Date.now() - bootDate.getTime()
      const days = Math.floor(diff / 86400000)
      const hours = Math.floor((diff % 86400000) / 3600000)
      return `Uptime: ${days}d ${hours}h`
    }
    return "Uptime: Unknown"
  } else {
    const uptime = runCommand("uptime -p")
    return `Uptime: ${uptime || "Unknown"}`
  }
}

function getSystemOverview(): string {
  const os = getOS()
  const hostname = runCommand("hostname")
  const osInfo = os === "win32"
    ? runCommand("wmic os get caption /value").match(/Caption=(.+)/)?.[1]?.trim() || "Windows"
    : runCommand("cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2") || "Linux"

  return [
    `🖥️ System Overview`,
    `${"─".repeat(40)}`,
    `OS: ${osInfo}`,
    `Hostname: ${hostname}`,
    ``,
    getCPUInfo(),
    ``,
    getMemoryInfo(),
    ``,
    `💾 Disks:`,
    getDiskInfo(),
    ``,
    getUptime()
  ].join("\n")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""

        if (command.match(/^sys(info|tem)?$/)) {
          console.log(`\n${getSystemOverview()}\n`)
        }

        if (command.match(/^cpu$/)) {
          console.log(`\n${getCPUInfo()}\n`)
        }

        if (command.match(/^ram|memory$/)) {
          console.log(`\n${getMemoryInfo()}\n`)
        }

        if (command.match(/^disk(s)?$/)) {
          console.log(`\n💾 Disks:\n${getDiskInfo()}\n`)
        }

        if (command.match(/^uptime$/)) {
          console.log(`\n${getUptime()}\n`)
        }
      }
    }
  }
}) satisfies Plugin