import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync } from "fs"

const ENV_PATTERNS = [
  { pattern: /process\.env\.([A-Z_]+)/g, source: "node" },
  { pattern: /os\.environ\.get\(['"]([A-Z_]+)['"]\)/g, source: "python" },
  { pattern: /os\.getenv\(['"]([A-Z_]+)['"]\)/g, source: "python" },
  { pattern: /env!\(['"]([A-Z_]+)['"]\)/g, source: "rust" },
  { pattern: /os\.Getenv\(['"]([A-Z_]+)['"]\)/g, source: "go" },
]

interface EnvUsage {
  variable: string
  source: string
  line?: number
}

function findEnvUsages(content: string): EnvUsage[] {
  const usages: EnvUsage[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    ENV_PATTERNS.forEach(({ pattern, source }) => {
      const regex = new RegExp(pattern.source, pattern.flags)
      let match
      while ((match = regex.exec(line)) !== null) {
        usages.push({
          variable: match[1],
          source,
          line: index + 1
        })
      }
    })
  })
  
  return usages
}

function checkEnvFile(): string[] {
  const envFiles = [".env", ".env.local", ".env.development", ".env.production"]
  const missing: string[] = []
  
  envFiles.forEach(file => {
    if (!existsSync(file)) {
      missing.push(file)
    }
  })
  
  return missing
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (filePath && (
          filePath.endsWith(".py") || 
          filePath.endsWith(".js") || 
          filePath.endsWith(".ts") ||
          filePath.endsWith(".go") ||
          filePath.endsWith(".rs")
        )) {
          try {
            const content = readFileSync(filePath, "utf-8")
            const usages = findEnvUsages(content)
            
            if (usages.length > 0) {
              console.log(`\n[env-manager] ${filePath}:`)
              console.log(`  🌐 Found ${usages.length} environment variable usages:`)
              
              const grouped = usages.reduce((acc, u) => {
                if (!acc[u.source]) acc[u.source] = []
                acc[u.source].push(u)
                return acc
              }, {} as Record<string, EnvUsage[]>)
              
              Object.entries(grouped).forEach(([source, vars]) => {
                console.log(`     ${source}:`)
                vars.forEach(v => {
                  console.log(`       - ${v.variable} (line ${v.line})`)
                })
              })
              
              const missing = checkEnvFile()
              if (missing.length > 0) {
                console.log(`  ⚠️  Missing env files: ${missing.join(", ")}`)
              }
              console.log("")
            }
          } catch {}
        }
      }
    }
  }
}) satisfies Plugin