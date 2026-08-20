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
  name: "unit-converter",
  description: "Convert between units (length, weight, temperature)",
  commands: [
    {
      name: "convert",
      description: "Convert units (e.g. convert 100 km to miles, convert 72 fahrenheit to celsius)",
      handler: (args: string) => {
        if (!args) return "Usage: convert <value> <from> to <to>\nExamples: convert 100 km to miles, convert 72 fahrenheit to celsius"
        const match = args.match(/^([\d.]+)\s+(\S+)\s+to\s+(\S+)$/i)
        if (!match) return "Usage: convert <value> <from> to <to>"
        const [, valueStr, fromRaw, toRaw] = match
        const value = parseFloat(valueStr)
        const from = fromRaw.toLowerCase()
        const to = toRaw.toLowerCase()

        const conversions: Record<string, Record<string, (v: number) => number>> = {
          length: {
            km: { miles: (v) => v * 0.621371, meters: (v) => v * 1000, feet: (v) => v * 3280.84, inches: (v) => v * 39370.1, cm: (v) => v * 100000 },
            miles: { km: (v) => v * 1.60934, meters: (v) => v * 1609.34, feet: (v) => v * 5280 },
            meters: { km: (v) => v / 1000, miles: (v) => v * 0.000621371, feet: (v) => v * 3.28084, cm: (v) => v * 100 },
            feet: { meters: (v) => v * 0.3048, km: (v) => v * 0.0003048, miles: (v) => v / 5280, inches: (v) => v * 12 },
            inches: { cm: (v) => v * 2.54, meters: (v) => v * 0.0254, feet: (v) => v / 12 },
            cm: { inches: (v) => v / 2.54, meters: (v) => v / 100, feet: (v) => v / 30.48 },
          },
          weight: {
            kg: { lbs: (v) => v * 2.20462, grams: (v) => v * 1000, oz: (v) => v * 35.274 },
            lbs: { kg: (v) => v * 0.453592, grams: (v) => v * 453.592, oz: (v) => v * 16 },
            grams: { kg: (v) => v / 1000, lbs: (v) => v * 0.00220462, oz: (v) => v * 0.035274 },
            oz: { grams: (v) => v * 28.3495, kg: (v) => v * 0.0283495, lbs: (v) => v / 16 },
          },
          temperature: {
            celsius: { fahrenheit: (v) => v * 9 / 5 + 32, kelvin: (v) => v + 273.15 },
            fahrenheit: { celsius: (v) => (v - 32) * 5 / 9, kelvin: (v) => (v - 32) * 5 / 9 + 273.15 },
            kelvin: { celsius: (v) => v - 273.15, fahrenheit: (v) => (v - 273.15) * 9 / 5 + 32 },
          },
        }

        for (const category of Object.values(conversions)) {
          if (category[from] && category[from][to]) {
            const result = category[from][to](value)
            return `${value} ${from} = ${Math.round(result * 10000) / 10000} ${to}`
          }
        }
        return `Conversion not supported: ${from} to ${to}\nSupported units: km, miles, meters, feet, inches, cm, kg, lbs, grams, oz, celsius, fahrenheit, kelvin`
      },
    },
  ],
} satisfies Plugin
