import test from "node:test";
import assert from "node:assert/strict";
import registerAgentLab from "../extension.mjs";
import { compareViaMcp } from "../mcp-bridge.mjs";

test("Pi registers one comparison tool with both required arrays", () => {
  const registered = [];
  registerAgentLab({ registerTool: (tool) => registered.push(tool) });
  assert.equal(registered.length, 1);
  assert.equal(registered[0].name, "compare_lists");
  assert.deepEqual([...registered[0].parameters.required].sort(), ["baseline", "source"]);
});

test("bridge invokes the locked Python MCP path without model keys", async () => {
  const input = { source: ["A", "B"], baseline: ["B", "C"] };
  const result = { same: ["B"], source_only: ["A"], baseline_only: ["C"] };
  const runner = async (command, args, options) => {
    assert.equal(command, "uv");
    assert.deepEqual(args.slice(0, 7), ["run", "--frozen", "agent-lab-mcp-client", "--no-tracing", "call", "compare_lists", "--arguments"]);
    assert.deepEqual(JSON.parse(args[7]), input);
    assert.equal(options.env.CEREBRAS_API_KEY, undefined);
    assert.equal(options.env.OPENAI_API_KEY, undefined);
    assert.equal(options.env.ANTHROPIC_API_KEY, undefined);
    return { stdout: JSON.stringify(result) };
  };
  assert.deepEqual(await compareViaMcp(input, { runner }), result);
});

test("bridge rejects malformed MCP results", async () => {
  await assert.rejects(
    compareViaMcp({ source: [], baseline: [] }, { runner: async () => ({ stdout: '{"same":[]}' }) }),
    /invalid result/,
  );
});
