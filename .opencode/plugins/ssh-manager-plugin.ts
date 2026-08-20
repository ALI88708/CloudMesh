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
  name: "ssh-manager",
  description: "SSH connection and key management",
  commands: [
    {
      name: "ssh",
      description: "Connect to a remote host via SSH (e.g. ssh user@192.168.1.1)",
      handler: (args: string) => {
        if (!args) return "Usage: ssh <user@host> or ssh <host>"
        return `Opening SSH connection to ${args}...\nNote: SSH sessions require interactive terminals. Use: ssh ${args}`
      },
    },
    {
      name: "ssh keygen",
      description: "Generate a new SSH key pair",
      handler: () => {
        const result = runCommand('ssh-keygen -t rsa -b 4096 -f "$env:USERPROFILE\\.ssh\\id_rsa" -N ""')
        return result || "SSH key pair generated in ~/.ssh/"
      },
    },
    {
      name: "ssh keys",
      description: "List SSH keys in ~/.ssh/",
      handler: () => {
        const result = runCommand('powershell -Command "Get-ChildItem -Path $env:USERPROFILE\\.ssh -ErrorAction SilentlyContinue | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize"')
        return result || "No SSH keys found in ~/.ssh/"
      },
    },
  ],
} satisfies Plugin
