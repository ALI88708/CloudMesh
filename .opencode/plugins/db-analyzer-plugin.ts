import type { Plugin } from "@opencode-ai/plugin"

const DB_PATTERNS = [
  { pattern: /SELECT\s+.*\s+FROM\s+(\w+)/gi, type: "SELECT", message: "SELECT query detected" },
  { pattern: /INSERT\s+INTO\s+(\w+)/gi, type: "INSERT", message: "INSERT query detected" },
  { pattern: /UPDATE\s+(\w+)\s+SET/gi, type: "UPDATE", message: "UPDATE query detected" },
  { pattern: /DELETE\s+FROM\s+(\w+)/gi, type: "DELETE", message: "DELETE query detected" },
  { pattern: /CREATE\s+TABLE\s+(\w+)/gi, type: "CREATE", message: "CREATE TABLE detected" },
  { pattern: /DROP\s+TABLE\s+(\w+)/gi, type: "DROP", message: "DROP TABLE detected - DANGER!" },
]

const SQL_INJECTION_PATTERNS = [
  { pattern: /['"]\s*\+\s*.*\+\s*['"]/g, message: "String concatenation in SQL - potential injection!" },
  { pattern: /f['"].*SELECT.*{/gi, message: "f-string in SQL - potential injection!" },
  { pattern: /\$\{.*\}.*SELECT/gi, message: "Template literal in SQL - potential injection!" },
]

interface DBAnalysis {
  queries: Array<{ type: string; message: string; line?: number }>
  vulnerabilities: Array<{ message: string; line?: number }>
}

function analyzeSQL(content: string): DBAnalysis {
  const queries: DBAnalysis["queries"] = []
  const vulnerabilities: DBAnalysis["vulnerabilities"] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    DB_PATTERNS.forEach(({ pattern, type, message }) => {
      pattern.lastIndex = 0
      if (pattern.test(line)) {
        queries.push({ type, message, line: index + 1 })
      }
    })
    
    SQL_INJECTION_PATTERNS.forEach(({ pattern, message }) => {
      if (pattern.test(line)) {
        vulnerabilities.push({ message, line: index + 1 })
      }
    })
  })
  
  return { queries, vulnerabilities }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (filePath && (filePath.endsWith(".sql") || filePath.endsWith(".py") || filePath.endsWith(".js"))) {
          try {
            const content = require("fs").readFileSync(filePath, "utf-8")
            const result = analyzeSQL(content)
            
            if (result.queries.length > 0) {
              console.log(`\n[db-analyzer] ${filePath}:`)
              console.log(`  📊 Found ${result.queries.length} queries:`)
              result.queries.forEach(q => {
                console.log(`     ${q.type}: ${q.message} (line ${q.line})`)
              })
              
              if (result.vulnerabilities.length > 0) {
                console.log(`  ⚠️  ${result.vulnerabilities.length} potential SQL injection risks:`)
                result.vulnerabilities.forEach(v => {
                  console.log(`     ${v.message} (line ${v.line})`)
                })
              }
              console.log("")
            }
          } catch {}
        }
      }
    }
  }
}) satisfies Plugin