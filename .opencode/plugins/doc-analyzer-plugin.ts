import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"

interface Documentation {
  functions: Array<{ name: string; hasDocs: boolean; line: number }>
  classes: Array<{ name: string; hasDocs: boolean; line: number }>
  modules: Array<{ name: string; hasDocs: boolean; line: number }>
  missingDocs: string[]
}

function analyzeDocumentation(content: string, lang: string): Documentation {
  const functions: Documentation["functions"] = []
  const classes: Documentation["classes"] = []
  const modules: Documentation["modules"] = []
  const missingDocs: string[] = []
  
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    // Python
    if (lang === "python") {
      const funcMatch = line.match(/def\s+(\w+)\s*\(/)
      if (funcMatch) {
        const hasDocs = index > 0 && (
          lines[index - 1].includes('"""') || 
          lines[index - 1].includes("'''") ||
          lines[index - 2]?.includes('"""') ||
          lines[index - 2]?.includes("'''")
        )
        functions.push({ name: funcMatch[1], hasDocs, line: index + 1 })
        if (!hasDocs) missingDocs.push(`Function ${funcMatch[1]} at line ${index + 1}`)
      }
      
      const classMatch = line.match(/class\s+(\w+)/)
      if (classMatch) {
        const hasDocs = index > 0 && (
          lines[index - 1].includes('"""') || 
          lines[index - 1].includes("'''")
        )
        classes.push({ name: classMatch[1], hasDocs, line: index + 1 })
        if (!hasDocs) missingDocs.push(`Class ${classMatch[1]} at line ${index + 1}`)
      }
    }
    
    // JavaScript/TypeScript
    if (lang === "javascript" || lang === "typescript") {
      const funcMatch = line.match(/(?:export\s+)?(?:async\s+)?function\s+(\w+)/)
      if (funcMatch) {
        const hasDocs = index > 0 && lines[index - 1].includes("*/")
        functions.push({ name: funcMatch[1], hasDocs, line: index + 1 })
        if (!hasDocs) missingDocs.push(`Function ${funcMatch[1]} at line ${index + 1}`)
      }
      
      const classMatch = line.match(/class\s+(\w+)/)
      if (classMatch) {
        const hasDocs = index > 0 && lines[index - 1].includes("*/")
        classes.push({ name: classMatch[1], hasDocs, line: index + 1 })
        if (!hasDocs) missingDocs.push(`Class ${classMatch[1]} at line ${index + 1}`)
      }
    }
  })
  
  return { functions, classes, modules, missingDocs }
}

function detectLanguage(filePath: string): string {
  if (filePath.endsWith(".py")) return "python"
  if (filePath.endsWith(".ts") || filePath.endsWith(".tsx")) return "typescript"
  if (filePath.endsWith(".js") || filePath.endsWith(".jsx")) return "javascript"
  if (filePath.endsWith(".go")) return "go"
  if (filePath.endsWith(".rs")) return "rust"
  return "unknown"
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (!filePath) return
        
        const lang = detectLanguage(filePath)
        if (lang === "unknown") return
        
        try {
          const content = readFileSync(filePath, "utf-8")
          const docs = analyzeDocumentation(content, lang)
          
          if (docs.functions.length > 0 || docs.classes.length > 0) {
            const functionsWithoutDocs = docs.functions.filter(f => !f.hasDocs).length
            const classesWithoutDocs = docs.classes.filter(c => !c.hasDocs).length
            
            if (functionsWithoutDocs > 0 || classesWithoutDocs > 0) {
              console.log(`\n[doc-analyzer] ${filePath}:`)
              console.log(`  📚 Documentation coverage:`)
              console.log(`     Functions: ${docs.functions.length - functionsWithoutDocs}/${docs.functions.length} documented`)
              console.log(`     Classes: ${docs.classes.length - classesWithoutDocs}/${docs.classes.length} documented`)
              
              if (docs.missingDocs.length > 0) {
                console.log(`  ⚠️  Missing documentation:`)
                docs.missingDocs.slice(0, 5).forEach(d => {
                  console.log(`     ${d}`)
                })
              }
              console.log("")
            }
          }
        } catch {}
      }
    }
  }
}) satisfies Plugin