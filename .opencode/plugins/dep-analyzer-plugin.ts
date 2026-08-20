import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"

interface DepInfo {
  name: string
  version: string
  type: "production" | "development" | "peer" | "optional"
  hasLockfile: boolean
  issues: string[]
}

function analyzePackageJson(content: string): DepInfo[] {
  const deps: DepInfo[] = []
  
  try {
    const pkg = JSON.parse(content)
    
    const processDeps = (depObj: Record<string, string>, type: DepInfo["type"]) => {
      Object.entries(depObj).forEach(([name, version]) => {
        const issues: string[] = []
        
        if (version.includes("*")) {
          issues.push("Wildcard version - use specific version")
        }
        
        if (version.includes("latest")) {
          issues.push("Using 'latest' tag - pin to specific version")
        }
        
        if (version.startsWith("^") || version.startsWith("~")) {
          issues.push("Range version - consider pinning for production")
        }
        
        deps.push({ name, version, type, hasLockfile: false, issues })
      })
    }
    
    if (pkg.dependencies) processDeps(pkg.dependencies, "production")
    if (pkg.devDependencies) processDeps(pkg.devDependencies, "development")
    if (pkg.peerDependencies) processDeps(pkg.peerDependencies, "peer")
    if (pkg.optionalDependencies) processDeps(pkg.optionalDependencies, "optional")
    
  } catch {}
  
  return deps
}

function analyzeRequirementsTxt(content: string): DepInfo[] {
  const deps: DepInfo[] = []
  
  content.split("\n").forEach(line => {
    const trimmed = line.trim()
    if (trimmed && !trimmed.startsWith("#") && !trimmed.startsWith("-")) {
      const match = trimmed.match(/^([a-zA-Z0-9_-]+)\s*([><=!~]+.+)?$/)
      if (match) {
        deps.push({
          name: match[1],
          version: match[2] || "unspecified",
          type: "production",
          hasLockfile: false,
          issues: !match[2] ? ["No version specified"] : []
        })
      }
    }
  })
  
  return deps
}

function analyzePyprojectToml(content: string): DepInfo[] {
  const deps: DepInfo[] = []
  
  const lines = content.split("\n")
  let inDeps = false
  
  lines.forEach(line => {
    if (line.includes("dependencies")) inDeps = true
    if (inDeps && line.includes("]")) inDeps = false
    
    if (inDeps) {
      const match = line.match(/["']([a-zA-Z0-9_-]+)\s*([><=!~]+.+)?["']/)
      if (match) {
        deps.push({
          name: match[1],
          version: match[2] || "unspecified",
          type: "production",
          hasLockfile: false,
          issues: !match[2] ? ["No version specified"] : []
        })
      }
    }
  })
  
  return deps
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (!filePath) return
        
        try {
          let deps: DepInfo[] = []
          
          if (filePath.endsWith("package.json")) {
            const content = readFileSync(filePath, "utf-8")
            deps = analyzePackageJson(content)
          } else if (filePath.endsWith("requirements.txt")) {
            const content = readFileSync(filePath, "utf-8")
            deps = analyzeRequirementsTxt(content)
          } else if (filePath.endsWith("pyproject.toml")) {
            const content = readFileSync(filePath, "utf-8")
            deps = analyzePyprojectToml(content)
          }
          
          if (deps.length > 0) {
            const withIssues = deps.filter(d => d.issues.length > 0)
            
            if (withIssues.length > 0) {
              console.log(`\n[dep-analyzer] ${filePath}:`)
              console.log(`  📦 Found ${deps.length} dependencies`)
              console.log(`  ⚠️  ${withIssues.length} with issues:`)
              withIssues.slice(0, 5).forEach(d => {
                console.log(`     ${d.name}@${d.version}: ${d.issues[0]}`)
              })
              console.log("")
            }
          }
        } catch {}
      }
    }
  }
}) satisfies Plugin