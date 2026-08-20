import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync } from "fs"

interface JSONFormatResult {
  isValid: boolean
  formatted?: string
  minified?: string
  error?: string
  path?: string[]
}

function formatJSON(content: string, indent: number = 2): JSONFormatResult {
  try {
    const parsed = JSON.parse(content)
    const formatted = JSON.stringify(parsed, null, indent)
    const minified = JSON.stringify(parsed)
    return { isValid: true, formatted, minified }
  } catch (e) {
    const match = (e as Error).message.match(/position (\d+)/)
    const position = match ? parseInt(match[1]) : 0
    const path = findJSONPath(content, position)
    
    return {
      isValid: false,
      error: e instanceof Error ? e.message : "Invalid JSON",
      path
    }
  }
}

function findJSONPath(content: string, position: number): string[] {
  const path: string[] = []
  let depth = 0
  let currentKey = ""
  
  for (let i = 0; i < position && i < content.length; i++) {
    const char = content[i]
    
    if (char === "{") {
      depth++
    } else if (char === "}") {
      depth--
      if (path.length > 0) path.pop()
    } else if (char === "[") {
      depth++
    } else if (char === "]") {
      depth--
      if (path.length > 0) path.pop()
    } else if (char === '"') {
      let key = ""
      i++
      while (i < content.length && content[i] !== '"') {
        if (content[i] === "\\") {
          i++
        }
        key += content[i]
        i++
      }
      if (content[i + 1] === ":") {
        currentKey = key
        path.push(key)
      }
    }
  }
  
  return path
}

function fixJSON(content: string): string | null {
  let fixed = content.trim()
  
  // Add missing commas between properties
  fixed = fixed.replace(/}\s*{/g, "},{")
  fixed = fixed.replace(/]\s*\[/g, "],[")
  fixed = fixed.replace(/"\s*"/g, '","')
  
  // Add missing colons
  fixed = fixed.replace(/(\w+)\s+"(\w+)"/g, '"$1":"$2"')
  
  // Try to parse
  try {
    JSON.parse(fixed)
    return fixed
  } catch {
    return null
  }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // JSON format command
        const formatMatch = command.match(/json\s+format\s+["']?([^\s"']+)["']?(?:\s+(\d+))?/)
        if (formatMatch) {
          const [, filePath, indent = "2"] = formatMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const result = formatJSON(content, parseInt(indent))
            
            console.log(`\n[json-formatter] ${filePath}:`)
            if (result.isValid) {
              console.log(`  ✅ Valid JSON`)
              console.log(`  📝 Formatted (${indent} spaces):`)
              console.log(result.formatted?.substring(0, 500))
              if (result.formatted && result.formatted.length > 500) {
                console.log(`     ... (${result.formatted.length} chars total)`)
              }
              
              // Save formatted version
              writeFileSync(filePath, result.formatted)
              console.log(`  💾 Saved formatted version`)
            } else {
              console.log(`  ❌ Invalid JSON: ${result.error}`)
              if (result.path) {
                console.log(`  📍 Error path: ${result.path.join(" > ")}`)
              }
            }
            console.log("")
          } catch (e) {
            console.log(`[json-formatter] Error reading file: ${e}`)
          }
        }
        
        // JSON validate command
        const validateMatch = command.match(/json\s+validate\s+["']?([^\s"']+)["']?/)
        if (validateMatch) {
          const [, filePath] = validateMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const result = formatJSON(content)
            
            console.log(`\n[json-formatter] ${filePath}:`)
            if (result.isValid) {
              console.log(`  ✅ Valid JSON`)
              try {
                const parsed = JSON.parse(content)
                const keys = Object.keys(parsed).length
                console.log(`  📊 Top-level keys: ${keys}`)
              } catch {}
            } else {
              console.log(`  ❌ Invalid JSON: ${result.error}`)
              if (result.path) {
                console.log(`  📍 Error path: ${result.path.join(" > ")}`)
              }
            }
            console.log("")
          } catch (e) {
            console.log(`[json-formatter] Error reading file: ${e}`)
          }
        }
      }
    }
  }
}) satisfies Plugin