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
  name: "text-to-speech",
  description: "Text-to-speech using Windows SAPI",
  commands: [
    {
      name: "speak",
      description: "Speak text using Windows TTS (e.g. speak Hello World)",
      handler: (args: string) => {
        if (!args) return "Usage: speak <text>"
        const script = `
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Speak("${args.replace(/"/g, '`"')}")
$synth.Dispose()
Write-Output "Spoke: ${args.replace(/"/g, '`"')}"`
        const tmpFile = `${process.env.TEMP}\\speak_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`)
        return `Speaking: ${args}`
      },
    },
    {
      name: "speak stop",
      description: "Stop any ongoing speech",
      handler: () => {
        const script = `
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SpeakAsyncCancelAll()
$synth.Dispose()
Write-Output "Speech stopped"`
        const tmpFile = `${process.env.TEMP}\\speakstop_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`)
        return "Speech stopped"
      },
    },
  ],
} satisfies Plugin
