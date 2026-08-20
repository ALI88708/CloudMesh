import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"
import { diffLines, Change } from "diff"

interface DiffResult {
  additions: number
  deletions: number
  changes: Change[]
}

function compareFiles(file1: string, file2: string): DiffResult | null {
  try {
    const content1 = readFileSync(file1, "utf-8")
    const content2 = readFileSync(file2, "utf-8")
    
    const changes = diffLines(content1, content2)
    let additions = 0
    let deletions = 0
    
    changes.forEach(change => {
      if (change.added) additions += change.count || 0
      if (change.removed) deletions += change.count || 0
    })
    
    return { additions, deletions, changes }
  } catch (e) {
    console.log(`[diff] Error reading files: ${e}`)
    return null
  }
}

function compareStrings(str1: string, str2: string): DiffResult {
  const changes = diffLines(str1, str2)
  let additions = 0
  let deletions = 0
  
  changes.forEach(change => {
    if (change.added) additions += change.count || 0
    if (change.removed) deletions += change.count || 0
  })
  
  return { additions, deletions, changes }
}

function formatDiff(result: DiffResult, file1?: string, file2?: string): void {
  console.log(`\n[diff] Comparison:`)
  if (file1 && file2) {
    console.log(`  Files: ${file1} vs ${file2}`)
  }
  console.log(`  Additions: +${result.additions}`)
  console.log(`  Deletions: -${result.deletions}`)
  console.log(`\n  Changes:`)
  
  result.changes.forEach(change => {
    const prefix = change.added ? "+" : change.removed ? "-" : " "
    const lines = change.value.split("\n").filter(l => l.trim())
    
    lines.forEach(line => {
      const color = change.added ? "\x1b[32m" : change.removed ? "\x1b[31m" : "\x1b[0m"
      console.log(`  ${color}${prefix} ${line}\x1b[0m`)
    })
  })
  
  console.log("")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Compare files command
        const compareMatch = command.match(/diff\s+compare\s+["']([^"']+)["']\s+["']([^"']+)["']/)
        if (compareMatch) {
          const [, file1, file2] = compareMatch
          const result = compareFiles(file1, file2)
          
          if (result) {
            formatDiff(result, file1, file2)
          }
        }
        
        // Compare strings command
        const stringMatch = command.match(/diff\s+strings?\s+["']([^"']+)["']\s+["']([^"']+)["']/)
        if (stringMatch) {
          const [, str1, str2] = stringMatch
          const result = compareStrings(str1, str2)
          formatDiff(result)
        }
        
        // Show differences command
        const showMatch = command.match(/diff\s+show\s+["']([^"']+)["']\s+["']([^"']+)["']/)
        if (showMatch) {
          const [, file1, file2] = showMatch
          try {
            const content1 = readFileSync(file1, "utf-8")
            const content2 = readFileSync(file2, "utf-8")
            
            console.log(`\n[diff] Files:`)
            console.log(`  ${file1}:`)
            console.log(`    Lines: ${content1.split("\n").length}`)
            console.log(`    Size: ${content1.length} bytes`)
            console.log(`  ${file2}:`)
            console.log(`    Lines: ${content2.split("\n").length}`)
            console.log(`    Size: ${content2.length} bytes`)
            console.log("")
          } catch (e) {
            console.log(`[diff] Error: ${e}`)
          }
        }
      }
    }
  }
}) satisfies Plugin