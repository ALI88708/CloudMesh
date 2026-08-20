import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync } from "fs"

function markdownToHtml(markdown: string): string {
  let html = markdown
  
  // Headers
  html = html.replace(/^### (.*$)/gm, "<h3>$1</h3>")
  html = html.replace(/^## (.*$)/gm, "<h2>$1</h2>")
  html = html.replace(/^# (.*$)/gm, "<h1>$1</h1>")
  
  // Bold and Italic
  html = html.replace(/\*\*\*(.*?)\*\*\*/g, "<strong><em>$1</em></strong>")
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
  html = html.replace(/\*(.*?)\*/g, "<em>$1</em>")
  
  // Code
  html = html.replace(/`(.*?)`/g, "<code>$1</code>")
  html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, "<pre><code class=\"language-$1\">$2</code></pre>")
  
  // Links and Images
  html = html.replace(/!\[(.*?)\]\((.*?)\)/g, "<img src=\"$2\" alt=\"$1\">")
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, "<a href=\"$2\">$1</a>")
  
  // Lists
  html = html.replace(/^\s*\*\s(.*$)/gm, "<li>$1</li>")
  html = html.replace(/^\s*-\s(.*$)/gm, "<li>$1</li>")
  html = html.replace(/^\s*\d+\.\s(.*$)/gm, "<li>$1</li>")
  
  // Blockquotes
  html = html.replace(/^>\s(.*$)/gm, "<blockquote>$1</blockquote>")
  
  // Horizontal rules
  html = html.replace(/^---$/gm, "<hr>")
  html = html.replace(/^\*\*\*$/gm, "<hr>")
  
  // Line breaks
  html = html.replace(/\n/g, "<br>")
  
  // Clean up multiple br tags
  html = html.replace(/(<br>){3,}/g, "<br><br>")
  
  return html
}

function htmlToMarkdown(html: string): string {
  let md = html
  
  // Headers
  md = md.replace(/<h1>(.*?)<\/h1>/g, "# $1\n")
  md = md.replace(/<h2>(.*?)<\/h2>/g, "## $1\n")
  md = md.replace(/<h3>(.*?)<\/h3>/g, "### $1\n")
  
  // Bold and Italic
  md = md.replace(/<strong><em>(.*?)<\/em><\/strong>/g, "***$1***")
  md = md.replace(/<strong>(.*?)<\/strong>/g, "**$1**")
  md = md.replace(/<em>(.*?)<\/em>/g, "*$1*")
  
  // Code
  md = md.replace(/<code>(.*?)<\/code>/g, "`$1`")
  md = md.replace(/<pre><code class="language-(.*?)">(.*?)<\/code><\/pre>/g, "```$1\n$2\n```")
  
  // Links and Images
  md = md.replace(/<img src="(.*?)" alt="(.*?)">/g, "![ $2 ]($1)")
  md = md.replace(/<a href="(.*?)">(.*?)<\/a>/g, "[$2]($1)")
  
  // Lists
  md = md.replace(/<li>(.*?)<\/li>/g, "- $1\n")
  
  // Blockquotes
  md = md.replace(/<blockquote>(.*?)<\/blockquote>/g, "> $1\n")
  
  // Horizontal rules
  md = md.replace(/<hr>/g, "---\n")
  
  // Line breaks
  md = md.replace(/<br>/g, "\n")
  
  return md
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Convert markdown to HTML
        const mdMatch = command.match(/markdown\s+to\s+html\s+["']([^"']+)["']/)
        if (mdMatch) {
          const [, filePath] = mdMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const html = markdownToHtml(content)
            
            const outputPath = filePath.replace(/\.md$/, ".html")
            writeFileSync(outputPath, html)
            
            console.log(`\n[markdown-converter] Converted ${filePath} to HTML`)
            console.log(`  Output: ${outputPath}`)
            console.log("")
          } catch (e) {
            console.log(`[markdown-converter] Error: ${e}`)
          }
        }
        
        // Convert HTML to markdown
        const htmlMatch = command.match(/html\s+to\s+markdown\s+["']([^"']+)["']/)
        if (htmlMatch) {
          const [, filePath] = htmlMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const markdown = htmlToMarkdown(content)
            
            const outputPath = filePath.replace(/\.html$/, ".md")
            writeFileSync(outputPath, markdown)
            
            console.log(`\n[markdown-converter] Converted ${filePath} to Markdown`)
            console.log(`  Output: ${outputPath}`)
            console.log("")
          } catch (e) {
            console.log(`[markdown-converter] Error: ${e}`)
          }
        }
        
        // Preview markdown
        const previewMatch = command.match(/markdown\s+preview\s+["']([^"']+)["']/)
        if (previewMatch) {
          const [, filePath] = previewMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const html = markdownToHtml(content)
            
            console.log(`\n[markdown-converter] HTML Preview:`)
            console.log(html)
            console.log("")
          } catch (e) {
            console.log(`[markdown-converter] Error: ${e}`)
          }
        }
      }
    }
  }
}) satisfies Plugin