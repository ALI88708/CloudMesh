import type { Plugin } from "@opencode-ai/plugin"

interface RegexTest {
  pattern: string
  flags: string
  testString: string
  matches: RegExpMatchArray[]
  isValid: boolean
  error?: string
}

function testRegex(pattern: string, flags: string, testString: string): RegexTest {
  try {
    const regex = new RegExp(pattern, flags)
    const matches: RegExpMatchArray[] = []
    let match
    
    if (flags.includes("g")) {
      while ((match = regex.exec(testString)) !== null) {
        matches.push(match)
        if (match.index === regex.lastIndex) {
          regex.lastIndex++
        }
      }
    } else {
      match = regex.exec(testString)
      if (match) matches.push(match)
    }
    
    return { pattern, flags, testString, matches, isValid: true }
  } catch (e) {
    return {
      pattern,
      flags,
      testString,
      matches: [],
      isValid: false,
      error: e instanceof Error ? e.message : "Invalid regex"
    }
  }
}

function formatMatch(match: RegExpMatchArray, index: number): string {
  const groups = match.slice(1).map((g, i) => `Group ${i + 1}: ${g}`).join(", ")
  return `Match ${index + 1}: "${match[0]}" at index ${match.index}${groups ? ` (${groups})` : ""}`
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Check for regex test command
        const regexMatch = command.match(/regex\s+test\s+["'](.+?)["']\s+["'](.+?)["'](?:\s+([gimyu]+))?/)
        if (regexMatch) {
          const [, pattern, testString, flags = ""] = regexMatch
          const result = testRegex(pattern, flags, testString)
          
          console.log(`\n[regex-tester] Testing: /${pattern}/${flags}`)
          console.log(`  Test string: "${testString}"`)
          
          if (!result.isValid) {
            console.log(`  ❌ Error: ${result.error}`)
          } else if (result.matches.length === 0) {
            console.log(`  ⚪ No matches found`)
          } else {
            console.log(`  ✅ Found ${result.matches.length} match(es):`)
            result.matches.slice(0, 5).forEach((m, i) => {
              console.log(`     ${formatMatch(m, i)}`)
            })
            if (result.matches.length > 5) {
              console.log(`     ... and ${result.matches.length - 5} more`)
            }
          }
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin