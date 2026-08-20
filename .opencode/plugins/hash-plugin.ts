import type { Plugin } from "@opencode-ai/plugin"
import { createHash } from "crypto"

type HashAlgorithm = "md5" | "sha1" | "sha256" | "sha512"

function generateHash(text: string, algorithm: HashAlgorithm): string {
  return createHash(algorithm).update(text).update(text).digest("hex")
}

function verifyHash(text: string, hash: string, algorithm: HashAlgorithm): boolean {
  const generated = generateHash(text, algorithm)
  return generated === hash
}

function generateFileHash(filePath: string, algorithm: HashAlgorithm): string {
  const { readFileSync } = require("fs")
  const content = readFileSync(filePath)
  return createHash(algorithm).update(content).digest("hex")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Generate hash command
        const generateMatch = command.match(/hash\s+generate\s+["']([^"']+)["']\s+(md5|sha1|sha256|sha512)/)
        if (generateMatch) {
          const [, text, algorithm] = generateMatch as [string, string, HashAlgorithm]
          const hash = generateHash(text, algorithm)
          
          console.log(`\n[hash] Generate:`)
          console.log(`  Input:       ${text}`)
          console.log(`  Algorithm:   ${algorithm.toUpperCase()}`)
          console.log(`  Hash:        ${hash}`)
          console.log("")
        }
        
        // Verify hash command
        const verifyMatch = command.match(/hash\s+verify\s+["']([^"']+)["']\s+["']([^"']+)["']\s+(md5|sha1|sha256|sha512)/)
        if (verifyMatch) {
          const [, text, hash, algorithm] = verifyMatch as [string, string, string, HashAlgorithm]
          const valid = verifyHash(text, hash, algorithm)
          
          console.log(`\n[hash] Verify:`)
          console.log(`  Input:       ${text}`)
          console.log(`  Hash:        ${hash}`)
          console.log(`  Algorithm:   ${algorithm.toUpperCase()}`)
          console.log(`  Valid:       ${valid ? "✅ Yes" : "❌ No"}`)
          console.log("")
        }
        
        // Hash file command
        const fileMatch = command.match(/hash\s+file\s+["']([^"']+)["']\s+(md5|sha1|sha256|sha512)/)
        if (fileMatch) {
          const [, filePath, algorithm] = fileMatch as [string, string, HashAlgorithm]
          try {
            const hash = generateFileHash(filePath, algorithm)
            console.log(`\n[hash] File:`)
            console.log(`  File:        ${filePath}`)
            console.log(`  Algorithm:   ${algorithm.toUpperCase()}`)
            console.log(`  Hash:        ${hash}`)
          } catch (e) {
            console.log(`[hash] Error: ${e}`)
          }
          console.log("")
        }
        
        // Quick hash command (defaults to sha256)
        const quickMatch = command.match(/hash\s+["']([^"']+)["']/)
        if (quickMatch && !command.match(/hash\s+(generate|verify|file)/)) {
          const [, text] = quickMatch
          const hash = generateHash(text, "sha256")
          
          console.log(`\n[hash] Quick:`)
          console.log(`  Input:       ${text}`)
          console.log(`  SHA256:      ${hash}`)
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin