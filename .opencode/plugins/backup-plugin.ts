import type { Plugin } from "@opencode-ai/plugin"
import { existsSync, mkdirSync, copyFileSync, statSync } from "fs"
import { join, dirname, basename } from "path"

const BACKUP_DIR = ".opencode/backups"
const MAX_BACKUPS = 10

function ensureBackupDir(dir: string) {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true })
  }
}

function getBackupPath(filePath: string): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-")
  const dir = dirname(filePath)
  const name = basename(filePath)
  const backupDir = join(dir, BACKUP_DIR)
  ensureBackupDir(backupDir)
  return join(backupDir, `${name}.${timestamp}.backup`)
}

function cleanOldBackups(dir: string, name: string) {
  if (!existsSync(dir)) return
  
  const { readdirSync, unlinkSync } = require("fs")
  const files = readdirSync(dir)
    .filter((f: string) => f.startsWith(name) && f.endsWith(".backup"))
    .sort()
    .reverse()
  
  if (files.length > MAX_BACKUPS) {
    files.slice(MAX_BACKUPS).forEach((f: string) => {
      try { unlinkSync(join(dir, f)) } catch {}
    })
  }
}

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "edit" || input.tool === "write") {
        const filePath = input.args?.filePath
        if (filePath && existsSync(filePath)) {
          try {
            const stat = statSync(filePath)
            if (stat.isFile()) {
              const backupPath = getBackupPath(filePath)
              copyFileSync(filePath, backupPath)
              const dir = dirname(filePath)
              const name = basename(filePath)
              cleanOldBackups(join(dir, BACKUP_DIR), name)
              console.log(`[backup] Saved: ${backupPath}`)
            }
          } catch (err) {
            console.error(`[backup] Failed:`, err)
          }
        }
      }
    }
  }
}) satisfies Plugin