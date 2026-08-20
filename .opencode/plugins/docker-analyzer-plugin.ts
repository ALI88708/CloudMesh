import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"

interface DockerInfo {
  services: string[]
  volumes: string[]
  networks: string[]
  issues: string[]
}

function analyzeDockerCompose(content: string): DockerInfo {
  const services: string[] = []
  const volumes: string[] = []
  const networks: string[] = []
  const issues: string[] = []
  
  const lines = content.split("\n")
  let inServices = false
  let inVolumes = false
  let inNetworks = false
  
  lines.forEach((line, index) => {
    const trimmed = line.trim()
    
    if (trimmed === "services:") inServices = true
    else if (trimmed === "volumes:") { inServices = false; inVolumes = true }
    else if (trimmed === "networks:") { inVolumes = false; inNetworks = true }
    else if (!trimmed.startsWith(" ") && trimmed !== "") { inServices = false; inVolumes = false; inNetworks = false }
    
    if (inServices && trimmed.match(/^[a-z][a-z0-9_-]*:/)) {
      services.push(trimmed.replace(":", ""))
    }
    
    if (inVolumes && trimmed.match(/^[a-z][a-z0-9_-]*:/)) {
      volumes.push(trimmed.replace(":", ""))
    }
    
    if (inNetworks && trimmed.match(/^[a-z][a-z0-9_-]*:/)) {
      networks.push(trimmed.replace(":", ""))
    }
    
    // Check for common issues
    if (trimmed.includes("restart: always") && !trimmed.includes("healthcheck")) {
      issues.push(`Line ${index + 1}: Service has restart:always but no healthcheck`)
    }
    
    if (trimmed.includes("ports:") && trimmed.includes("0.0.0.0:")) {
      issues.push(`Line ${index + 1}: Port exposed to all interfaces (0.0.0.0)`)
    }
  })
  
  return { services, volumes, networks, issues }
}

function analyzeDockerfile(content: string): string[] {
  const issues: string[] = []
  const lines = content.split("\n")
  
  lines.forEach((line, index) => {
    const trimmed = line.trim()
    
    if (trimmed.startsWith("FROM") && !trimmed.includes("AS")) {
      issues.push(`Line ${index + 1}: Consider using multi-stage builds`)
    }
    
    if (trimmed.includes("COPY . .") || trimmed.includes("ADD . .")) {
      issues.push(`Line ${index + 1}: Copying entire context - use .dockerignore`)
    }
    
    if (trimmed.includes("RUN apt-get install") && !trimmed.includes("rm -rf /var/lib/apt/lists")) {
      issues.push(`Line ${index + 1}: Clean apt cache after install`)
    }
    
    if (trimmed.includes("EXPOSE") && trimmed.includes("22")) {
      issues.push(`Line ${index + 1}: SSH exposed - consider if necessary`)
    }
  })
  
  return issues
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "read" || input.tool === "edit") {
        const filePath = input.args?.filePath
        if (!filePath) return
        
        try {
          if (filePath.includes("docker-compose") && filePath.endsWith(".yml")) {
            const content = readFileSync(filePath, "utf-8")
            const info = analyzeDockerCompose(content)
            
            console.log(`\n[docker-analyzer] ${filePath}:`)
            console.log(`  🐳 Services: ${info.services.join(", ") || "none"}`)
            console.log(`  💾 Volumes: ${info.volumes.join(", ") || "none"}`)
            console.log(`  🌐 Networks: ${info.networks.join(", ") || "none"}`)
            
            if (info.issues.length > 0) {
              console.log(`  ⚠️  Issues:`)
              info.issues.forEach(i => console.log(`     ${i}`))
            }
            console.log("")
          }
          
          if (filePath.endsWith("Dockerfile")) {
            const content = readFileSync(filePath, "utf-8")
            const issues = analyzeDockerfile(content)
            
            if (issues.length > 0) {
              console.log(`\n[docker-analyzer] ${filePath}:`)
              console.log(`  🐳 Dockerfile issues:`)
              issues.forEach(i => console.log(`     ${i}`))
              console.log("")
            }
          }
        } catch {}
      }
    }
  }
}) satisfies Plugin