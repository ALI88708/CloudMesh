import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"

interface LogEntry {
  timestamp?: string
  level: string
  message: string
  source?: string
  line?: number
}

const LOG_PATTERNS = [
  { pattern: /\[(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})\]\s*(ERROR|WARN|INFO|DEBUG)\s*(.*)/i, type: "structured" },
  { pattern: /(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})\s*(ERROR|WARN|INFO|DEBUG)\s*(.*)/i, type: "timestamp-first" },
  { pattern: /(ERROR|WARN|INFO|DEBUG)[:\s]+(.*)/i, type: "level-first" },
]

const ERROR_PATTERNS = [
  { pattern: /error|exception|failed|failure/i, severity: "high" },
  { pattern: /warning|warn|deprecated/i, severity: "medium" },
  { pattern: /debug|trace/i, severity: "low" },
]

function analyzeLogs(content: string): LogEntry[] {
  const entries: LogEntry[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    for (const { pattern } of LOG_PATTERNS) {
      const match = line.match(pattern)
      if (match) {
        entries.push({
          timestamp: match[1],
          level: match[2]?.toUpperCase() || "UNKNOWN",
          message: match[3] || match[2],
          line: index + 1
        })
        break
      }
    }
  })
  
  return entries
}

function findErrors(content: string): Array<{ message: string; line: number; severity: string }> {
  const errors: Array<{ message: string; line: number; severity: string }> = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    ERROR_PATTERNS.forEach(({ pattern, severity }) => {
      if (pattern.test(line)) {
        errors.push({
          message: line.trim().substring(0, 100),
          line: index + 1,
          severity
        })
      }
    })
  })
  
  return errors
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (!filePath) return
        
        const logExtensions = [".log", ".txt"]
        const isLog = logExtensions.some(ext => filePath.endsWith(ext))
        const isLogFile = filePath.includes("log") || filePath.includes("Log")
        
        if (isLog || isLogFile) {
          try {
            const content = readFileSync(filePath, "utf-8")
            const entries = analyzeLogs(content)
            const errors = findErrors(content)
            
            console.log(`\n[log-analyzer] ${filePath}:`)
            console.log(`  📋 Found ${entries.length} log entries`)
            
            if (errors.length > 0) {
              const high = errors.filter(e => e.severity === "high")
              const medium = errors.filter(e => e.severity === "medium")
              
              if (high.length) {
                console.log(`  🔴 HIGH (${high.length}):`)
                high.slice(0, 5).forEach(e => {
                  console.log(`     Line ${e.line}: ${e.message}`)
                })
              }
              
              if (medium.length) {
                console.log(`  🟡 MEDIUM (${medium.length}):`)
                medium.slice(0, 5).forEach(e => {
                  console.log(`     Line ${e.line}: ${e.message}`)
                })
              }
            }
            
            console.log("")
          } catch {}
        }
      }
    }
  }
}) satisfies Plugin