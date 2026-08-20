import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync } from "fs"

interface ConfigInfo {
  type: string
  settings: Record<string, any>
  issues: string[]
}

function analyzeJSON(content: string): ConfigInfo {
  const issues: string[] = []
  let settings: Record<string, any> = {}
  
  try {
    settings = JSON.parse(content)
    
    // Check for common issues
    if (settings.password || settings.secret || settings.apiKey || settings.token) {
      issues.push("Hardcoded secrets detected in config!")
    }
    
    if (settings.debug === true) {
      issues.push("Debug mode is enabled - disable in production")
    }
    
    if (settings.port && settings.port < 1024) {
      issues.push("Using privileged port (< 1024)")
    }
    
    if (!settings.version && !settings.$schema) {
      issues.push("Missing version or schema declaration")
    }
    
  } catch (e) {
    issues.push("Invalid JSON syntax")
  }
  
  return { type: "json", settings, issues }
}

function analyzeYAML(content: string): ConfigInfo {
  const issues: string[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    // Check for tabs (YAML should use spaces)
    if (line.includes("\t")) {
      issues.push(`Line ${index + 1}: Tabs detected - YAML should use spaces`)
    }
    
    // Check for potential secrets
    if (/password|secret|api[_-]?key|token/i.test(line) && /:\s*['"]?[^'"]+['"]?/.test(line)) {
      issues.push(`Line ${index + 1}: Potential hardcoded secret`)
    }
  })
  
  return { type: "yaml", settings: {}, issues }
}

function analyzeINI(content: string): ConfigInfo {
  const issues: string[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    // Check for potential secrets
    if (/password|secret|api[_-]?key|token/i.test(line) && /=/.test(line)) {
      issues.push(`Line ${index + 1}: Potential hardcoded secret`)
    }
    
    // Check for comments with TODO
    if (line.includes("#") && /TODO|FIXME|HACK/i.test(line)) {
      issues.push(`Line ${index + 1}: TODO/FIXME in config`)
    }
  })
  
  return { type: "ini", settings: {}, issues }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (!filePath) return
        
        const configFiles = [
          "package.json", "tsconfig.json", "pyproject.toml", 
          "docker-compose.yml", "nginx.conf", ".env",
          "config.json", "settings.json", "appsettings.json"
        ]
        
        const isConfig = configFiles.some(f => filePath.includes(f)) ||
                        filePath.endsWith(".json") ||
                        filePath.endsWith(".yml") ||
                        filePath.endsWith(".yaml") ||
                        filePath.endsWith(".toml") ||
                        filePath.endsWith(".ini") ||
                        filePath.endsWith(".conf")
        
        if (isConfig) {
          try {
            const content = readFileSync(filePath, "utf-8")
            let result: ConfigInfo
            
            if (filePath.endsWith(".json")) {
              result = analyzeJSON(content)
            } else if (filePath.endsWith(".yml") || filePath.endsWith(".yaml")) {
              result = analyzeYAML(content)
            } else {
              result = analyzeINI(content)
            }
            
            if (result.issues.length > 0) {
              console.log(`\n[config-analyzer] ${filePath}:`)
              console.log(`  ⚙️  Config type: ${result.type}`)
              console.log(`  ⚠️  Issues:`)
              result.issues.forEach(i => {
                console.log(`     ${i}`)
              })
              console.log("")
            }
          } catch {}
        }
      }
    }
  }
}) satisfies Plugin