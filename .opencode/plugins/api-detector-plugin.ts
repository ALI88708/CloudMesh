import type { Plugin } from "@opencode-ai/plugin"

interface APIEndpoint {
  method: string
  path: string
  line?: number
}

const API_PATTERNS = [
  // Express.js / Fastify
  { pattern: /app\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]/gi, framework: "express" },
  // FastAPI / Flask
  { pattern: @(app|router)\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]/gi, framework: "fastapi" },
  // Django
  { pattern: /path\s*\(\s*['"]([^'"]+)['"]/gi, framework: "django" },
  // REST framework
  { pattern: /@api_view\s*\(\s*\[['"]([\w]+)['"]\]/gi, framework: "rest-framework" },
]

function detectAPIs(content: string): APIEndpoint[] {
  const endpoints: APIEndpoint[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    API_PATTERNS.forEach(({ pattern }) => {
      const regex = new RegExp(pattern.source, pattern.flags)
      let match
      while ((match = regex.exec(line)) !== null) {
        endpoints.push({
          method: match[1]?.toUpperCase() || "UNKNOWN",
          path: match[2] || match[1],
          line: index + 1
        })
      }
    })
  })
  
  return endpoints
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (filePath && (
          filePath.endsWith(".py") || 
          filePath.endsWith(".js") || 
          filePath.endsWith(".ts")
        )) {
          try {
            const content = require("fs").readFileSync(filePath, "utf-8")
            const endpoints = detectAPIs(content)
            
            if (endpoints.length > 0) {
              console.log(`\n[api-detector] ${filePath}:`)
              console.log(`  🔌 Found ${endpoints.length} API endpoints:`)
              endpoints.forEach(ep => {
                console.log(`     ${ep.method}: ${ep.path} (line ${ep.line})`)
              })
              console.log("")
            }
          } catch {}
        }
      }
    }
  }
}) satisfies Plugin