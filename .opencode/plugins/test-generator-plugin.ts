import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync } from "fs"
import { basename, dirname, join } from "path"

interface FunctionInfo {
  name: string
  params: string[]
  returnType?: string
  isAsync: boolean
  line: number
}

function extractFunctions(content: string, lang: string): FunctionInfo[] {
  const functions: FunctionInfo[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    let match: RegExpMatchArray | null = null
    
    // Python
    if (lang === "python") {
      match = line.match(/(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\w+))?\s*:/)
      if (match) {
        const params = match[2].split(",").map(p => p.trim().split(":")[0].split("=")[0].trim())
        functions.push({
          name: match[1],
          params: params.filter(p => p && p !== "self"),
          returnType: match[3],
          isAsync: line.includes("async"),
          line: index + 1
        })
      }
    }
    
    // JavaScript/TypeScript
    if (lang === "javascript" || lang === "typescript") {
      match = line.match(/(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*(\w+))?/)
      if (match) {
        const params = match[2].split(",").map(p => p.trim().split(":")[0].split("=")[0].trim())
        functions.push({
          name: match[1],
          params: params.filter(p => p),
          returnType: match[3],
          isAsync: line.includes("async"),
          line: index + 1
        })
      }
      
      // Arrow functions
      const arrowMatch = line.match(/(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)(?:\s*:\s*(\w+))?\s*=>/)
      if (arrowMatch) {
        const params = arrowMatch[2].split(",").map(p => p.trim().split(":")[0].split("=")[0].trim())
        functions.push({
          name: arrowMatch[1],
          params: params.filter(p => p),
          returnType: arrowMatch[3],
          isAsync: line.includes("async"),
          line: index + 1
        })
      }
    }
  })
  
  return functions
}

function generateTest(func: FunctionInfo, lang: string): string {
  const testName = `test_${func.name}`
  
  if (lang === "python") {
    const params = func.params.map(p => `mock_${p}`).join(", ")
    const asyncPrefix = func.isAsync ? "async " : ""
    const awaitPrefix = func.isAsync ? "await " : ""
    
    return `
${asyncPrefix}def ${testName}():
    """Test ${func.name}"""
    # TODO: Add test implementation
    result = ${awaitPrefix}${func.name}(${params})
    assert result is not None
    # Add more assertions here
`
  }
  
  if (lang === "javascript" || lang === "typescript") {
    const params = func.params.map(p => `mock${p.charAt(0).toUpperCase() + p.slice(1)}`).join(", ")
    const asyncPrefix = func.isAsync ? "async " : ""
    const awaitPrefix = func.isAsync ? "await " : ""
    
    return `
describe('${func.name}', () => {
  ${asyncPrefix}it('should work correctly', ${asyncPrefix}() => {
    // TODO: Add test implementation
    const result = ${awaitPrefix}${func.name}(${params});
    expect(result).toBeDefined();
    // Add more expectations here
  });
});
`
  }
  
  return ""
}

function detectLanguage(filePath: string): string {
  if (filePath.endsWith(".py")) return "python"
  if (filePath.endsWith(".ts") || filePath.endsWith(".tsx")) return "typescript"
  if (filePath.endsWith(".js") || filePath.endsWith(".jsx")) return "javascript"
  return "unknown"
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Generate tests command
        const testMatch = command.match(/generate\s+tests?\s+["']?([^\s"']+)["']?/)
        if (testMatch) {
          const [, filePath] = testMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const lang = detectLanguage(filePath)
            
            if (lang === "unknown") {
              console.log(`[test-gen] Unsupported file type: ${filePath}`)
              return
            }
            
            const functions = extractFunctions(content, lang)
            
            if (functions.length === 0) {
              console.log(`[test-gen] No functions found in ${filePath}`)
              return
            }
            
            console.log(`\n[test-gen] Found ${functions.length} functions in ${filePath}`)
            console.log(`  Generating tests...`)
            
            let testContent = ""
            if (lang === "python") {
              testContent = `import pytest\nfrom ${basename(filePath, ".py")} import *\n\n`
            } else {
              testContent = `import { ${functions.map(f => f.name).join(", ")} } from './${basename(filePath)}';\n\n`
            }
            
            functions.forEach(func => {
              testContent += generateTest(func, lang)
            })
            
            // Generate test file path
            const dir = dirname(filePath)
            const name = basename(filePath)
            const testFile = lang === "python" 
              ? join(dir, `test_${name}`)
              : join(dir, `${name}.test.${lang === "typescript" ? "ts" : "js"}`)
            
            writeFileSync(testFile, testContent)
            console.log(`  ✅ Generated test file: ${testFile}`)
            console.log(`  📝 Functions tested: ${functions.map(f => f.name).join(", ")}`)
            console.log("")
          } catch (e) {
            console.log(`[test-gen] Error: ${e}`)
          }
        }
      }
    }
  }
}) satisfies Plugin