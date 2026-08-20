import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"

interface ImportInfo {
  module: string
  type: "import" | "require" | "from"
  line?: number
}

function analyzeImports(content: string): ImportInfo[] {
  const imports: ImportInfo[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    // ES6 imports
    const es6Match = line.match(/import\s+.*\s+from\s+['"]([^'"]+)['"]/)
    if (es6Match) {
      imports.push({ module: es6Match[1], type: "import", line: index + 1 })
    }
    
    // CommonJS require
    const requireMatch = line.match(/require\s*\(\s*['"]([^'"]+)['"]\s*\)/)
    if (requireMatch) {
      imports.push({ module: requireMatch[1], type: "require", line: index + 1 })
    }
    
    // Python imports
    const pythonMatch = line.match(/(?:from\s+(\S+)\s+)?import\s+(\S+)/)
    if (pythonMatch) {
      imports.push({ module: pythonMatch[1] || pythonMatch[2], type: "from", line: index + 1 })
    }
  })
  
  return imports
}

function detectCircularDeps(imports: ImportInfo[]): string[] {
  const warnings: string[] = []
  const moduleMap = new Map<string, string[]>()
  
  imports.forEach(imp => {
    if (!moduleMap.has(imp.module)) {
      moduleMap.set(imp.module, [])
    }
  })
  
  // Simple circular dependency detection
  moduleMap.forEach((deps, module) => {
    deps.forEach(dep => {
      if (moduleMap.has(dep) && moduleMap.get(dep)?.includes(module)) {
        warnings.push(`Potential circular dependency: ${module} <-> ${dep}`)
      }
    })
  })
  
  return warnings
}

function checkUnusedImports(content: string, imports: ImportInfo[]): string[] {
  const warnings: string[] = []
  
  imports.forEach(imp => {
    const moduleName = imp.module.split("/").pop() || imp.module
    const regex = new RegExp(`\\b${moduleName}\\b`)
    
    // Check if module is used elsewhere in the file
    const lines = content.split("\n")
    const importLine = imp.line ? lines[imp.line - 1] : ""
    const contentWithoutImport = content.replace(importLine, "")
    
    if (!regex.test(contentWithoutImport)) {
      warnings.push(`Potentially unused import: ${imp.module}`)
    }
  })
  
  return warnings
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (!filePath) return
        
        if (filePath.endsWith(".ts") || filePath.endsWith(".js") || 
            filePath.endsWith(".py") || filePath.endsWith(".tsx") ||
            filePath.endsWith(".jsx")) {
          try {
            const content = readFileSync(filePath, "utf-8")
            const imports = analyzeImports(content)
            
            if (imports.length > 0) {
              const unused = checkUnusedImports(content, imports)
              
              if (unused.length > 0) {
                console.log(`\n[import-analyzer] ${filePath}:`)
                console.log(`  📦 Found ${imports.length} imports`)
                console.log(`  ⚠️  Potential unused imports:`)
                unused.slice(0, 5).forEach(w => {
                  console.log(`     ${w}`)
                })
                console.log("")
              }
            }
          } catch {}
        }
      }
    }
  }
}) satisfies Plugin