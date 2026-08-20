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
  name: "system-info",
  description: "Show detailed system information",
  commands: [
    {
      name: "sysinfo",
      description: "Show full system information",
      handler: () => {
        const result = runCommand('systeminfo')
        return result || "Could not get system info"
      },
    },
    {
      name: "sysinfo cpu",
      description: "Show CPU information",
      handler: () => {
        const result = runCommand('powershell -Command "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed, LoadPercentage | Format-List"')
        return result || "Could not get CPU info"
      },
    },
    {
      name: "sysinfo ram",
      description: "Show RAM information",
      handler: () => {
        const result = runCommand('powershell -Command "Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, Manufacturer | Format-Table -AutoSize; $total = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; Write-Output \"Total RAM: $([math]::Round($total/1GB, 2)) GB\""')
        return result || "Could not get RAM info"
      },
    },
    {
      name: "sysinfo gpu",
      description: "Show GPU information",
      handler: () => {
        const result = runCommand('powershell -Command "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion, VideoProcessor | Format-List"')
        return result || "Could not get GPU info"
      },
    },
    {
      name: "sysinfo disk",
      description: "Show disk information",
      handler: () => {
        const result = runCommand('powershell -Command "Get-CimInstance Win32_DiskDrive | Select-Object Model, Size, MediaType, InterfaceType | Format-List"')
        return result || "Could not get disk info"
      },
    },
  ],
} satisfies Plugin
