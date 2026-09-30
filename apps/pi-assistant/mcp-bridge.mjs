import { execFile as execFileCallback } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const execFile = promisify(execFileCallback);
const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));

export async function compareViaMcp(input, { signal, runner = execFile } = {}) {
  const env = { ...process.env, OPENAI_AGENTS_DISABLE_TRACING: "1" };
  delete env.CEREBRAS_API_KEY;
  delete env.OPENAI_API_KEY;
  delete env.ANTHROPIC_API_KEY;

  const args = [
    "run", "--frozen", "agent-lab-mcp-client", "--no-tracing",
    "call", "compare_lists", "--arguments", JSON.stringify(input),
  ];
  let stdout;
  try {
    ({ stdout } = await runner("uv", args, {
      cwd: root, env, signal, timeout: 20000, maxBuffer: 65536,
    }));
  } catch (error) {
    if (signal?.aborted) throw new Error("Local MCP comparison cancelled.");
    throw new Error(`Local MCP comparison failed (${error.code ?? "process error"}). Check uv sync and the MCP server.`);
  }
  let result;
  try {
    result = JSON.parse(stdout);
  } catch {
    throw new Error("Local MCP comparison returned invalid JSON.");
  }
  const fields = ["same", "source_only", "baseline_only"];
  if (!result || Object.keys(result).sort().join() !== fields.sort().join() ||
      fields.some((field) => !Array.isArray(result[field]) || result[field].some((item) => typeof item !== "string"))) {
    throw new Error("Local MCP comparison returned an invalid result.");
  }
  return result;
}
