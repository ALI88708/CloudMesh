import type { Plugin } from "@opencode-ai/plugin"
import { randomBytes, randomInt } from "crypto"

interface PasswordOptions {
  length: number
  uppercase: boolean
  lowercase: boolean
  numbers: boolean
  symbols: boolean
  excludeAmbiguous: boolean
}

const UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
const LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
const NUMBERS = "0123456789"
const SYMBOLS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
const AMBIGUOUS = "Il1O0"

function generatePassword(options: PasswordOptions): string {
  let chars = ""
  
  if (options.uppercase) chars += UPPERCASE
  if (options.lowercase) chars += LOWERCASE
  if (options.numbers) chars += NUMBERS
  if (options.symbols) chars += SYMBOLS
  
  if (options.excludeAmbiguous) {
    chars = chars.split("").filter(c => !AMBIGUOUS.includes(c)).join("")
  }
  
  if (chars.length === 0) {
    chars = LOWERCASE
  }
  
  let password = ""
  const array = new Uint32Array(options.length)
  randomBytes(array.length).forEach((byte, i) => {
    array[i] = byte
  })
  
  for (let i = 0; i < options.length; i++) {
    password += chars[array[i] % chars.length]
  }
  
  return password
}

function calculateStrength(password: string): { score: number; label: string; color: string } {
  let score = 0
  
  if (password.length >= 8) score++
  if (password.length >= 12) score++
  if (password.length >= 16) score++
  if (/[a-z]/.test(password)) score++
  if (/[A-Z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  if (/[^a-zA-Z0-9]/.test(password)) score++
  
  if (score <= 2) return { score, label: "Weak", color: "\x1b[31m" }
  if (score <= 4) return { score, label: "Medium", color: "\x1b[33m" }
  if (score <= 5) return { score, label: "Strong", color: "\x1b[32m" }
  return { score, label: "Very Strong", color: "\x1b[32m" }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Generate password command
        const genMatch = command.match(/password\s+generate\s*(\d+)?(?:\s+--no-uppercase)?(?:\s+--no-lowercase)?(?:\s+--no-numbers)?(?:\s+--no-symbols)?(?:\s+--exclude-ambiguous)?/)
        if (genMatch) {
          const length = parseInt(genMatch[1]) || 16
          const options: PasswordOptions = {
            length,
            uppercase: !command.includes("--no-uppercase"),
            lowercase: !command.includes("--no-lowercase"),
            numbers: !command.includes("--no-numbers"),
            symbols: !command.includes("--no-symbols"),
            excludeAmbiguous: command.includes("--exclude-ambiguous")
          }
          
          const password = generatePassword(options)
          const strength = calculateStrength(password)
          
          console.log(`\n[password-gen] Generated password:`)
          console.log(`  Password: ${password}`)
          console.log(`  Length: ${password.length}`)
          console.log(`  Strength: ${strength.color}${strength.label}\x1b[0m (${strength.score}/7)`)
          console.log("")
        }
        
        // Check password strength
        const checkMatch = command.match(/password\s+strength\s+["']([^"']+)["']/)
        if (checkMatch) {
          const [, password] = checkMatch
          const strength = calculateStrength(password)
          
          console.log(`\n[password-gen] Password strength:`)
          console.log(`  Password: ${"*".repeat(password.length)} (${password.length} chars)`)
          console.log(`  Strength: ${strength.color}${strength.label}\x1b[0m (${strength.score}/7)`)
          console.log("")
        }
        
        // Generate passphrase
        const passMatch = command.match(/password\s+passphrase\s*(\d+)?/)
        if (passMatch) {
          const words = parseInt(passMatch[1]) || 4
          const wordList = ["apple", "banana", "cherry", "dog", "elephant", "frog", "grape", "house", "ice", "juice", "kite", "lemon", "mango", "nut", "orange", "pear", "queen", "rain", "sun", "tree", "umbrella", "violet", "water", "xylophone", "yacht", "zebra"]
          
          const passphrase = Array.from({ length: words }, () => 
            wordList[Math.floor(Math.random() * wordList.length)]
          ).join("-")
          
          console.log(`\n[password-gen] Generated passphrase:`)
          console.log(`  Passphrase: ${passphrase}`)
          console.log(`  Words: ${words}`)
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin