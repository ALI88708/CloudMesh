import type { Plugin } from "@opencode-ai/plugin"

const COMMON_PATTERNS = {
  email: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
  url: /^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$/,
  phone: /^(\+?\d{1,3}[- ]?)?\d{10}$/,
  ipv4: /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
  ipv6: /^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$/,
  date: /^\d{4}-\d{2}-\d{2}$/,
  time: /^\d{2}:\d{2}(:\d{2})?$/,
  hex: /^#?([a-fA-F0-9]{6}|[a-fA-F0-9]{3})$/,
  alphanumeric: /^[a-zA-Z0-9]+$/,
  numeric: /^\d+$/,
  alpha: /^[a-zA-Z]+$/,
  username: /^[a-zA-Z0-9_-]{3,20}$/,
  password: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/,
  slug: /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
  uuid: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
}

function buildRegex(pattern: string, flags: string = ""): RegExp {
  return new RegExp(pattern, flags)
}

function testRegex(regex: RegExp, testString: string): { matches: RegExpMatchArray[]; matchCount: number } {
  const matches: RegExpMatchArray[] = []
  let match
  
  if (regex.flags.includes("g")) {
    while ((match = regex.exec(testString)) !== null) {
      matches.push(match)
      if (match.index === regex.lastIndex) regex.lastIndex++
    }
  } else {
    match = regex.exec(testString)
    if (match) matches.push(match)
  }
  
  return { matches, matchCount: matches.length }
}

function explainRegex(pattern: string): string[] {
  const explanations: string[] = []
  const chars = pattern.split("")
  
  let i = 0
  while (i < chars.length) {
    const char = chars[i]
    
    switch (char) {
      case "^":
        explanations.push("^ - Start of string")
        break
      case "$":
        explanations.push("$ - End of string")
        break
      case ".":
        explanations.push(". - Any character (except newline)")
        break
      case "*":
        explanations.push("* - Zero or more of previous")
        break
      case "+":
        explanations.push("+ - One or more of previous")
        break
      case "?":
        explanations.push("? - Zero or one of previous")
        break
      case "\\":
        if (i + 1 < chars.length) {
          const next = chars[i + 1]
          switch (next) {
            case "d": explanations.push("\\d - Digit [0-9]"); break
            case "D": explanations.push("\\D - Non-digit"); break
            case "w": explanations.push("\\w - Word character [a-zA-Z0-9_]"); break
            case "W": explanations.push("\\W - Non-word character"); break
            case "s": explanations.push("\\s - Whitespace"); break
            case "S": explanations.push("\\S - Non-whitespace"); break
            case "b": explanations.push("\\b - Word boundary"); break
            default: explanations.push(`\\${next} - Escaped character`); break
          }
          i++
        }
        break
      case "[":
        const closingBracket = pattern.indexOf("]", i)
        if (closingBracket !== -1) {
          const charClass = pattern.substring(i, closingBracket + 1)
          explanations.push(`${charClass} - Character class`)
          i = closingBracket
        }
        break
      case "(":
        explanations.push("( - Start group")
        break
      case ")":
        explanations.push(") - End group")
        break
      case "|":
        explanations.push("| - OR")
        break
      case "{":
        const closingBrace = pattern.indexOf("}", i)
        if (closingBrace !== -1) {
          const quantifier = pattern.substring(i, closingBrace + 1)
          explanations.push(`${quantifier} - Quantifier`)
          i = closingBrace
        }
        break
      default:
        if (/[a-zA-Z0-9]/.test(char)) {
          explanations.push(`"${char}" - Literal character`)
        }
    }
    
    i++
  }
  
  return explanations
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Build and test regex
        const testMatch = command.match(/regex\s+test\s+["']([^"']+)["']\s+["']([^"']+)["'](?:\s+([gimyu]+))?/)
        if (testMatch) {
          const [, pattern, testString, flags = ""] = testMatch
          try {
            const regex = buildRegex(pattern, flags)
            const result = testRegex(regex, testString)
            
            console.log(`\n[regex-builder] Testing: /${pattern}/${flags}`)
            console.log(`  Test string: "${testString}"`)
            console.log(`  Matches: ${result.matchCount}`)
            
            result.matches.slice(0, 5).forEach((match, i) => {
              console.log(`    ${i + 1}: "${match[0]}" at index ${match.index}`)
              if (match.length > 1) {
                match.slice(1).forEach((group, j) => {
                  console.log(`      Group ${j + 1}: "${group}"`)
                })
              }
            })
          } catch (e) {
            console.log(`[regex-builder] Error: ${e}`)
          }
          console.log("")
        }
        
        // Explain regex
        const explainMatch = command.match(/regex\s+explain\s+["']([^"']+)["']/)
        if (explainMatch) {
          const [, pattern] = explainMatch
          const explanations = explainRegex(pattern)
          
          console.log(`\n[regex-builder] Explaining: ${pattern}`)
          explanations.forEach(exp => {
            console.log(`  ${exp}`)
          })
          console.log("")
        }
        
        // Show common patterns
        if (command.match(/regex\s+patterns|regex\s+help/)) {
          console.log(`\n[regex-builder] Common patterns:`)
          Object.entries(COMMON_PATTERNS).forEach(([name, regex]) => {
            console.log(`  ${name.padEnd(12)} ${regex}`)
          })
          console.log("")
        }
        
        // Quick test with common patterns
        const quickMatch = command.match(/regex\s+(\w+)\s+["']([^"']+)["']/)
        if (quickMatch && COMMON_PATTERNS[quickMatch[1] as keyof typeof COMMON_PATTERNS]) {
          const [, type, testString] = quickMatch
          const regex = COMMON_PATTERNS[type as keyof typeof COMMON_PATTERNS]
          const result = testRegex(regex, testString)
          
          console.log(`\n[regex-builder] ${type} test:`)
          console.log(`  Pattern: ${regex}`)
          console.log(`  Test: "${testString}"`)
          console.log(`  Match: ${result.matchCount > 0 ? "✅ Yes" : "❌ No"}`)
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin