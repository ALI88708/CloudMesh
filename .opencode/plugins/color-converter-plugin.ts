import type { Plugin } from "@opencode-ai/plugin"

interface RGB { r: number; g: number; b: number }
interface HSL { h: number; s: number; l: number }
interface HSV { h: number; s: number; v: number }

function hexToRgb(hex: string): RGB | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : null
}

function rgbToHex(rgb: RGB): string {
  return "#" + [rgb.r, rgb.g, rgb.b].map(x => x.toString(16).padStart(2, "0")).join("")
}

function rgbToHsl(rgb: RGB): HSL {
  const r = rgb.r / 255
  const g = rgb.g / 255
  const b = rgb.b / 255
  
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  
  if (max === min) return { h: 0, s: 0, l }
  
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  
  let h = 0
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
  else if (max === g) h = ((b - r) / d + 2) / 6
  else h = ((r - g) / d + 4) / 6
  
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) }
}

function hslToRgb(hsl: HSL): RGB {
  const h = hsl.h / 360
  const s = hsl.s / 100
  const l = hsl.l / 100
  
  if (s === 0) {
    const v = Math.round(l * 255)
    return { r: v, g: v, b: v }
  }
  
  const hue2rgb = (p: number, q: number, t: number) => {
    if (t < 0) t += 1
    if (t > 1) t -= 1
    if (t < 1/6) return p + (q - p) * 6 * t
    if (t < 1/2) return q
    if (t < 2/3) return p + (q - p) * (2/3 - t) * 6
    return p
  }
  
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  
  return {
    r: Math.round(hue2rgb(p, q, h + 1/3) * 255),
    g: Math.round(hue2rgb(p, q, h) * 255),
    b: Math.round(hue2rgb(p, q, h - 1/3) * 255)
  }
}

function rgbToHsv(rgb: RGB): HSV {
  const r = rgb.r / 255
  const g = rgb.g / 255
  const b = rgb.b / 255
  
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const d = max - min
  
  const v = max
  const s = max === 0 ? 0 : d / max
  
  let h = 0
  if (max !== min) {
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break
      case g: h = (b - r) / d + 2; break
      case b: h = (r - g) / d + 4; break
    }
    h /= 6
  }
  
  return { h: Math.round(h * 360), s: Math.round(s * 100), v: Math.round(v * 100) }
}

function getContrastColor(rgb: RGB): string {
  const luminance = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255
  return luminance > 0.5 ? "#000000" : "#FFFFFF"
}

function getColorName(rgb: RGB): string {
  const hsl = rgbToHsl(rgb)
  const { h, s, l } = hsl
  
  if (l < 10) return "Black"
  if (l > 90) return "White"
  if (s < 10) return "Gray"
  
  if (h < 15) return "Red"
  if (h < 45) return "Orange"
  if (h < 65) return "Yellow"
  if (h < 170) return "Green"
  if (h < 195) return "Cyan"
  if (h < 255) return "Blue"
  if (h < 285) return "Purple"
  if (h < 330) return "Pink"
  return "Red"
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Convert hex to RGB
        const hexMatch = command.match(/color\s+hex\s+["']?(#[a-fA-F0-9]{6}|[a-fA-F0-9]{6})["']?/)
        if (hexMatch) {
          const hex = hexMatch[1].startsWith("#") ? hexMatch[1] : "#" + hexMatch[1]
          const rgb = hexToRgb(hex)
          
          if (rgb) {
            const hsl = rgbToHsl(rgb)
            const hsv = rgbToHsv(rgb)
            const name = getColorName(rgb)
            const contrast = getContrastColor(rgb)
            
            console.log(`\n[color-converter] Color: ${hex}`)
            console.log(`  Name: ${name}`)
            console.log(`  RGB: rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`)
            console.log(`  HSL: hsl(${hsl.h}, ${hsl.s}%, ${hsl.l}%)`)
            console.log(`  HSV: hsv(${hsv.h}, ${hsv.s}%, ${hsv.v}%)`)
            console.log(`  Contrast: ${contrast}`)
          } else {
            console.log(`[color-converter] Invalid hex: ${hex}`)
          }
          console.log("")
        }
        
        // Convert RGB to hex
        const rgbMatch = command.match(/color\s+rgb\s+(\d+)\s+(\d+)\s+(\d+)/)
        if (rgbMatch) {
          const rgb = { r: parseInt(rgbMatch[1]), g: parseInt(rgbMatch[2]), b: parseInt(rgbMatch[3]) }
          const hex = rgbToHex(rgb)
          const hsl = rgbToHsl(rgb)
          const name = getColorName(rgb)
          
          console.log(`\n[color-converter] Color: rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`)
          console.log(`  Name: ${name}`)
          console.log(`  Hex: ${hex}`)
          console.log(`  HSL: hsl(${hsl.h}, ${hsl.s}%, ${hsl.l}%)`)
          console.log("")
        }
        
        // Generate color palette
        const paletteMatch = command.match(/color\s+palette\s+["']?(#[a-fA-F0-9]{6}|[a-fA-F0-9]{6})["']?/)
        if (paletteMatch) {
          const hex = paletteMatch[1].startsWith("#") ? paletteMatch[1] : "#" + paletteMatch[1]
          const rgb = hexToRgb(hex)
          
          if (rgb) {
            const hsl = rgbToHsl(rgb)
            
            console.log(`\n[color-converter] Palette for ${hex}:`)
            
            // Shades
            console.log(`  Shades:`)
            for (let i = 100; i >= 0; i -= 20) {
              const shadeRgb = hslToRgb({ ...hsl, l: i })
              console.log(`    ${rgbToHex(shadeRgb)} (L: ${i}%)`)
            }
            
            // Tints
            console.log(`  Tints:`)
            for (let i = 0; i <= 100; i += 20) {
              const tintRgb = hslToRgb({ ...hsl, l: i })
              console.log(`    ${rgbToHex(tintRgb)} (L: ${i}%)`)
            }
          }
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin