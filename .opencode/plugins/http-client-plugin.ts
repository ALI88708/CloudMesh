import type { Plugin } from "@opencode-ai/plugin"

interface HTTPRequest {
  method: string
  url: string
  headers: Record<string, string>
  body?: string
  timestamp: string
}

function formatRequest(req: HTTPRequest): string {
  return `${req.method} ${req.url}\nHeaders: ${JSON.stringify(req.headers, null, 2)}${req.body ? `\nBody: ${req.body}` : ""}`
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // HTTP GET command
        const getMatch = command.match(/http\s+get\s+["']([^"']+)["'](?:\s+--header\s+["']([^"']+)["'])?/)
        if (getMatch) {
          const [, url, header] = getMatch
          console.log(`\n[http-client] GET ${url}`)
          if (header) console.log(`  Header: ${header}`)
          console.log(`  Note: Use webfetch tool for actual requests`)
          console.log("")
        }
        
        // HTTP POST command
        const postMatch = command.match(/http\s+post\s+["']([^"']+)["']\s+--data\s+["']([^"']+)["'](?:\s+--header\s+["']([^"']+)["'])?/)
        if (postMatch) {
          const [, url, data, header] = postMatch
          console.log(`\n[http-client] POST ${url}`)
          console.log(`  Data: ${data}`)
          if (header) console.log(`  Header: ${header}`)
          console.log(`  Note: Use webfetch tool for actual requests`)
          console.log("")
        }
        
        // HTTP status check
        const statusMatch = command.match(/http\s+status\s+["']([^"']+)["']/)
        if (statusMatch) {
          const [, url] = statusMatch
          console.log(`\n[http-client] Checking status: ${url}`)
          console.log(`  Note: Use webfetch tool for actual status check`)
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin