import type { Plugin } from "@opencode-ai/plugin"

const SECURITY_PATTERNS = [
  { pattern: /eval\s*\(/gi, severity: "high", message: "eval() usage detected - potential security risk" },
  { pattern: /innerHTML\s*=/gi, severity: "medium", message: "innerHTML usage - potential XSS vulnerability" },
  { pattern: /document\.write\s*\(/gi, severity: "medium", message: "document.write() usage - potential XSS" },
  { pattern: /password\s*[:=]\s*['"][^'"]+['"]/gi, severity: "high", message: "Hardcoded password detected!" },
  { pattern: /api[_-]?key\s*[:=]\s*['"][^'"]+['"]/gi, severity: "high", message: "Hardcoded API key detected!" },
  { pattern: /secret\s*[:=]\s*['"][^'"]+['"]/gi, severity: "high", message: "Hardcoded secret detected!" },
  { pattern: /TODO\s*:/gi, severity: "low", message: "TODO comment found" },
  { pattern: /console\.log\s*\(/gi, severity: "low", message: "console.log() - consider removing in production" },
]

const STYLE_ISSUES = [
  { pattern: /var\s+/g, severity: "low", message: "Use 'const' or 'let' instead of 'var'" },
  { pattern: /==(?!=)/g, severity: "low", message: "Use strict equality (===) instead of ==" },
  { pattern: /!=(?!=)/g, severity: "low", message: "Use strict inequality (!==) instead of !=" },
]

interface ReviewResult {
  file: string
  issues: Array<{
    line?: number
    severity: "high" | "medium" | "low"
    message: string
  }>
}

function reviewCode(content: string, filePath: string): ReviewResult {
  const issues: ReviewResult["issues"] = []
  const lines = content.split("\n")
  
  const allPatterns = [...SECURITY_PATTERNS, ...STYLE_ISSUES]
  
  lines.forEach((line, index) => {
    allPatterns.forEach(({ pattern, severity, message }) => {
      pattern.lastIndex = 0
      if (pattern.test(line)) {
        issues.push({
          line: index + 1,
          severity,
          message: `${message} (line ${index + 1})`
        })
      }
    })
  })
  
  return { file: filePath, issues }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "edit" || input.tool === "write") {
        const filePath = input.args?.filePath
        const content = input.args?.content || input.args?.newString
        
        if (filePath && content) {
          const ext = filePath.split(".").pop()?.toLowerCase()
          const reviewableExts = ["ts", "tsx", "js", "jsx", "py", "go", "rs", "java", "php"]
          
          if (reviewableExts.includes(ext || "")) {
            const result = reviewCode(content, filePath)
            
            if (result.issues.length > 0) {
              const high = result.issues.filter(i => i.severity === "high")
              const medium = result.issues.filter(i => i.severity === "medium")
              const low = result.issues.filter(i => i.severity === "low")
              
              console.log(`\n[code-review] ${filePath}:`)
              if (high.length) console.log(`  🔴 HIGH (${high.length}):`)
              high.forEach(i => console.log(`     ${i.message}`))
              if (medium.length) console.log(`  🟡 MEDIUM (${medium.length}):`)
              medium.forEach(i => console.log(`     ${i.message}`))
              if (low.length) console.log(`  🟢 LOW (${low.length}):`)
              low.forEach(i => console.log(`     ${i.message}`))
              console.log("")
            }
          }
        }
      }
    }
  }
}) satisfies Plugin