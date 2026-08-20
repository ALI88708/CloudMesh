import type { Plugin } from "@opencode-ai/plugin"

const LOREM_WORDS = [
  "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit",
  "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore",
  "magna", "aliqua", "enim", "ad", "minim", "veniam", "quis", "nostrud",
  "exercitation", "ullamco", "laboris", "nisi", "aliquip", "ex", "ea", "commodo",
  "consequat", "duis", "aute", "irure", "in", "reprehenderit", "voluptate",
  "velit", "esse", "cillum", "fugiat", "nulla", "pariatur", "excepteur", "sint",
  "occaecat", "cupidatat", "non", "proident", "sunt", "culpa", "qui", "officia",
  "deserunt", "mollit", "anim", "id", "est", "laborum", "perspiciatis", "unde",
  "omnis", "iste", "natus", "error", "voluptatem", "accusantium", "doloremque",
  "laudantium", "totam", "rem", "aperiam", "eaque", "ipsa", "quae", "ab", "illo",
  "inventore", "veritatis", "quasi", "architecto", "beatae", "vitae", "dicta",
  "explicabo", "nemo", "ipsam", "quia", "voluptas", "aspernatur", "aut", "odit",
  "fugit", "consequuntur", "magni", "dolores", "eos", "ratione", "sequi", "nesciunt",
  "neque", "porro", "quisquam", "nihil", "impedit", "quo", "minus", "maxime",
  "placeat", "facere", "possimus", "omnis", "voluptas", "assumenda", "repellendus",
  "temporibus", "autem", "quibusdam", "officiis", "debitis", "ratione", "necessitatibus",
  "saepe", "eveniet", "voluptates", "mollitia", "aliquid", "ratione", "voluptatem",
  "nesciunt", "neque", "porro", "quisquam", "nihil", "impedit", "quo", "minus",
  "maxime", "placeat", "facere", "possimus", "omnis", "voluptas", "assumenda",
  "repellendus", "temporibus", "autem", "quibusdam", "officiis", "debitis", "ratione",
  "necessitatibus", "saepe", "eveniet", "voluptates", "mollitia", "aliquid"
]

function generateWord(): string {
  return LOREM_WORDS[Math.floor(Math.random() * LOREM_WORDS.length)]
}

function generateSentence(): string {
  const length = Math.floor(Math.random() * 10) + 5
  const words = Array.from({ length }, generateWord)
  words[0] = words[0].charAt(0).toUpperCase() + words[0].slice(1)
  return words.join(" ") + "."
}

function generateParagraph(): string {
  const sentences = Math.floor(Math.random() * 5) + 3
  return Array.from({ length: sentences }, generateSentence).join(" ")
}

function generateLorem(type: "word" | "sentence" | "paragraph" | "words", count: number): string {
  switch (type) {
    case "word":
      return Array.from({ length: count }, generateWord).join(" ")
    case "sentence":
      return Array.from({ length: count }, generateSentence).join(" ")
    case "paragraph":
      return Array.from({ length: count }, generateParagraph).join("\n\n")
    case "words":
      return Array.from({ length: count }, generateWord).join(" ")
    default:
      return generateParagraph()
  }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Generate Lorem Ipsum command
        const loremMatch = command.match(/lorem\s+(word|sentence|paragraph|words)\s+(\d+)/)
        if (loremMatch) {
          const [, type, countStr] = loremMatch
          const count = parseInt(countStr)
          const result = generateLorem(type as any, count)
          
          console.log(`\n[lorem] Generated ${count} ${type}(s):`)
          console.log(result)
          console.log("")
        }
        
        // Quick Lorem Ipsum (defaults to 3 paragraphs)
        if (command.match(/lorem|lorem\s+ipsum/)) {
          const result = generateLorem("paragraph", 3)
          console.log(`\n[lorem] Generated 3 paragraphs:`)
          console.log(result)
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin