import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { platform, hostname } from "os"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 10000 }).trim()
  } catch (e) {
    return ""
  }
}

function shutdown(): string {
  const os = platform()
  if (os === "win32") {
    return runCommand("shutdown /s /t 60 /c \"Shutdown via opencode\"")
  } else {
    return runCommand("shutdown -h +1")
  }
}

function restart(): string {
  const os = platform()
  if (os === "win32") {
    return runCommand("shutdown /r /t 60 /c \"Restart via opencode\"")
  } else {
    return runCommand("shutdown -r +1")
  }
}

function cancelShutdown(): string {
  const os = platform()
  if (os === "win32") {
    return runCommand("shutdown /a")
  } else {
    return runCommand("shutdown -c")
  }
}

function getQuickStats(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`⚡ Quick Stats`)
  lines.push(`${"─".repeat(30)}`)

  if (os === "win32") {
    const cpu = runCommand("wmic cpu get loadpercentage /value")
    const cpuMatch = cpu.match(/LoadPercentage=(\d+)/)
    lines.push(`CPU: ${cpuMatch?.[1] || "?"}%`)

    const mem = runCommand("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /value")
    const totalMatch = mem.match(/TotalVisibleMemorySize=(\d+)/)
    const freeMatch = mem.match(/FreePhysicalMemory=(\d+)/)
    if (totalMatch && freeMatch) {
      const total = parseInt(totalMatch[1])
      const free = parseInt(freeMatch[1])
      const used = total - free
      lines.push(`RAM: ${Math.round(used / 1024)}MB / ${Math.round(total / 1024)}MB (${Math.round(used / total * 100)}%)`)
    }

    const disk = runCommand("wmic logicaldisk get freespace,size,caption /format:csv")
    const diskLines = disk.split("\n").filter(l => l.includes(",") && !l.startsWith("Node"))
    diskLines.forEach(line => {
      const parts = line.split(",")
      if (parts.length >= 4 && parts[3]) {
        const free = (parseInt(parts[2]) / 1073741824).toFixed(0)
        const total = (parseInt(parts[3]) / 1073741824).toFixed(0)
        lines.push(`${parts[1]}: ${free}GB free / ${total}GB`)
      }
    })
  } else {
    const mem = runCommand("free -m | grep Mem")
    const parts = mem.split(/\s+/)
    if (parts.length >= 4) {
      lines.push(`RAM: ${parts[2]}MB / ${parts[1]}MB`)
    }

    const cpu = runCommand("top -bn1 | grep Cpu | awk '{print $2}'")
    lines.push(`CPU: ${cpu || "?"}%`)
  }

  return lines.join("\n")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""

        // Quick stats
        if (command.match(/^qs|quickstats|stats$/)) {
          console.log(`\n${getQuickStats()}\n`)
        }

        // Shutdown
        if (command.match(/^sys\s+shutdown|poweroff$/)) {
          console.log(`\n⚠️ Shutdown in 60 seconds... (use sys cancel to abort)\n`)
          console.log(shutdown())
        }

        // Restart
        if (command.match(/^sys\s+restart|reboot$/)) {
          console.log(`\n⚠️ Restart in 60 seconds... (use sys cancel to abort)\n`)
          console.log(restart())
        }

        // Cancel
        if (command.match(/^sys\s+cancel|cancel\s+shutdown$/)) {
          console.log(`\n✅ Shutdown cancelled!\n`)
          console.log(cancelShutdown())
        }

        // Hostname
        if (command.match(/^hostname|host$/)) {
          console.log(`\n🖥️ Hostname: ${hostname()}\n`)
        }
      }
    }
  }
}) satisfies Plugin