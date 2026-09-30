#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const binary = resolve(root, "apps/pi-assistant/node_modules/.bin/pi");
const extension = resolve(root, "apps/pi-assistant/extension.mjs");
const skill = resolve(root, "apps/pi-assistant/skills/independent-checks/SKILL.md");

function readCerebrasKey() {
  if (process.env.CEREBRAS_API_KEY?.trim()) return process.env.CEREBRAS_API_KEY.trim();
  const envFile = resolve(root, ".env");
  if (!existsSync(envFile)) return "";
  const lines = readFileSync(envFile, "utf8").split(/\r?\n/);
  const line = lines.find((item) => /^\s*CEREBRAS_API_KEY\s*=/.test(item));
  if (!line) return "";
  const raw = line.slice(line.indexOf("=") + 1).trim();
  const value = raw.match(/^(["'])(.*)\1\s*(?:#.*)?$/)?.[2] ?? raw.replace(/\s+#.*$/, "");
  return value.trim();
}

if (!existsSync(binary)) {
  console.error("Pi is not installed. Run: mise exec -- pnpm install --frozen-lockfile --ignore-scripts");
  process.exit(1);
}

const key = readCerebrasKey();
if (!key) {
  console.error("CEREBRAS_API_KEY is missing. Set it in the ignored .env file or the environment.");
  process.exit(1);
}

const agentDir = resolve(root, ".local/pi");
mkdirSync(agentDir, { recursive: true, mode: 0o700 });
const env = { ...process.env, CEREBRAS_API_KEY: key, PI_CODING_AGENT_DIR: agentDir };
delete env.OPENAI_API_KEY;
delete env.ANTHROPIC_API_KEY;

const child = spawnSync(binary, [
  "--provider", "cerebras", "--model", "qwen-3.8-27b", "--thinking", "off",
  "--extension", extension, "--skill", skill,
  ...process.argv.slice(2),
], { cwd: root, env, stdio: "inherit" });

if (child.error) {
  console.error(`Could not start Pi: ${child.error.message}`);
  process.exit(1);
}
if (child.signal) process.kill(process.pid, child.signal);
process.exit(child.status ?? 1);
