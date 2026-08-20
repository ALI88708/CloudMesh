import type { Plugin } from "@opencode-ai/plugin"

interface CronExpression {
  minute: string
  hour: string
  dayOfMonth: string
  month: string
  dayOfWeek: string
}

const CRON_DESCRIPTIONS = {
  minute: "Minute (0-59)",
  hour: "Hour (0-23)",
  dayOfMonth: "Day of month (1-31)",
  month: "Month (1-12)",
  dayOfWeek: "Day of week (0-7, 0 and 7 = Sunday)"
}

const COMMON_CRONS = {
  "every-minute": "* * * * *",
  "every-hour": "0 * * * *",
  "every-day-midnight": "0 0 * * *",
  "every-day-noon": "0 12 * * *",
  "every-week": "0 0 * * 0",
  "every-month": "0 0 1 * *",
  "every-year": "0 0 1 1 *",
  "every-5-minutes": "*/5 * * * *",
  "every-15-minutes": "*/15 * * * *",
  "every-30-minutes": "*/30 * * * *",
  "every-2-hours": "0 */2 * * *",
  "every-6-hours": "0 */6 * * *",
  "every-12-hours": "0 */12 * * *",
  "weekdays-only": "0 9 * * 1-5",
  "weekends-only": "0 9 * * 0,6",
  "business-hours": "0 9-17 * * 1-5"
}

function buildCron(minute: string, hour: string, dayOfMonth: string, month: string, dayOfWeek: string): string {
  return `${minute} ${hour} ${dayOfMonth} ${month} ${dayOfWeek}`
}

function parseCron(cron: string): CronExpression | null {
  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) return null
  
  return {
    minute: parts[0],
    hour: parts[1],
    dayOfMonth: parts[2],
    month: parts[3],
    dayOfWeek: parts[4]
  }
}

function explainCron(cron: string): string[] {
  const parsed = parseCron(cron)
  if (!parsed) return ["Invalid cron expression"]
  
  const explanations: string[] = []
  
  // Explain each part
  const parts: [keyof CronExpression, string][] = [
    ["minute", parsed.minute],
    ["hour", parsed.hour],
    ["dayOfMonth", parsed.dayOfMonth],
    ["month", parsed.month],
    ["dayOfWeek", parsed.dayOfWeek]
  ]
  
  parts.forEach(([field, value]) => {
    let explanation = `${field}: ${value}`
    
    if (value === "*") {
      explanation += " (every)"
    } else if (value.includes("/")) {
      const [start, interval] = value.split("/")
      explanation += ` (every ${interval} ${field === "minute" ? "minutes" : field === "hour" ? "hours" : field === "month" ? "months" : "units"} starting from ${start})`
    } else if (value.includes("-")) {
      const [start, end] = value.split("-")
      explanation += ` (from ${start} to ${end})`
    } else if (value.includes(",")) {
      explanation += ` (at ${value.split(",").join(" and ")}${field === "dayOfWeek" ? " (0=Sun, 1=Mon, ...)" : ""})`
    }
    
    explanations.push(explanation)
  })
  
  // Add human-readable description
  let readable = "Runs "
  
  if (parsed.minute === "*" && parsed.hour === "*") {
    readable += "every minute"
  } else if (parsed.minute === "0" && parsed.hour === "*") {
    readable += "every hour at minute 0"
  } else if (parsed.minute === "0" && parsed.hour === "0") {
    readable += "every day at midnight"
  } else {
    readable += `at ${parsed.hour}:${parsed.minute.padStart(2, "0")}`
    
    if (parsed.dayOfMonth !== "*") {
      readable += ` on day ${parsed.dayOfMonth}`
    }
    if (parsed.month !== "*") {
      readable += ` in month ${parsed.month}`
    }
    if (parsed.dayOfWeek !== "*") {
      const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
      if (parsed.dayOfWeek.includes("-")) {
        const [start, end] = parsed.dayOfWeek.split("-")
        readable += ` from ${days[parseInt(start)]} to ${days[parseInt(end)]}`
      } else {
        readable += ` on ${parsed.dayOfWeek.split(",").map(d => days[parseInt(d)] || d).join(", ")}`
      }
    }
  }
  
  explanations.push("")
  explanations.push(`Human-readable: ${readable}`)
  
  return explanations
}

function getNextRuns(cron: string, count: number = 5): Date[] {
  const parsed = parseCron(cron)
  if (!parsed) return []
  
  const runs: Date[] = []
  const now = new Date()
  
  for (let i = 0; i < count; i++) {
    const next = new Date(now)
    next.setMinutes(next.getMinutes() + i + 1)
    
    // Simple approximation
    if (parsed.minute !== "*") {
      next.setMinutes(parseInt(parsed.minute))
    }
    if (parsed.hour !== "*") {
      next.setHours(parseInt(parsed.hour))
    }
    
    runs.push(next)
  }
  
  return runs
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Build cron expression
        const buildMatch = command.match(/cron\s+build\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/)
        if (buildMatch) {
          const [, minute, hour, dayOfMonth, month, dayOfWeek] = buildMatch
          const cron = buildCron(minute, hour, dayOfMonth, month, dayOfWeek)
          
          console.log(`\n[cron-builder] Built cron expression:`)
          console.log(`  Cron: ${cron}`)
          console.log("")
        }
        
        // Explain cron expression
        const explainMatch = command.match(/cron\s+explain\s+["']([^"']+)["']/)
        if (explainMatch) {
          const [, cron] = explainMatch
          const explanations = explainCron(cron)
          
          console.log(`\n[cron-builder] Explaining: ${cron}`)
          explanations.forEach(exp => {
            console.log(`  ${exp}`)
          })
          console.log("")
        }
        
        // Show common crons
        if (command.match(/cron\s+common|cron\s+presets/)) {
          console.log(`\n[cron-builder] Common cron expressions:`)
          Object.entries(COMMON_CRONS).forEach(([name, cron]) => {
            console.log(`  ${name.padEnd(20)} ${cron}`)
          })
          console.log("")
        }
        
        // Validate cron
        const validateMatch = command.match(/cron\s+validate\s+["']([^"']+)["']/)
        if (validateMatch) {
          const [, cron] = validateMatch
          const parsed = parseCron(cron)
          
          console.log(`\n[cron-builder] Validation: ${cron}`)
          console.log(`  Valid: ${parsed ? "✅ Yes" : "❌ No"}`)
          if (parsed) {
            console.log(`  Minute: ${parsed.minute}`)
            console.log(`  Hour: ${parsed.hour}`)
            console.log(`  Day of month: ${parsed.dayOfMonth}`)
            console.log(`  Month: ${parsed.month}`)
            console.log(`  Day of week: ${parsed.dayOfWeek}`)
          }
          console.log("")
        }
        
        // Quick cron from description
        const descMatch = command.match(/cron\s+for\s+["']([^"']+)["']/)
        if (descMatch) {
          const [, description] = descMatch
          const lowerDesc = description.toLowerCase()
          
          let cron = ""
          let matched = false
          
          if (lowerDesc.includes("every minute")) {
            cron = "* * * * *"
            matched = true
          } else if (lowerDesc.includes("every hour")) {
            cron = "0 * * * *"
            matched = true
          } else if (lowerDesc.includes("every day") && lowerDesc.includes("midnight")) {
            cron = "0 0 * * *"
            matched = true
          } else if (lowerDesc.includes("every week")) {
            cron = "0 0 * * 0"
            matched = true
          } else if (lowerDesc.includes("every month")) {
            cron = "0 0 1 * *"
            matched = true
          } else if (lowerDesc.includes("weekdays")) {
            cron = "0 9 * * 1-5"
            matched = true
          } else if (lowerDesc.includes("weekends")) {
            cron = "0 9 * * 0,6"
            matched = true
          }
          
          if (matched) {
            console.log(`\n[cron-builder] Cron for "${description}":`)
            console.log(`  ${cron}`)
            console.log("")
          } else {
            console.log(`\n[cron-builder] Could not find cron for "${description}"`)
            console.log(`  Try: cron common`)
            console.log("")
          }
        }
      }
    }
  }
}) satisfies Plugin