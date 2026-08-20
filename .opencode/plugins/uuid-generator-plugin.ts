import type { Plugin } from "@opencode-ai/plugin"
import { randomUUID } from "crypto"

function generateUUID(version: 1 | 4 = 4): string {
  if (version === 4) {
    return randomUUID()
  }
  
  // UUID v1 (timestamp-based)
  const timestamp = Date.now()
  const clockSeq = Math.floor(Math.random() * 16384)
  const node = Array.from({ length: 6 }, () => Math.floor(Math.random() * 256))
  
  const timeLow = timestamp & 0xffffffff
  const timeMid = (timestamp / 0x100000000) & 0xffff
  const timeHi = ((timestamp / 0x1000000000000) & 0x0fff) | 0x1000
  
  return [
    timeLow.toString(16).padStart(8, "0"),
    timeMid.toString(16).padStart(4, "0"),
    timeHi.toString(16).padStart(4, "0"),
    ((clockSeq & 0x3fff) | 0x8000).toString(16).padStart(4, "0"),
    node.map(b => b.toString(16).padStart(2, "0")).join("")
  ].join("-")
}

function validateUUID(uuid: string): { valid: boolean; version?: number; variant?: string } {
  const regex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
  
  if (!regex.test(uuid)) {
    return { valid: false }
  }
  
  const parts = uuid.split("-")
  const version = parseInt(parts[2][0], 16)
  const variant = parseInt(parts[3][0], 16)
  
  let variantName = "Unknown"
  if (variant >= 8 && variant <= 11) variantName = "RFC 4122"
  else if (variant >= 12 && variant <= 13) variantName: "Microsoft"
  else if (variant >= 14 && variant <= 15) variantName = "Reserved"
  
  return { valid: true, version, variant: variantName }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Generate UUID command
        const genMatch = command.match(/uuid\s+generate\s*(v[14])?/)
        if (genMatch) {
          const version = genMatch[1] === "v1" ? 1 : 4
          const uuid = generateUUID(version)
          
          console.log(`\n[uuid-gen] Generated UUID v${version}:`)
          console.log(`  UUID: ${uuid}`)
          console.log("")
        }
        
        // Validate UUID command
        const valMatch = command.match(/uuid\s+validate\s+["']([^"']+)["']/)
        if (valMatch) {
          const [, uuid] = valMatch
          const result = validateUUID(uuid)
          
          console.log(`\n[uuid-gen] UUID Validation:`)
          console.log(`  UUID: ${uuid}`)
          console.log(`  Valid: ${result.valid ? "✅ Yes" : "❌ No"}`)
          if (result.valid) {
            console.log(`  Version: ${result.version}`)
            console.log(`  Variant: ${result.variant}`)
          }
          console.log("")
        }
        
        // Generate multiple UUIDs
        const multiMatch = command.match(/uuid\s+generate\s+(\d+)/)
        if (multiMatch) {
          const count = Math.min(parseInt(multiMatch[1]), 100)
          
          console.log(`\n[uuid-gen] Generated ${count} UUIDs:`)
          for (let i = 0; i < count; i++) {
            console.log(`  ${i + 1}. ${generateUUID()}`)
          }
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin