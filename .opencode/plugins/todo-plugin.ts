import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import * as fs from "fs"

const TODO_FILE = "C:\\Users\\mr_ali7685\\AppData\\Local\\Temp\\opencode-todos.json"

interface Todo {
  id: number
  text: string
  done: boolean
  created: string
}

function loadTodos(): Todo[] {
  try {
    if (fs.existsSync(TODO_FILE)) {
      return JSON.parse(fs.readFileSync(TODO_FILE, "utf-8"))
    }
  } catch {}
  return []
}

function saveTodos(todos: Todo[]): void {
  fs.writeFileSync(TODO_FILE, JSON.stringify(todos, null, 2))
}

export default {
  name: "todo",
  description: "Simple todo list manager",
  commands: [
    {
      name: "todo",
      description: "List all todos",
      handler: () => {
        const todos = loadTodos()
        if (todos.length === 0) return "No todos. Add one with: todo add <text>"
        const lines = todos.map((t) => {
          const status = t.done ? "[x]" : "[ ]"
          return `  ${t.id}. ${status} ${t.text}`
        })
        return `Todo List (${todos.filter((t) => !t.done).length} pending):\n${lines.join("\n")}`
      },
    },
    {
      name: "todo add",
      description: "Add a new todo (e.g. todo add Buy groceries)",
      handler: (args: string) => {
        if (!args) return "Usage: todo add <text>"
        const todos = loadTodos()
        const maxId = todos.reduce((max, t) => Math.max(max, t.id), 0)
        todos.push({
          id: maxId + 1,
          text: args,
          done: false,
          created: new Date().toISOString(),
        })
        saveTodos(todos)
        return `Added todo #${maxId + 1}: ${args}`
      },
    },
    {
      name: "todo done",
      description: "Mark a todo as done (e.g. todo done 1)",
      handler: (args: string) => {
        if (!args) return "Usage: todo done <id>"
        const id = parseInt(args.trim())
        if (isNaN(id)) return "Invalid todo ID"
        const todos = loadTodos()
        const todo = todos.find((t) => t.id === id)
        if (!todo) return `Todo #${id} not found`
        todo.done = true
        saveTodos(todos)
        return `Completed: #${id} - ${todo.text}`
      },
    },
    {
      name: "todo remove",
      description: "Remove a todo (e.g. todo remove 1)",
      handler: (args: string) => {
        if (!args) return "Usage: todo remove <id>"
        const id = parseInt(args.trim())
        if (isNaN(id)) return "Invalid todo ID"
        const todos = loadTodos()
        const index = todos.findIndex((t) => t.id === id)
        if (index === -1) return `Todo #${id} not found`
        const removed = todos.splice(index, 1)[0]
        saveTodos(todos)
        return `Removed: #${id} - ${removed.text}`
      },
    },
  ],
} satisfies Plugin
