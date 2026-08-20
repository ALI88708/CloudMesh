import type { Plugin } from "@opencode-ai/plugin"

function encodeBase64(text: string): string {
  return Buffer.from(text).toString("base64")
}

function decodeBase64(encoded: string): string {
  try {
    return Buffer.from(encoded, "base64").toString("utf-8")
  } catch {
    throw new Error("Invalid Base64 string")
  }
}

function isBase64(str: string): boolean {
  try {
    const decoded = Buffer.from(str, "base64").toString("base64")
    return decoded === str
  } catch {
    return false
  }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Base64 encode command
        const encodeMatch = command.match(/base64\s+encode\s+["']([^"']+)["']/)
        if (encodeMatch) {
          const [, text] = encodeMatch
          const encoded = encodeBase64(text)
          console.log(`\n[base64] Encoding:`)
          console.log(`  Input:  ${text}`)
          console.log(`  Output: ${encoded}`)
          console.log("")
        }
        
        // Base64 decode command
        const decodeMatch = command.match(/base64\s+decode\s+["']([^"']+)["']/)
        if (decodeMatch) {
          const [, encoded] = decodeMatch
          try {
            const decoded = decodeBase64(encoded)
            console.log(`\n[base64] Decoding:`)
            console.log(`  Input:  ${encoded}`)
            console.log(`  Output: ${decoded}`)
          } catch (e) {
            console.log(`[base64] Error: ${e}`)
          }
          console.log("")
        }
        
        // Check if string is Base64
        const checkMatch = command.match(/base64\s+check\s+["']([^"']+)["']/)
        if (checkMatch) {
          const [, str] = checkMatch
          const valid = isBase64(str)
          console.log(`\n[base64] Check:`)
          console.log(`  String: ${str}`)
          console.log(`  Valid Base64: ${valid ? "✅ Yes" : "❌ No"}`)
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin