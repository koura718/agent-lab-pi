import { Type } from "typebox";
import { compareViaMcp } from "./mcp-bridge.mjs";

// Pi 0.87.1 exposes registerTool. Delegate to the existing MCP diagnostic client.
export default function registerAgentLab(pi) {
  pi.registerTool({
    name: "compare_lists",
    label: "Compare lists (local MCP)",
    description: "Compare two string lists via the repository's Python MCP server. Return sorted same, source_only and baseline_only arrays.",
    parameters: Type.Object({
      source: Type.Array(Type.String({ minLength: 1, maxLength: 256 }), { maxItems: 1000 }),
      baseline: Type.Array(Type.String({ minLength: 1, maxLength: 256 }), { maxItems: 1000 }),
    }, { additionalProperties: false }),
    async execute(_callId, params, signal) {
      const result = await compareViaMcp(params, { signal });
      return { content: [{ type: "text", text: JSON.stringify(result) }], details: result };
    },
  });
}
