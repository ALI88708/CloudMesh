import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"

function runCommand(cmd: string): string {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 30000 }).trim()
  } catch (e: any) {
    return e.stdout || e.stderr || ""
  }
}

export default {
  name: "weather",
  description: "Show current weather information",
  commands: [
    {
      name: "weather",
      description: "Show current weather using wttr.in",
      handler: () => {
        const result = runCommand('curl -s "wttr.in/?format=4"')
        if (result) return result
        const detailed = runCommand('curl -s "wttr.in/?format=%l:+%c+%t+%h+%w"')
        return detailed || "Could not fetch weather data. Check your internet connection."
      },
    },
  ],
} satisfies Plugin
