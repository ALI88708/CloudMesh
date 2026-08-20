import type { Plugin } from "@opencode-ai/plugin"

interface FetchResult {
  url: string
  status: number
  contentType: string
  contentLength: number
  timestamp: string
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // URL fetch command
        const fetchMatch = command.match(/url\s+fetch\s+["']([^"']+)["'](?:\s+--format\s+(markdown|text|html))?/)
        if (fetchMatch) {
          const [, url, format = "markdown"] = fetchMatch
          
          console.log(`\n[url-fetcher] Fetching: ${url}`)
          console.log(`  Format: ${format}`)
          console.log(`  Note: Use the webfetch tool for actual content`)
          console.log("")
        }
        
        // URL info command
        const infoMatch = command.match(/url\s+info\s+["']([^"']+)["']/)
        if (infoMatch) {
          const [, url] = infoMatch
          try {
            const urlObj = new URL(url)
            console.log(`\n[url-fetcher] URL Info:`)
            console.log(`  Protocol: ${urlObj.protocol}`)
            console.log(`  Host: ${urlObj.hostname}`)
            console.log(`  Port: ${urlObj.port || "default"}`)
            console.log(`  Path: ${urlObj.pathname}`)
            if (urlObj.search) console.log(`  Query: ${urlObj.search}`)
            if (urlObj.hash) console.log(`  Hash: ${urlObj.hash}`)
          } catch {
            console.log(`[url-fetcher] Invalid URL: ${url}`)
          }
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin