import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync } from "fs"

const NOTES_FILE = "C:\\Users\\mr_ali7685\\AppData\\Local\\Temp\\opencode-notes.json"

interface Note {
  id: number
  text: string
  createdAt: string
}

function getNotes(): Note[] {
  try {
    if (existsSync(NOTES_FILE)) {
      return JSON.parse(readFileSync(NOTES_FILE, "utf-8"))
    }
  } catch {}
  return []
}

function saveNotes(notes: Note[]) {
  writeFileSync(NOTES_FILE, JSON.stringify(notes, null, 2))
}

export default {
  name: "notes",
  description: "Quick notes system for storing and managing notes",
  commands: [
    {
      name: "note",
      description: "Manage quick notes. Usage: note add <text> | note list | note remove <id> | note clear",
      handler: (args: string) => {
        if (!args || args.trim() === "") {
          return `Usage:
  note add <text>    - Add a new note
  note list          - List all notes
  note remove <id>   - Remove a note by ID
  note clear         - Clear all notes`
        }

        const notes = getNotes()
        const parts = args.trim().split(/\s+/)
        const action = parts[0].toLowerCase()

        if (action === "list") {
          if (notes.length === 0) return "No notes stored."
          return notes
            .map((n) => `[${n.id}] (${n.createdAt}) ${n.text}`)
            .join("\n")
        }

        if (action === "clear") {
          saveNotes([])
          return "All notes cleared."
        }

        if (action === "remove") {
          const id = parseInt(parts[1])
          if (isNaN(id)) return "Usage: note remove <id>"
          const index = notes.findIndex((n) => n.id === id)
          if (index === -1) return `Note [${id}] not found.`
          const removed = notes.splice(index, 1)[0]
          saveNotes(notes)
          return `Removed note [${id}]: ${removed.text}`
        }

        if (action === "add") {
          const text = args.trim().slice(4).trim()
          if (!text) return "Usage: note add <text>"
          const id = notes.length > 0 ? Math.max(...notes.map((n) => n.id)) + 1 : 1
          const note: Note = {
            id,
            text,
            createdAt: new Date().toISOString(),
          }
          notes.push(note)
          saveNotes(notes)
          return `Note [${id}] added: ${text}`
        }

        return `Unknown action: ${action}. Use: note add|list|remove|clear`
      },
    },
  ],
} satisfies Plugin
