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
  name: "audio-control",
  description: "Control system audio volume",
  commands: [
    {
      name: "vol",
      description: "Show current volume level",
      handler: () => {
        const script = `
Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int j();
    int GetMasterVolumeLevelScalar(out float pfLevel);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {
    int Activate(ref System.Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}
[Guid("A95664D2-9614-4F35-A746-de8db996169A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumeratorComObject {}
"@ -ReferencedAssemblies System.Runtime.InteropServices

$enumerator = New-Object MMDeviceEnumeratorComObject
$device = $null
$enumerator.GetDefaultAudioEndpoint(0, 1, [ref]$device)
$interface = $null
$iid = [Guid]"5CDF2C82-841E-4546-9722-0CF74078229A"
$device.Activate([ref]$iid, 1, [IntPtr]::Zero, [ref]$interface)
$level = 0.0
$interface.GetMasterVolumeLevelScalar([ref]$level)
$pct = [math]::Round($level * 100)
Write-Output "Volume: $pct%"`
        const tmpFile = `${process.env.TEMP}\\vol_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not get volume"
      },
    },
    {
      name: "vol up",
      description: "Increase volume by 10%",
      handler: () => {
        const script = `
Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int j();
    int GetMasterVolumeLevelScalar(out float pfLevel);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {
    int Activate(ref System.Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}
[Guid("A95664D2-9614-4F35-A746-de8db996169A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumeratorComObject {}
"@ -ReferencedAssemblies System.Runtime.InteropServices

$enumerator = New-Object MMDeviceEnumeratorComObject
$device = $null
$enumerator.GetDefaultAudioEndpoint(0, 1, [ref]$device)
$interface = $null
$iid = [Guid]"5CDF2C82-841E-4546-9722-0CF74078229A"
$device.Activate([ref]$iid, 1, [IntPtr]::Zero, [ref]$interface)
$level = 0.0
$interface.GetMasterVolumeLevelScalar([ref]$level)
$newLevel = [math]::Min(1.0, $level + 0.1)
$interface.SetMasterVolumeLevelScalar($newLevel, [Guid]::Empty)
$pct = [math]::Round($newLevel * 100)
Write-Output "Volume increased to $pct%"`
        const tmpFile = `${process.env.TEMP}\\volup_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not adjust volume"
      },
    },
    {
      name: "vol down",
      description: "Decrease volume by 10%",
      handler: () => {
        const script = `
Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int j();
    int GetMasterVolumeLevelScalar(out float pfLevel);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {
    int Activate(ref System.Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}
[Guid("A95664D2-9614-4F35-A746-de8db996169A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumeratorComObject {}
"@ -ReferencedAssemblies System.Runtime.InteropServices

$enumerator = New-Object MMDeviceEnumeratorComObject
$device = $null
$enumerator.GetDefaultAudioEndpoint(0, 1, [ref]$device)
$interface = $null
$iid = [Guid]"5CDF2C82-841E-4546-9722-0CF74078229A"
$device.Activate([ref]$iid, 1, [IntPtr]::Zero, [ref]$interface)
$level = 0.0
$interface.GetMasterVolumeLevelScalar([ref]$level)
$newLevel = [math]::Max(0.0, $level - 0.1)
$interface.SetMasterVolumeLevelScalar($newLevel, [Guid]::Empty)
$pct = [math]::Round($newLevel * 100)
Write-Output "Volume decreased to $pct%"`
        const tmpFile = `${process.env.TEMP}\\voldown_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not adjust volume"
      },
    },
    {
      name: "vol mute",
      description: "Toggle mute",
      handler: () => {
        const script = `
Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int j();
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, System.Guid pguidEventContext);
    int GetMute([MarshalAs(UnmanagedType.Bool)] out bool pbMute);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {
    int Activate(ref System.Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}
[Guid("A95664D2-9614-4F35-A746-de8db996169A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumeratorComObject {}
"@ -ReferencedAssemblies System.Runtime.InteropServices

$enumerator = New-Object MMDeviceEnumeratorComObject
$device = $null
$enumerator.GetDefaultAudioEndpoint(0, 1, [ref]$device)
$interface = $null
$iid = [Guid]"5CDF2C82-841E-4546-9722-0CF74078229A"
$device.Activate([ref]$iid, 1, [IntPtr]::Zero, [ref]$interface)
$muted = $false
$interface.GetMute([ref]$muted)
$newMute = -not $muted
$interface.SetMute($newMute, [Guid]::Empty)
if ($newMute) { Write-Output "Audio muted" } else { Write-Output "Audio unmuted" }`
        const tmpFile = `${process.env.TEMP}\\volmute_cmd.ps1`
        require("fs").writeFileSync(tmpFile, script)
        return runCommand(`powershell -ExecutionPolicy Bypass -File "${tmpFile}"`) || "Could not toggle mute"
      },
    },
  ],
} satisfies Plugin
