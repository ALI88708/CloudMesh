import type { Plugin } from "@opencode-ai/plugin"

const HTML_ENTITIES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
  "/": "&#x2F;",
  "`": "&#x60;",
  "=": "&#x3D;"
}

const REVERSE_HTML_ENTITIES: Record<string, string> = Object.fromEntries(
  Object.entries(HTML_ENTITIES).map(([char, entity]) => [entity, char])
)

function encodeHTMLEntities(text: string): string {
  return text.split("").map(char => HTML_ENTITIES[char] || char).join("")
}

function decodeHTMLEntities(text: string): string {
  let decoded = text
  
  // Decode named entities
  Object.entries(REVERSE_HTML_ENTITIES).forEach(([entity, char]) => {
    decoded = decoded.split(entity).join(char)
  })
  
  // Decode numeric entities
  decoded = decoded.replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code)))
  decoded = decoded.replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(parseInt(code, 16)))
  
  return decoded
}

function escapeHTML(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

function unescapeHTML(text: string): string {
  const textarea = { innerHTML: text } as any
  return textarea.innerHTML
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Encode HTML entities
        const encodeMatch = command.match(/html\s+encode\s+["']([^"']+)["']/)
        if (encodeMatch) {
          const [, text] = encodeMatch
          console.log(`\n[html-entity] Encoding:`)
          console.log(`  Input:  ${text}`)
          console.log(`  Output: ${encodeHTMLEntities(text)}`)
          console.log("")
        }
        
        // Decode HTML entities
        const decodeMatch = command.match(/html\s+decode\s+["']([^"']+)["']/)
        if (decodeMatch) {
          const [, text] = decodeMatch
          console.log(`\n[html-entity] Decoding:`)
          console.log(`  Input:  ${text}`)
          console.log(`  Output: ${decodeHTMLEntities(text)}`)
          console.log("")
        }
        
        // Escape HTML
        const escapeMatch = command.match(/html\s+escape\s+["']([^"']+)["']/)
        if (escapeMatch) {
          const [, text] = escapeMatch
          console.log(`\n[html-entity] Escaping:`)
          console.log(`  Input:  ${text}`)
          console.log(`  Output: ${escapeHTML(text)}`)
          console.log("")
        }
        
        // Show common entities
        if (command.match(/html\s+entities|html\s+help/)) {
          console.log(`\n[html-entity] Common HTML entities:`)
          Object.entries(HTML_ENTITIES).forEach(([char, entity]) => {
            console.log(`  ${char} -> ${entity}`)
          })
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin