import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { platform } from "os"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e) {
    return ""
  }
}

function listInstalledApps(): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`📦 Installed Applications`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const programs: string[] = []

    // Registry programs
    const reg1 = runCommand('reg query "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall" /s 2>nul | findstr "DisplayName"')
    const reg2 = runCommand('reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall" /s 2>nul | findstr "DisplayName"')

    const extractNames = (output: string) => {
      output.split("\n").forEach(line => {
        const match = line.match(/DisplayName\s+REG_SZ\s+(.+)/)
        if (match) programs.push(match[1].trim())
      })
    }

    extractNames(reg1)
    extractNames(reg2)

    // Remove duplicates
    const unique = [...new Set(programs)].sort()
    lines.push(`Found: ${unique.length} programs\n`)
    unique.forEach(p => lines.push(`  📦 ${p}`))
  } else {
    // Linux
    const dpkg = runCommand("dpkg --list 2>/dev/null | grep ^ii | awk '{print $2}'")
    const rpm = runCommand("rpm -qa 2>/dev/null | sort")

    const packages = (dpkg || rpm || "").split("\n").filter(p => p.trim())
    lines.push(`Found: ${packages.length} packages\n`)
    packages.slice(0, 50).forEach(p => lines.push(`  📦 ${p}`))
    if (packages.length > 50) {
      lines.push(`  ... and ${packages.length - 50} more`)
    }
  }

  return lines.join("\n")
}

function searchApp(query: string): string {
  const os = platform()
  const lines: string[] = []
  lines.push(`🔍 Search: "${query}"`)
  lines.push(`${"─".repeat(40)}`)

  if (os === "win32") {
    const programs: string[] = []
    const reg1 = runCommand('reg query "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall" /s 2>nul | findstr "DisplayName"')
    const reg2 = runCommand('reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall" /s 2>nul | findstr "DisplayName"')

    const extractNames = (output: string) => {
      output.split("\n").forEach(line => {
        const match = line.match(/DisplayName\s+REG_SZ\s+(.+)/)
        if (match && match[1].toLowerCase().includes(query.toLowerCase())) {
          programs.push(match[1].trim())
        }
      })
    }

    extractNames(reg1)
    extractNames(reg2)

    lines.push(`Found: ${programs.length} matches\n`)
    programs.forEach(p => lines.push(`  📦 ${p}`))
  } else {
    const result = runCommand(`dpkg --list 2>/dev/null | grep -i "${query}" | awk '{print $2}'`)
    const packages = result.split("\n").filter(p => p.trim())
    lines.push(`Found: ${packages.length} matches\n`)
    packages.forEach(p => lines.push(`  📦 ${p}`))
  }

  return lines.join("\n")
}

function getPythonPackages(): string {
  const lines: string[] = []
  lines.push(`🐍 Python Packages`)
  lines.push(`${"─".repeat(40)}`)

  const result = runCommand("pip list 2>/dev/null || pip3 list 2>/dev/null")
  const packages = result.split("\n").filter(p => p.trim() && !p.includes("---") && !p.includes("Package"))
  lines.push(`Found: ${packages.length} packages\n`)
  packages.slice(0, 30).forEach(p => lines.push(`  🐍 ${p}`))
  if (packages.length > 30) {
    lines.push(`  ... and ${packages.length - 30} more`)
  }

  return lines.join("\n")
}

function getNpmPackages(): string {
  const lines: string[] = []
  lines.push(`📦 NPM Packages (Global)`)
  lines.push(`${"─".repeat(40)}`)

  const result = runCommand("npm list -g --depth=0 2>/dev/null")
  const packages = result.split("\n").filter(p => p.trim() && !p.includes("empty"))
  lines.push(`Found: ${packages.length} packages\n`)
  packages.forEach(p => lines.push(`  📦 ${p}`))

  return lines.join("\n")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""

        // List all apps
        if (command.match(/^apps|programs|installed$/)) {
          console.log(`\n${listInstalledApps()}\n`)
        }

        // Search apps
        const searchMatch = command.match(/^apps\s+search\s+(.+)$/)
        if (searchMatch) {
          console.log(`\n${searchApp(searchMatch[1])}\n`)
        }

        // Python packages
        if (command.match(/^pip\s+list|python\s+packages$/)) {
          console.log(`\n${getPythonPackages()}\n`)
        }

        // NPM packages
        if (command.match(/^npm\s+list|npm\s+packages$/)) {
          console.log(`\n${getNpmPackages()}\n`)
        }
      }
    }
  }
}) satisfies Plugin