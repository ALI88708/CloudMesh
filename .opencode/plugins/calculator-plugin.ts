import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 15000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

export default {
  name: "calculator",
  description: "Evaluate mathematical expressions",
  commands: [
    {
      name: "calc",
      description: "Evaluate a math expression (e.g. calc 2+2, calc sqrt(144), calc sin(3.14))",
      handler: (args: string) => {
        if (!args) return "Usage: calc <expression>\nExamples: calc 2+2, calc sqrt(144), calc sin(3.14), calc 2^10"
        const expr = args
          .replace(/\^/g, "**")
          .replace(/sqrt\(/g, "[Math]::Sqrt(")
          .replace(/sin\(/g, "[Math]::Sin(")
          .replace(/cos\(/g, "[Math]::Cos(")
          .replace(/tan\(/g, "[Math]::Tan(")
          .replace(/log\(/g, "[Math]::Log10(")
          .replace(/ln\(/g, "[Math]::Log(")
          .replace(/abs\(/g, "[Math]::Abs(")
          .replace(/pi/gi, "[Math]::PI")
          .replace(/e(?![a-z])/gi, "[Math]::E")
        const result = runCommand(`powershell -Command "[Math]::Round(($expr), 10)"`)
        if (!result || result.includes("error") || result.includes("Error")) {
          return `Error evaluating: ${args}`
        }
        return `${args} = ${result}`
      },
    },
  ],
} satisfies Plugin
