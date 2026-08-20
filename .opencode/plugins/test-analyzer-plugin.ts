import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"

interface TestInfo {
  totalTests: number
  testFiles: string[]
  frameworks: string[]
  coverage?: number
}

function detectTestFramework(content: string): string[] {
  const frameworks: string[] = []
  
  if (content.includes("describe(") || content.includes("it(") || content.includes("test(")) {
    frameworks.push("Jest/Mocha/Vitest")
  }
  
  if (content.includes("pytest") || content.includes("@pytest")) {
    frameworks.push("Pytest")
  }
  
  if (content.includes("unittest")) {
    frameworks.push("Unittest")
  }
  
  if (content.includes("@Test")) {
    frameworks.push("JUnit")
  }
  
  if (content.includes("func Test")) {
    frameworks.push("Go Test")
  }
  
  if (content.includes("#[test]")) {
    frameworks.push("Rust Test")
  }
  
  return frameworks
}

function countTests(content: string): number {
  let count = 0
  
  // Jest/Mocha style
  count += (content.match(/\b(it|test)\s*\(/g) || []).length
  
  // Pytest style
  count += (content.match(/def test_/g) || []).length
  
  // JUnit style
  count += (content.match(/@Test/g) || []).length
  
  // Go style
  count += (content.match(/func Test/g) || []).length
  
  return count
}

function findTestFiles(dir: string): string[] {
  const testFiles: string[] = []
  const patterns = ["test", "spec", "Test", "Spec"]
  
  try {
    const { readdirSync } = require("fs")
    const files = readdirSync(dir, { recursive: true })
    
    files.forEach((file: string) => {
      if (patterns.some(p => file.includes(p)) && (
        file.endsWith(".ts") || file.endsWith(".js") ||
        file.endsWith(".py") || file.endsWith(".go") ||
        file.endsWith(".rs") || file.endsWith(".java")
      )) {
        testFiles.push(file)
      }
    })
  } catch {}
  
  return testFiles
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (!filePath) return
        
        const isTestFile = /test|spec|Test|Spec/i.test(filePath)
        
        if (isTestFile) {
          try {
            const content = readFileSync(filePath, "utf-8")
            const frameworks = detectTestFramework(content)
            const testCount = countTests(content)
            
            console.log(`\n[test-analyzer] ${filePath}:`)
            console.log(`  🧪 Frameworks: ${frameworks.join(", ") || "Unknown"}`)
            console.log(`  📊 Tests found: ${testCount}`)
            console.log("")
          } catch {}
        }
      }
    }
  }
}) satisfies Plugin