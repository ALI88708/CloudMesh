import type { Plugin } from "@opencode-ai/plugin"

interface SearchResult {
  title: string
  url: string
  snippet: string
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Web search command
        const searchMatch = command.match(/web\s+search\s+["']([^"']+)["'](?:\s+(\d+))?/)
        if (searchMatch) {
          const [, query, numResults = "5"] = searchMatch
          
          console.log(`\n[web-search] Searching for: "${query}"`)
          console.log(`  Results: ${numResults}`)
          console.log(`  Note: Use the websearch tool for actual results`)
          console.log("")
        }
        
        // Quick search
        if (command.match(/search\s+["']([^"']+)["']/) && !command.match(/web\s+search/)) {
          const quickMatch = command.match(/search\s+["']([^"']+)["']/)
          if (quickMatch) {
            const [, query] = quickMatch
            console.log(`\n[web-search] Quick search: "${query}"`)
            console.log(`  Use websearch tool for actual results`)
            console.log("")
          }
        }
      }
    }
  }
}) satisfies Plugin