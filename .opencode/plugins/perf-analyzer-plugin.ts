import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"

interface PerformanceIssue {
  type: string
  severity: "high" | "medium" | "low"
  message: string
  line?: number
}

const PERF_PATTERNS = [
  // Python
  { pattern: /for\s+\w+\s+in\s+range\s*\(\s*len\s*\(/g, type: "python", message: "Use enumerate() instead of range(len())" },
  { pattern: /\+\s*=\s*['"]/g, type: "python", message: "String concatenation in loop - use join()" },
  { pattern: /import\s+\*/g, type: "python", message: "Wildcard import - avoid for performance" },
  
  // JavaScript/TypeScript
  { pattern: /document\.getElementById/g, type: "js", message: "Consider using querySelector for better performance" },
  { pattern: /innerHTML\s*=/g, type: "js", message: "innerHTML is slower than textContent for plain text" },
  { pattern: /new\s+Array\s*\(/g, type: "js", message: "Use Array literal [] instead of new Array()" },
  { pattern: /\.forEach\s*\(/g, type: "js", message: "for loop is faster than forEach" },
  
  // General
  { pattern: /console\.log\s*\(/g, type: "general", message: "console.log impacts performance - remove in production" },
  { pattern: /debugger\s*;/g, type: "general", message: "Debugger statement found - remove before deployment" },
  { pattern: /TODO.*performance/gi, type: "general", message: "Performance TODO found" },
]

function analyzePerformance(content: string): PerformanceIssue[] {
  const issues: PerformanceIssue[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    PERF_PATTERNS.forEach(({ pattern, type, message }) => {
      const regex = new RegExp(pattern.source, pattern.flags)
      if (regex.test(line)) {
        issues.push({
          type,
          severity: type === "general" ? "low" : "medium",
          message,
          line: index + 1
        })
      }
    })
  })
  
  return issues
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (!filePath) return
        
        if (filePath.endsWith(".py") || filePath.endsWith(".js") || 
            filePath.endsWith(".ts") || filePath.endsWith(".tsx")) {
          try {
            const content = readFileSync(filePath, "utf-8")
            const issues = analyzePerformance(content)
            
            if (issues.length > 0) {
              console.log(`\n[perf-analyzer] ${filePath}:`)
              console.log(`  ⚡ Found ${issues.length} performance suggestions:`)
              
              const grouped = issues.reduce((acc, issue) => {
                if (!acc[issue.severity]) acc[issue.severity] = []
                acc[issue.severity].push(issue)
                return acc
              }, {} as Record<string, PerformanceIssue[]>)
              
              if (grouped.high) {
                console.log(`  🔴 HIGH:`)
                grouped.high.forEach(i => console.log(`     Line ${i.line}: ${i.message}`))
              }
              if (grouped.medium) {
                console.log(`  🟡 MEDIUM:`)
                grouped.medium.slice(0, 3).forEach(i => console.log(`     Line ${i.line}: ${i.message}`))
              }
              if (grouped.low) {
                console.log(`  🟢 LOW:`)
                grouped.low.slice(0, 2).forEach(i => console.log(`     Line ${i.line}: ${i.message}`))
              }
              
              console.log("")
            }
          } catch {}
        }
      }
    }
  }
}) satisfies Plugin