import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"

interface CommitSuggestion {
  type: string
  scope?: string
  description: string
  body?: string
}

const COMMIT_TYPES = [
  { type: "feat", description: "A new feature" },
  { type: "fix", description: "A bug fix" },
  { type: "docs", description: "Documentation only changes" },
  { type: "style", description: "Code style changes (formatting, etc)" },
  { type: "refactor", description: "Code refactoring" },
  { type: "test", description: "Adding or updating tests" },
  { type: "chore", description: "Maintenance tasks" },
  { type: "perf", description: "Performance improvements" },
  { type: "ci", description: "CI/CD changes" },
  { type: "build", description: "Build system changes" },
]

function analyzeChanges(): { added: string[], modified: string[], deleted: string[] } {
  try {
    const status = execSync("git status --porcelain", { encoding: "utf-8" })
    const lines = status.split("\n").filter(l => l.trim())
    
    const added: string[] = []
    const modified: string[] = []
    const deleted: string[] = []
    
    lines.forEach(line => {
      const status = line.substring(0, 2).trim()
      const file = line.substring(3)
      
      if (status === "A" || status === "??" || status.includes("A")) {
        added.push(file)
      } else if (status === "D" || status.includes("D")) {
        deleted.push(file)
      } else if (status === "M" || status.includes("M")) {
        modified.push(file)
      }
    })
    
    return { added, modified, deleted }
  } catch {
    return { added: [], modified: [], deleted: [] }
  }
}

function suggestCommitType(changes: { added: string[], modified: string[], deleted: string[] }): string {
  const allFiles = [...changes.added, ...changes.modified, ...changes.deleted]
  
  // Check for specific file types
  if (allFiles.some(f => f.includes("test") || f.includes("spec"))) {
    return "test"
  }
  if (allFiles.some(f => f.includes("README") || f.includes("docs"))) {
    return "docs"
  }
  if (allFiles.some(f => f.includes(".github") || f.includes("Dockerfile") || f.includes("docker-compose"))) {
    return "chore"
  }
  if (allFiles.some(f => f.includes(".eslintrc") || f.includes(".prettierrc") || f.includes("tsconfig"))) {
    return "style"
  }
  
  // Check for new files
  if (changes.added.length > 0) {
    return "feat"
  }
  
  // Default to fix for modifications
  if (changes.modified.length > 0) {
    return "fix"
  }
  
  return "chore"
}

function suggestScope(files: string[]): string | undefined {
  if (files.length === 0) return undefined
  
  const firstFile = files[0]
  const parts = firstFile.split("/")
  
  if (parts.length > 1) {
    return parts[0]
  }
  
  return undefined
}

function generateCommitMessage(type: string, scope?: string, changes?: { added: string[], modified: string[], deleted: string[] }): string {
  const scopePart = scope ? `(${scope})` : ""
  const files = [...(changes?.added || []), ...(changes?.modified || [])]
  
  if (files.length === 0) {
    return `${type}${scopePart}: update files`
  }
  
  // Analyze what was changed
  const hasNewFiles = (changes?.added || []).length > 0
  const hasModifiedFiles = (changes?.modified || []).length > 0
  const hasDeletedFiles = (changes?.deleted || []).length > 0
  
  if (hasNewFiles && !hasModifiedFiles && !hasDeletedFiles) {
    return `${type}${scopePart}: add ${files.length} new file(s)`
  }
  
  if (hasDeletedFiles && !hasNewFiles && !hasModifiedFiles) {
    return `${type}${scopePart}: remove ${files.length} file(s)`
  }
  
  if (hasModifiedFiles && !hasNewFiles && !hasDeletedFiles) {
    return `${type}${scopePart}: update ${files.length} file(s)`
  }
  
  return `${type}${scopePart}: update ${files.length} file(s)`
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Git commit suggestion command
        if (command.match(/git\s+commit\s+suggest|commit\s+suggest/)) {
          const changes = analyzeChanges()
          const type = suggestCommitType(changes)
          const scope = suggestScope([...changes.added, ...changes.modified])
          const message = generateCommitMessage(type, scope, changes)
          
          console.log(`\n[git-commit-helper] Suggested commit:`)
          console.log(`  📝 Type: ${type}`)
          if (scope) console.log(`  🎯 Scope: ${scope}`)
          console.log(`  💬 Message: ${message}`)
          console.log(`\n  Changes:`)
          if (changes.added.length) console.log(`     Added: ${changes.added.join(", ")}`)
          if (changes.modified.length) console.log(`     Modified: ${changes.modified.join(", ")}`)
          if (changes.deleted.length) console.log(`     Deleted: ${changes.deleted.join(", ")}`)
          console.log(`\n  To commit: git commit -m "${message}"`)
          console.log("")
        }
        
        // Git commit types command
        if (command.match(/commit\s+types/)) {
          console.log(`\n[git-commit-helper] Commit types:`)
          COMMIT_TYPES.forEach(({ type, description }) => {
            console.log(`  ${type.padEnd(10)} - ${description}`)
          })
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin