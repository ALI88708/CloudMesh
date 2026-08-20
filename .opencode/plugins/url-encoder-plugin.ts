import type { Plugin } from "@opencode-ai/plugin"

function encodeURL(url: string): string {
  return encodeURI(url)
}

function decodeURL(url: string): string {
  try {
    return decodeURI(url)
  } catch {
    return "Invalid URL"
  }
}

function encodeComponent(component: string): string {
  return encodeURIComponent(component)
}

function decodeComponent(component: string): string {
  try {
    return decodeURIComponent(component)
  } catch {
    return "Invalid component"
  }
}

function parseQueryString(queryString: string): Record<string, string> {
  const params: Record<string, string> = {}
  
  queryString.split("&").forEach(pair => {
    const [key, value] = pair.split("=")
    if (key) {
      params[decodeURIComponent(key)] = value ? decodeURIComponent(value) : ""
    }
  })
  
  return params
}

function buildQueryString(params: Record<string, string>): string {
  return Object.entries(params)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("&")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // URL encode
        const encodeMatch = command.match(/url\s+encode\s+["']([^"']+)["']/)
        if (encodeMatch) {
          const [, url] = encodeMatch
          console.log(`\n[url-encoder] Encoding:`)
          console.log(`  Input:  ${url}`)
          console.log(`  Output: ${encodeURL(url)}`)
          console.log("")
        }
        
        // URL decode
        const decodeMatch = command.match(/url\s+decode\s+["']([^"']+)["']/)
        if (decodeMatch) {
          const [, url] = decodeMatch
          console.log(`\n[url-encoder] Decoding:`)
          console.log(`  Input:  ${url}`)
          console.log(`  Output: ${decodeURL(url)}`)
          console.log("")
        }
        
        // Component encode
        const compEncodeMatch = command.match(/url\s+component\s+encode\s+["']([^"']+)["']/)
        if (compEncodeMatch) {
          const [, component] = compEncodeMatch
          console.log(`\n[url-encoder] Component encoding:`)
          console.log(`  Input:  ${component}`)
          console.log(`  Output: ${encodeComponent(component)}`)
          console.log("")
        }
        
        // Component decode
        const compDecodeMatch = command.match(/url\s+component\s+decode\s+["']([^"']+)["']/)
        if (compDecodeMatch) {
          const [, component] = compDecodeMatch
          console.log(`\n[url-encoder] Component decoding:`)
          console.log(`  Input:  ${component}`)
          console.log(`  Output: ${decodeComponent(component)}`)
          console.log("")
        }
        
        // Parse query string
        const parseMatch = command.match(/url\s+parse\s+["']([^"']+)["']/)
        if (parseMatch) {
          const [, queryString] = parseMatch
          const params = parseQueryString(queryString)
          
          console.log(`\n[url-encoder] Query string:`)
          console.log(`  Input: ${queryString}`)
          console.log(`  Parsed:`)
          Object.entries(params).forEach(([key, value]) => {
            console.log(`    ${key}: ${value}`)
          })
          console.log("")
        }
        
        // Build query string
        const buildMatch = command.match(/url\s+build\s+query\s+["']([^"']+)["'](?:\s+["']([^"']+)["'])*/)
        if (buildMatch) {
          const params: Record<string, string> = {}
          const matches = command.matchAll(/["']([^"']+)["']\s+["']([^"']+)["']/g)
          
          for (const match of matches) {
            if (match[1] !== buildMatch[1]) {
              params[match[1]] = match[2]
            }
          }
          
          if (Object.keys(params).length > 0) {
            const queryString = buildQueryString(params)
            console.log(`\n[url-encoder] Built query string:`)
            console.log(`  ${queryString}`)
            console.log("")
          }
        }
      }
    }
  }
}) satisfies Plugin