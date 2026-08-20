import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, readdirSync, existsSync } from "fs"
import { join } from "path"

interface PluginTest {
  name: string
  file: string
  status: "pass" | "fail" | "warning"
  errors: string[]
  warnings: string[]
  hasExport: boolean
  hasHooks: boolean
  syntaxValid: boolean
}

interface TestReport {
  totalPlugins: number
  passed: number
  failed: number
  warnings: number
  plugins: PluginTest[]
}

function getPluginFiles(): string[] {
  const pluginsDir = join(process.cwd(), ".opencode", "plugins")
  
  if (!existsSync(pluginsDir)) {
    return []
  }
  
  return readdirSync(pluginsDir)
    .filter(f => f.endsWith(".ts") || f.endsWith(".js"))
    .map(f => join(pluginsDir, f))
}

function testPlugin(filePath: string): PluginTest {
  const name = filePath.split(/[/\\]/).pop()?.replace(/\.(ts|js)$/, "") || "unknown"
  const errors: string[] = []
  const warnings: string[] = []
  let hasExport = false
  let hasHooks = false
  let syntaxValid = true
  
  try {
    const content = readFileSync(filePath, "utf-8")
    
    // Check for export default
    if (content.includes("export default") || content.includes("module.exports")) {
      hasExport = true
    } else {
      errors.push("Missing default export")
    }
    
    // Check for plugin hooks
    const hookPatterns = [
      "tool.execute.before",
      "tool.execute.after",
      "event",
      "config",
      "chat.message",
      "permission.ask"
    ]
    
    const hasAnyHook = hookPatterns.some(hook => content.includes(hook))
    if (hasAnyHook) {
      hasHooks = true
    } else {
      warnings.push("No plugin hooks found")
    }
    
    // Check for TypeScript syntax issues
    if (filePath.endsWith(".ts")) {
      // Check for common issues
      if (content.includes("require(") && !content.includes("import")) {
        warnings.push("Using require() instead of import")
      }
      
      // Check for missing types
      if (content.includes("function(") && !content.includes(": ")) {
        warnings.push("Missing type annotations")
      }
      
      // Check for console.log (should use proper logging)
      if (content.includes("console.log")) {
        warnings.push("Using console.log - consider proper logging")
      }
    }
    
    // Check for error handling
    if (!content.includes("try") && !content.includes("catch")) {
      warnings.push("No error handling found")
    }
    
    // Check for proper Plugin type usage
    if (content.includes("satisfies Plugin") || content.includes("as Plugin")) {
      // Good
    } else {
      warnings.push("Missing Plugin type assertion")
    }
    
  } catch (e) {
    syntaxValid = false
    errors.push(`File read error: ${e}`)
  }
  
  const status = errors.length > 0 ? "fail" : warnings.length > 0 ? "warning" : "pass"
  
  return {
    name,
    file: filePath,
    status,
    errors,
    warnings,
    hasExport,
    hasHooks,
    syntaxValid
  }
}

function runTests(): TestReport {
  const pluginFiles = getPluginFiles()
  const plugins: PluginTest[] = []
  
  pluginFiles.forEach(file => {
    plugins.push(testPlugin(file))
  })
  
  return {
    totalPlugins: plugins.length,
    passed: plugins.filter(p => p.status === "pass").length,
    failed: plugins.filter(p => p.status === "fail").length,
    warnings: plugins.filter(p => p.status === "warning").length,
    plugins
  }
}

function formatReport(report: TestReport): string {
  const lines: string[] = []
  
  lines.push("╔══════════════════════════════════════════════════════════════╗")
  lines.push("║                 PLUGIN TEST REPORT                         ║")
  lines.push("╚══════════════════════════════════════════════════════════════╝")
  lines.push("")
  lines.push(`📊 Summary:`)
  lines.push(`   Total Plugins: ${report.totalPlugins}`)
  lines.push(`   ✅ Passed: ${report.passed}`)
  lines.push(`   ❌ Failed: ${report.failed}`)
  lines.push(`   ⚠️  Warnings: ${report.warnings}`)
  lines.push("")
  
  if (report.failed > 0) {
    lines.push("❌ FAILED PLUGINS:")
    lines.push("─".repeat(50))
    report.plugins
      .filter(p => p.status === "fail")
      .forEach(p => {
        lines.push(`\n  🔴 ${p.name}`)
        lines.push(`     File: ${p.file}`)
        p.errors.forEach(e => lines.push(`     ❌ ${e}`))
      })
    lines.push("")
  }
  
  if (report.warnings > 0) {
    lines.push("⚠️  WARNINGS:")
    lines.push("─".repeat(50))
    report.plugins
      .filter(p => p.status === "warning")
      .forEach(p => {
        lines.push(`\n  🟡 ${p.name}`)
        p.warnings.forEach(w => lines.push(`     ⚠️  ${w}`))
      })
    lines.push("")
  }
  
  if (report.passed > 0) {
    lines.push("✅ PASSED PLUGINS:")
    lines.push("─".repeat(50))
    report.plugins
      .filter(p => p.status === "pass")
      .forEach(p => {
        lines.push(`  🟢 ${p.name}`)
      })
    lines.push("")
  }
  
  return lines.join("\n")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Test all plugins
        if (command.match(/plugins?\s+test|test\s+plugins?/)) {
          const report = runTests()
          console.log(formatReport(report))
        }
        
        // Test specific plugin
        const testMatch = command.match(/plugins?\s+test\s+["']([^"']+)["']/)
        if (testMatch) {
          const [, pluginName] = testMatch
          const pluginsDir = join(process.cwd(), ".opencode", "plugins")
          const filePath = join(pluginsDir, `${pluginName}.ts`)
          
          if (existsSync(filePath)) {
            const result = testPlugin(filePath)
            console.log(`\n[plugin-tester] Testing: ${result.name}`)
            console.log(`  Status: ${result.status === "pass" ? "✅ PASS" : result.status === "fail" ? "❌ FAIL" : "⚠️  WARNING"}`)
            
            if (result.errors.length) {
              console.log(`  Errors:`)
              result.errors.forEach(e => console.log(`    ❌ ${e}`))
            }
            
            if (result.warnings.length) {
              console.log(`  Warnings:`)
              result.warnings.forEach(w => console.log(`    ⚠️  ${w}`))
            }
          } else {
            console.log(`[plugin-tester] Plugin not found: ${pluginName}`)
          }
          console.log("")
        }
        
        // List all plugins
        if (command.match(/plugins?\s+list|list\s+plugins?/)) {
          const pluginFiles = getPluginFiles()
          
          console.log(`\n[plugin-tester] Installed plugins (${pluginFiles.length}):`)
          pluginFiles.forEach((file, i) => {
            const name = file.split(/[/\\]/).pop()?.replace(/\.(ts|js)$/, "") || "unknown"
            console.log(`  ${i + 1}. ${name}`)
          })
          console.log("")
        }
        
        // Plugin stats
        if (command.match(/plugins?\s+stats|stats\s+plugins?/)) {
          const report = runTests()
          const pluginsDir = join(process.cwd(), ".opencode", "plugins")
          const totalSize = pluginFiles.reduce((sum, file) => {
            try {
              return sum + readFileSync(file).length
            } catch {
              return sum
            }
          }, 0)
          
          console.log(`\n[plugin-tester] Plugin Statistics:`)
          console.log(`  Total plugins: ${report.totalPlugins}`)
          console.log(`  Total size: ${(totalSize / 1024).toFixed(2)} KB`)
          console.log(`  Average size: ${(totalSize / report.totalPlugins / 1024).toFixed(2)} KB`)
          console.log(`  Health: ${report.failed === 0 ? "✅ Good" : "❌ Issues found"}`)
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin