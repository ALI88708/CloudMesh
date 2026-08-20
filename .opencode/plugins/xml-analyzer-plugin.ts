import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync } from "fs"

interface XMLNode {
  name: string
  attributes: Record<string, string>
  children: XMLNode[]
  text?: string
}

function parseXML(xml: string): XMLNode | null {
  const parser = new DOMParser()
  const doc = parser.parseFromString(xml, "text/xml")
  
  const errorNode = doc.querySelector("parsererror")
  if (errorNode) {
    return null
  }
  
  function nodeToObj(node: Node): XMLNode {
    const obj: XMLNode = {
      name: node.nodeName,
      attributes: {},
      children: []
    }
    
    if (node.attributes) {
      for (let i = 0; i < node.attributes.length; i++) {
        const attr = node.attributes[i]
        obj.attributes[attr.name] = attr.value
      }
    }
    
    for (let i = 0; i < node.childNodes.length; i++) {
      const child = node.childNodes[i]
      if (child.nodeType === 1) {
        obj.children.push(nodeToObj(child))
      } else if (child.nodeType === 3 && child.textContent?.trim()) {
        obj.text = child.textContent.trim()
      }
    }
    
    return obj
  }
  
  return nodeToObj(doc.documentElement)
}

function validateXML(xml: string): { valid: boolean; error?: string; line?: number } {
  const parser = new DOMParser()
  const doc = parser.parseFromString(xml, "text/xml")
  
  const errorNode = doc.querySelector("parsererror")
  if (errorNode) {
    const errorText = errorNode.textContent || "Unknown error"
    const lineMatch = errorText.match(/line (\d+)/i)
    return {
      valid: false,
      error: errorText.split("\n")[0],
      line: lineMatch ? parseInt(lineMatch[1]) : undefined
    }
  }
  
  return { valid: true }
}

function formatXML(xml: string, indent: number = 2): string {
  let formatted = ""
  let indentLevel = 0
  
  const lines = xml.replace(/(>)(<)(\/*)/g, "$1\n$2$3").split("\n")
  
  lines.forEach(line => {
    const trimmed = line.trim()
    
    if (trimmed.startsWith("</")) {
      indentLevel--
    }
    
    formatted += " ".repeat(indentLevel * indent) + trimmed + "\n"
    
    if (trimmed.startsWith("<") && !trimmed.startsWith("</") && !trimmed.endsWith("/>") && !trimmed.includes("</")) {
      indentLevel++
    }
  })
  
  return formatted.trim()
}

function xmlToJSON(xml: string): string | null {
  const node = parseXML(xml)
  if (!node) return null
  
  function nodeToJSON(node: XMLNode): any {
    const obj: any = {}
    
    if (Object.keys(node.attributes).length > 0) {
      obj["@attributes"] = node.attributes
    }
    
    if (node.text) {
      obj["#text"] = node.text
    }
    
    node.children.forEach(child => {
      if (obj[child.name]) {
        if (!Array.isArray(obj[child.name])) {
          obj[child.name] = [obj[child.name]]
        }
        obj[child.name].push(nodeToJSON(child))
      } else {
        obj[child.name] = nodeToJSON(child)
      }
    })
    
    return Object.keys(obj).length === 0 ? "" : obj
  }
  
  return JSON.stringify({ [node.name]: nodeToJSON(node) }, null, 2)
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Validate XML
        const validateMatch = command.match(/xml\s+validate\s+["']([^"']+)["']/)
        if (validateMatch) {
          const [, filePath] = validateMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const result = validateXML(content)
            
            console.log(`\n[xml-analyzer] Validation: ${filePath}`)
            console.log(`  Valid: ${result.valid ? "✅ Yes" : "❌ No"}`)
            if (result.error) {
              console.log(`  Error: ${result.error}`)
              if (result.line) console.log(`  Line: ${result.line}`)
            }
          } catch (e) {
            console.log(`[xml-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Format XML
        const formatMatch = command.match(/xml\s+format\s+["']([^"']+)["'](?:\s+--indent\s+(\d+))?/)
        if (formatMatch) {
          const [, filePath, indent = "2"] = formatMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const formatted = formatXML(content, parseInt(indent))
            
            console.log(`\n[xml-analyzer] Formatted XML:`)
            console.log(formatted)
          } catch (e) {
            console.log(`[xml-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Convert XML to JSON
        const jsonMatch = command.match(/xml\s+to\s+json\s+["']([^"']+)["']/)
        if (jsonMatch) {
          const [, filePath] = jsonMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const json = xmlToJSON(content)
            
            if (json) {
              console.log(`\n[xml-analyzer] XML to JSON:`)
              console.log(json)
            } else {
              console.log(`[xml-analyzer] Failed to parse XML`)
            }
          } catch (e) {
            console.log(`[xml-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Analyze XML structure
        const analyzeMatch = command.match(/xml\s+analyze\s+["']([^"']+)["']/)
        if (analyzeMatch) {
          const [, filePath] = analyzeMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const node = parseXML(content)
            
            if (node) {
              console.log(`\n[xml-analyzer] XML Structure:`)
              console.log(`  Root: ${node.name}`)
              console.log(`  Attributes: ${Object.keys(node.attributes).length}`)
              console.log(`  Children: ${node.children.length}`)
              
              function countNodes(n: XMLNode): number {
                return 1 + n.children.reduce((sum, child) => sum + countNodes(child), 0)
              }
              
              console.log(`  Total nodes: ${countNodes(node)}`)
            }
          } catch (e) {
            console.log(`[xml-analyzer] Error: ${e}`)
          }
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin