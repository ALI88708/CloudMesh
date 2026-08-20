import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs"
import { join } from "path"

const SNIPPETS_DIR = ".opencode/snippets"

interface Snippet {
  name: string
  description: string
  language: string
  code: string
  tags: string[]
  createdAt: string
  updatedAt: string
}

function ensureSnippetsDir() {
  if (!existsSync(SNIPPETS_DIR)) {
    mkdirSync(SNIPPETS_DIR, { recursive: true })
  }
}

function getSnippetPath(name: string): string {
  return join(SNIPPETS_DIR, `${name}.json`)
}

function saveSnippet(snippet: Snippet) {
  ensureSnippetsDir()
  const path = getSnippetPath(snippet.name)
  writeFileSync(path, JSON.stringify(snippet, null, 2))
}

function loadSnippet(name: string): Snippet | null {
  const path = getSnippetPath(name)
  if (!existsSync(path)) return null
  
  try {
    return JSON.parse(readFileSync(path, "utf-8"))
  } catch {
    return null
  }
}

function listSnippets(): Snippet[] {
  ensureSnippetsDir()
  const { readdirSync } = require("fs")
  const files = readdirSync(SNIPPETS_DIR).filter((f: string) => f.endsWith(".json"))
  
  return files.map((f: string) => {
    try {
      return JSON.parse(readFileSync(join(SNIPPETS_DIR, f), "utf-8"))
    } catch {
      return null
    }
  }).filter(Boolean)
}

function searchSnippets(query: string): Snippet[] {
  const snippets = listSnippets()
  const lowerQuery = query.toLowerCase()
  
  return snippets.filter(s => 
    s.name.toLowerCase().includes(lowerQuery) ||
    s.description.toLowerCase().includes(lowerQuery) ||
    s.tags.some(t => t.toLowerCase().includes(lowerQuery))
  )
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Save snippet command
        const saveMatch = command.match(/snippet\s+save\s+["']([^"']+)["']\s+["']([^"']+)["'](?:\s+([a-z]+))?(?:\s+--tags?\s+([^\s]+(?:\s+[^\s]+)*))?/)
        if (saveMatch) {
          const [, name, code, language = "text", tagsStr = ""] = saveMatch
          const tags = tagsStr ? tagsStr.split(",").map(t => t.trim()) : []
          
          const snippet: Snippet = {
            name,
            description: `Code snippet: ${name}`,
            language,
            code,
            tags,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
          }
          
          saveSnippet(snippet)
          console.log(`\n[snippet-manager] Saved snippet: ${name}`)
          console.log(`  Language: ${language}`)
          console.log(`  Tags: ${tags.join(", ") || "none"}`)
          console.log("")
        }
        
        // List snippets command
        if (command.match(/snippet\s+list|snippets\s+list/)) {
          const snippets = listSnippets()
          console.log(`\n[snippet-manager] Snippets (${snippets.length} total):`)
          snippets.forEach(s => {
            console.log(`  📝 ${s.name} (${s.language})`)
            if (s.tags.length) console.log(`     Tags: ${s.tags.join(", ")}`)
          })
          console.log("")
        }
        
        // Search snippets command
        const searchMatch = command.match(/snippet\s+search\s+["']([^"']+)["']/)
        if (searchMatch) {
          const [, query] = searchMatch
          const results = searchSnippets(query)
          
          console.log(`\n[snippet-manager] Search results for "${query}" (${results.length} found):`)
          results.forEach(s => {
            console.log(`  📝 ${s.name} (${s.language})`)
            console.log(`     ${s.code.substring(0, 50)}...`)
          })
          console.log("")
        }
        
        // Get snippet command
        const getMatch = command.match(/snippet\s+get\s+["']([^"']+)["']/)
        if (getMatch) {
          const [, name] = getMatch
          const snippet = loadSnippet(name)
          
          if (snippet) {
            console.log(`\n[snippet-manager] ${snippet.name}:`)
            console.log(`  Language: ${snippet.language}`)
            console.log(`  Tags: ${snippet.tags.join(", ") || "none"}`)
            console.log(`  Created: ${snippet.createdAt}`)
            console.log(`\n  Code:`)
            console.log(snippet.code)
            console.log("")
          } else {
            console.log(`[snippet-manager] Snippet not found: ${name}`)
          }
        }
        
        // Delete snippet command
        const deleteMatch = command.match(/snippet\s+delete\s+["']([^"']+)["']/)
        if (deleteMatch) {
          const [, name] = deleteMatch
          const path = getSnippetPath(name)
          
          if (existsSync(path)) {
            const { unlinkSync } = require("fs")
            unlinkSync(path)
            console.log(`[snippet-manager] Deleted snippet: ${name}`)
          } else {
            console.log(`[snippet-manager] Snippet not found: ${name}`)
          }
        }
      }
    }
  }
}) satisfies Plugin