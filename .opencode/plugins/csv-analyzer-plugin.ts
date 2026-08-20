import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync } from "fs"

interface CSVData {
  headers: string[]
  rows: string[][]
  rowCount: number
  columnCount: number
}

function parseCSV(content: string, delimiter: string = ","): CSVData {
  const lines = content.split("\n").filter(line => line.trim())
  const headers = lines[0]?.split(delimiter).map(h => h.trim()) || []
  const rows = lines.slice(1).map(line => line.split(delimiter).map(cell => cell.trim()))
  
  return {
    headers,
    rows,
    rowCount: rows.length,
    columnCount: headers.length
  }
}

function formatCSV(data: CSVData, delimiter: string = ","): string {
  const headerLine = data.headers.join(delimiter)
  const rows = data.rows.map(row => row.join(delimiter))
  return [headerLine, ...rows].join("\n")
}

function analyzeCSV(data: CSVData): void {
  console.log(`\n[csv-analyzer] CSV Analysis:`)
  console.log(`  Rows: ${data.rowCount}`)
  console.log(`  Columns: ${data.columnCount}`)
  console.log(`  Headers: ${data.headers.join(", ")}`)
  
  // Analyze each column
  console.log(`\n  Column Statistics:`)
  data.headers.forEach((header, index) => {
    const values = data.rows.map(row => row[index]).filter(v => v)
    const numericValues = values.filter(v => !isNaN(Number(v)))
    
    console.log(`    ${header}:`)
    console.log(`      Non-empty: ${values.length}/${data.rowCount}`)
    console.log(`      Type: ${numericValues.length > values.length * 0.8 ? "numeric" : "text"}`)
    
    if (numericValues.length > 0) {
      const nums = numericValues.map(Number)
      console.log(`      Min: ${Math.min(...nums)}`)
      console.log(`      Max: ${Math.max(...nums)}`)
      console.log(`      Avg: ${(nums.reduce((a, b) => a + b, 0) / nums.length).toFixed(2)}`)
    }
  })
}

function searchCSV(data: CSVData, query: string): string[][] {
  const results: string[][] = []
  
  data.rows.forEach(row => {
    const match = row.some(cell => cell.toLowerCase().includes(query.toLowerCase()))
    if (match) results.push(row)
  })
  
  return results
}

function filterCSV(data: CSVData, column: string, value: string): CSVData {
  const colIndex = data.headers.indexOf(column)
  if (colIndex === -1) return { ...data, rows: [] }
  
  const filteredRows = data.rows.filter(row => row[colIndex] === value)
  
  return {
    headers: data.headers,
    rows: filteredRows,
    rowCount: filteredRows.length,
    columnCount: data.columnCount
  }
}

function sortCSV(data: CSVData, column: string, ascending: boolean = true): CSVData {
  const colIndex = data.headers.indexOf(column)
  if (colIndex === -1) return data
  
  const sortedRows = [...data.rows].sort((a, b) => {
    const aVal = a[colIndex]
    const bVal = b[colIndex]
    
    const aNum = Number(aVal)
    const bNum = Number(bVal)
    
    if (!isNaN(aNum) && !isNaN(bNum)) {
      return ascending ? aNum - bNum : bNum - aNum
    }
    
    return ascending ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
  })
  
  return {
    headers: data.headers,
    rows: sortedRows,
    rowCount: sortedRows.length,
    columnCount: data.columnCount
  }
}

export default (async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash") {
        const command = input.args?.command || ""
        
        // Analyze CSV
        const analyzeMatch = command.match(/csv\s+analyze\s+["']([^"']+)["'](?:\s+--delimiter\s+["']([^"']+)["'])?/)
        if (analyzeMatch) {
          const [, filePath, delimiter = ","] = analyzeMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const data = parseCSV(content, delimiter)
            analyzeCSV(data)
          } catch (e) {
            console.log(`[csv-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Search CSV
        const searchMatch = command.match(/csv\s+search\s+["']([^"']+)["']\s+["']([^"']+)["']/)
        if (searchMatch) {
          const [, filePath, query] = searchMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const data = parseCSV(content)
            const results = searchCSV(data, query)
            
            console.log(`\n[csv-analyzer] Search results for "${query}":`)
            console.log(`  Found ${results.length} rows`)
            results.slice(0, 5).forEach(row => {
              console.log(`    ${row.join(", ")}`)
            })
          } catch (e) {
            console.log(`[csv-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Filter CSV
        const filterMatch = command.match(/csv\s+filter\s+["']([^"']+)["']\s+--column\s+["']([^"']+)["']\s+--value\s+["']([^"']+)["']/)
        if (filterMatch) {
          const [, filePath, column, value] = filterMatch
          try {
            const content = readFileSync(filePath, "utf-8")
            const data = parseCSV(content)
            const filtered = filterCSV(data, column, value)
            
            console.log(`\n[csv-analyzer] Filtered by ${column} = ${value}:`)
            console.log(`  Found ${filtered.rowCount} rows`)
            filtered.rows.slice(0, 5).forEach(row => {
              console.log(`    ${row.join(", ")}`)
            })
          } catch (e) {
            console.log(`[csv-analyzer] Error: ${e}`)
          }
          console.log("")
        }
        
        // Sort CSV
        const sortMatch = command.match(/csv\s+sort\s+["']([^"']+)["']\s+--column\s+["']([^"']+)["'](?:\s+--desc)?/)
        if (sortMatch) {
          const [, filePath, column] = sortMatch
          const ascending = !command.includes("--desc")
          try {
            const content = readFileSync(filePath, "utf-8")
            const data = parseCSV(content)
            const sorted = sortCSV(data, column, ascending)
            
            console.log(`\n[csv-analyzer] Sorted by ${column} (${ascending ? "asc" : "desc"}):`)
            sorted.rows.slice(0, 5).forEach(row => {
              console.log(`    ${row.join(", ")}`)
            })
          } catch (e) {
            console.log(`[csv-analyzer] Error: ${e}`)
          }
          console.log("")
        }
      }
    }
  }
}) satisfies Plugin