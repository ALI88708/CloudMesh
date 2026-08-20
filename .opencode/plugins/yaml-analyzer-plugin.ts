import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync } from "fs"

function validateYAML(yaml: string): { valid: boolean; error?: string; line?: number } {
  const lines = yaml.split("\n")
  const errors: string[] = []
  
  lines.forEach((line, index) => {
    // Check for tabs
    if (line.includes("\t")) {
      errors.push(`Line ${index + 1}: Tabs found (use spaces)`)
    }
    
    // Check for trailing spaces
    if (line !== line.trimEnd()) {
      errors.push(`Line ${index + 1}: Trailing spaces`)
    }
    
    // Check for inconsistent indentation
    const indent = line.match(/^(\s*)/)?.[1] || ""
    if (indent.length % 2 !== 0) {
      errors.push(`Line ${index + 1}: Odd indentation (${indent.length} spaces)`)
    }
  })
  
  // Check for duplicate keys
  const keys = new Set<string>()
  lines.forEach((line, index) => {
    const match = line.match(/^(\s*)(\w[\w-]*):/)
    if (match) {
      const key = match[2]
      if (keys.has(key)) {
        errors.push(`Line ${index + 1}: Duplicate key "${key}"`)
      }
      keys.add(key)
    }
  })
  
  // Check for missing document start
  if (!yaml.trimStart().startsWith("---")) {
    errors.push("Missing document start (---)")
  }
  
  return {
    valid: errors.length === 0,
    error: errors[0],
    line: errors[0] ? parseInt(errors[0].match(/Line (\d+)/)?.[1] || "0") : undefined
  }
}

function formatYAML(yaml: string, indent: number = 2): string {
  const lines = yaml.split("\n")
  const formatted: string[] = []
  let currentIndent = 0
  
  lines.forEach((line, index) => {
    const trimmed = line.trim()
    
    if (trimmed === "---" || trimmed === "...") {
      formatted.push(trimmed)
      return
    }
    
    if (trimmed.startsWith("- ")) {
      formatted.push(" ".repeat(currentIndent) + trimmed)
    } else if (trimmed.includes(":")) {
      const [key, ...valueParts] = trimmed.split(":")
      const value = valueParts.join(":").trim()
      
      formatted.push(" ".repeat(currentIndent) + key + ":")
      
      if (value) {
        formatted.push(" ".repeat(currentIndent + indent) + value)
      }
    } else if (trimmed) {
      formatted.push(" ".repeat(currentIndent) + trimmed)
    }
  })
  
  return formatted.join("\n")
}

function yamlToJSON(yaml: string): string | null {
  try {
    const lines = yaml.split("\n").filter(l => l.trim() && !l.trim().startsWith("---"))
    const result: any = {}
    let currentKey = ""
    let currentObj = result
    
    lines.forEach(line => {
      const match = line.match(/^(\s*)([\w-]+):\s*(.*)/)
      if (match) {
        const [, indent, key, value] = match
        const indentLevel = indent.length / 2
        
        if (indentLevel === 0) {
          currentKey = key
          result[key] = value || {}
          currentObj = result[key]
        } else if (value) {
          currentObj[key] = value
        }
      }
      
      // Handle list items
      if (line.trim().startsWith("- ")) {
        const item = line.trim().substring(2)
        if (!Array.isArray(currentObj)) {
          currentObj = []
          result[currentKey] = currentObj
        }
        currentObj.push(item)
      }
    })
    
    return JSON.stringify(result, null, 2)
  } catch {
    return null
  }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Validate YAML
        const validateMatch = command.match(/yaml\s+validate\s+["']([^"']+)["']/)
        if (validateMatch) {
          const [, filePath] = validateMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const result = validateYAML(content)
            
            console.log(`\n[yaml-analyzer] Validation: ${filePath}`)
            console.log(`  Valid: ${result.valid ? "✅ Yes" : "❌ No"}`)
            if (result.error) {
              console.log(`  Error: ${result.error}`)
              if (result.line) console.log(`  Line: ${result.line}`)
            }
          } catch (e) {
            console.log(`[yaml-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Format YAML
        const formatMatch = command.match(/yaml\s+format\s+["']([^"']+)["'](?:\s+--indent\s+(\d+))?/)
        if (formatMatch) {
          const [, filePath, indent = "2"] = formatMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const formatted = formatYAML(content, parseInt(indent))
            
            writeFileSync(filePath, formatted)
            console.log(`\n[yaml-analyzer] Formatted: ${filePath}`)
          } catch (e) {
            console.log(`[yaml-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Convert YAML to JSON
        const jsonMatch = command.match(/yaml\s+to\s+json\s+["']([^"']+)["']/)
        if (jsonMatch) {
          const [, filePath] = jsonMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const json = yamlToJSON(content)
            
            if (json) {
              console.log(`\n[yaml-analyzer] YAML to JSON:`)
              console.log(json)
            } else {
              console.log(`[yaml-analyzer] Failed to parse YAML`)
            }
          } catch (e) {
            console.log(`[yaml-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Analyze YAML structure
        const analyzeMatch = command.match(/yaml\s+analyze\s+["']([^"']+)["']/)
        if (analyzeMatch) {
          const [, filePath] = analyzeMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const lines = content.split("\n")
            
            let keys = 0
            let lists = 0
            let comments = 0
            
            lines.forEach(line => {
              if (line.match(/^\s*[\w-]+:/)) keys++
              if (line.trim().startsWith("-")) lists++
              if (line.trim().startsWith("#")) comments++
            })
            
            console.log(`\n[yaml-analyzer] Structure: ${filePath}`)
            console.log(`  Lines: ${lines.length}`)
            console.log(`  Keys: ${keys}`)
            console.log(`  Lists: ${lists}`)
            console.log(`  Comments: ${comments}`)
          } catch (e) {
            console.log(`[yaml-analyzer] Error: ${e}`)
          }
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin