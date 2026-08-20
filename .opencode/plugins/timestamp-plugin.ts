import type { Plugin } from "@opencode-ai/plugin"

function convertTimestamp(timestamp: string): void {
  const date = new Date(timestamp)
  
  if (isNaN(date.getTime())) {
    console.log(`[timestamp] Invalid timestamp: ${timestamp}`)
    return
  }
  
  console.log(`\n[timestamp] Converting: ${timestamp}`)
  console.log(`  ISO 8601:   ${date.toISOString()}`)
  console.log(`  UTC:        ${date.toUTCString()}`)
  console.log(`  Locale:     ${date.toLocaleString()}`)
  console.log(`  Unix (s):   ${Math.floor(date.getTime() / 1000)}`)
  console.log(`  Unix (ms):  ${date.getTime()}`)
  console.log(`  Relative:   ${getRelativeTime(date)}`)
  console.log("")
}

function convertUnix(unix: string): void {
  const timestamp = parseInt(unix)
  
  if (isNaN(timestamp)) {
    console.log(`[timestamp] Invalid Unix timestamp: ${unix}`)
    return
  }
  
  // Auto-detect seconds vs milliseconds
  const isMilliseconds = timestamp > 1e12
  const date = new Date(isMilliseconds ? timestamp : timestamp * 1000)
  
  console.log(`\n[timestamp] Converting Unix: ${unix}`)
  console.log(`  ISO 8601:   ${date.toISOString()}`)
  console.log(`  UTC:        ${date.toUTCString()}`)
  console.log(`  Locale:     ${date.toLocaleString()}`)
  console.log(`  Unit:       ${isMilliseconds ? "milliseconds" : "seconds"}`)
  console.log(`  Relative:   ${getRelativeTime(date)}`)
  console.log("")
}

function getRelativeTime(date: Date): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const absDiff = Math.abs(diff)
  
  const seconds = Math.floor(absDiff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  const months = Math.floor(days / 30)
  const years = Math.floor(days / 365)
  
  let result = ""
  
  if (years > 0) result = `${years} year${years > 1 ? "s" : ""}`
  else if (months > 0) result = `${months} month${months > 1 ? "s" : ""}`
  else if (days > 0) result = `${days} day${days > 1 ? "s" : ""}`
  else if (hours > 0) result = `${hours} hour${hours > 1 ? "s" : ""}`
  else if (minutes > 0) result = `${minutes} minute${minutes > 1 ? "s" : ""}`
  else result = `${seconds} second${seconds > 1 ? "s" : ""}`
  
  return diff > 0 ? `${result} ago` : `in ${result}`
}

function getNow(): void {
  const now = new Date()
  
  console.log(`\n[timestamp] Current time:`)
  console.log(`  ISO 8601:   ${now.toISOString()}`)
  console.log(`  UTC:        ${now.toUTCString()}`)
  console.log(`  Locale:     ${now.toLocaleString()}`)
  console.log(`  Unix (s):   ${Math.floor(now.getTime() / 1000)}`)
  console.log(`  Unix (ms):  ${now.getTime()}`)
  console.log("")
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Convert timestamp command
        const convertMatch = command.match(/timestamp\s+convert\s+["']([^"']+)["']/)
        if (convertMatch) {
          convertTimestamp(convertMatch[1])
        }
        
        // Convert Unix command
        const unixMatch = command.match(/timestamp\s+unix\s+(\d+)/)
        if (unixMatch) {
          convertUnix(unixMatch[1])
        }
        
        // Get current time
        if (command.match(/timestamp\s+now|time\s+now/)) {
          getNow()
        }
      }
    }
  }
}) satisfies Plugin