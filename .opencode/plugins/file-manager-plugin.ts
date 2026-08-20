import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { existsSync, statSync, readdirSync, mkdirSync, copyFileSync, unlinkSync, renameSync } from "fs"
import { join, resolve, extname, basename } from "path"
import { platform } from "os"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 10000 }).trim()
  } catch (e) {
    return ""
  }
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i]
}

function formatDate(date: Date): string {
  return date.toLocaleDateString() + " " + date.toLocaleTimeString()
}

function listDirectory(path: string, showHidden: boolean = false): string {
  try {
    const resolved = resolve(path)
    const items = readdirSync(resolved)
    const lines: string[] = []

    lines.push(`📁 ${resolved}`)
    lines.push(`${"─".repeat(50)}`)

    const dirs: string[] = []
    const files: string[] = []

    items.forEach(item => {
      if (!showHidden && item.startsWith(".")) return
      try {
        const stat = statSync(join(resolved, item))
        if (stat.isDirectory()) {
          dirs.push(`📁 ${item}/`)
        } else {
          const size = formatSize(stat.size)
          const date = formatDate(stat.mtime)
          files.push(`📄 ${item.padEnd(30)} ${size.padStart(10)} ${date}`)
        }
      } catch {
        lines.push(`❓ ${item}`)
      }
    })

    if (dirs.length > 0) {
      lines.push(`\nDirectories (${dirs.length}):`)
      dirs.sort().forEach(d => lines.push(`  ${d}`))
    }

    if (files.length > 0) {
      lines.push(`\nFiles (${files.length}):`)
      files.sort().forEach(f => lines.push(`  ${f}`))
    }

    lines.push(`\nTotal: ${dirs.length} dirs, ${files.length} files`)
    return lines.join("\n")
  } catch (e) {
    return `Error listing directory: ${e}`
  }
}

function getFileInfo(path: string): string {
  try {
    const stat = statSync(path)
    const ext = extname(path)
    const name = basename(path)

    return [
      `📄 File Info: ${name}`,
      `${"─".repeat(30)}`,
      `Path: ${path}`,
      `Size: ${formatSize(stat.size)}`,
      `Type: ${ext || "unknown"}`,
      `Created: ${formatDate(stat.birthtime)}`,
      `Modified: ${formatDate(stat.mtime)}`,
      `Accessed: ${formatDate(stat.atime)}`,
      `Readonly: ${stat.readonly ? "Yes" : "No"}`,
    ].join("\n")
  } catch (e) {
    return `Error: ${e}`
  }
}

function searchFiles(dir: string, pattern: string): string {
  const os = platform()
  if (os === "win32") {
    return runCommand(`dir /s /b "${join(dir, pattern)}" 2>nul`)
  } else {
    return runCommand(`find "${dir}" -name "${pattern}" -type f 2>/dev/null | head -20`)
  }
}

function getDirectorySize(path: string): string {
  const os = platform()
  if (os === "win32") {
    const result = runCommand(`powershell -Command "(Get-ChildItem -Path '${path}' -Recurse -File | Measure-Object -Property Length -Sum).Sum"`)
    const bytes = parseInt(result) || 0
    return formatSize(bytes)
  } else {
    const result = runCommand(`du -sh "${path}" 2>/dev/null | awk '{print $1}'`)
    return result || "Unknown"
  }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""

        // List directory
        const lsMatch = command.match(/^ls\s*(.*)$/)
        if (lsMatch) {
          const path = lsMatch[1] || "."
          const showHidden = command.includes("-a") || command.includes("-la") || command.includes("-al")
          console.log(`\n${listDirectory(path, showHidden)}\n`)
        }

        // File info
        const fiMatch = command.match(/^fi\s+(.+)$/)
        if (fiMatch) {
          console.log(`\n${getFileInfo(fiMatch[1])}\n`)
        }

        // Search files
        const findMatch = command.match(/^find\s+(.+?)\s+(.+)$/)
        if (findMatch) {
          console.log(`\n🔍 Searching in ${findMatch[1]} for "${findMatch[2]}":`)
          const results = searchFiles(findMatch[1], findMatch[2])
          console.log(results || "No results found")
          console.log("")
        }

        // Directory size
        const duMatch = command.match(/^du\s+(.+)$/)
        if (duMatch) {
          console.log(`\n📊 Size of ${duMatch[1]}: ${getDirectorySize(duMatch[1])}\n`)
        }

        // Quick access shortcuts
        if (command.match(/^cd~$/)) {
          console.log(`\n🏠 Home: ${process.env.USERPROFILE || process.env.HOME}\n`)
        }

        if (command.match(/^cd Desktop$/)) {
          const home = process.env.USERPROFILE || process.env.HOME || ""
          const desktop = join(home, "Desktop")
          console.log(`\n🖥️ Desktop: ${desktop}\n`)
        }

        if (command.match(/^cd Downloads$/)) {
          const home = process.env.USERPROFILE || process.env.HOME || ""
          const downloads = join(home, "Downloads")
          console.log(`\n📥 Downloads: ${downloads}\n`)
        }

        if (command.match(/^cd Documents$/)) {
          const home = process.env.USERPROFILE || process.env.HOME || ""
          const docs = join(home, "Documents")
          console.log(`\n📄 Documents: ${docs}\n`)
        }
      }
    }
  }
}) satisfies Plugin