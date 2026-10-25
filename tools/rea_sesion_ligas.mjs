// Sesion MCP local de REA: reutiliza el analisis de un binario entre consultas.
// No ejecuta el cliente del juego; el proveedor Ghidra analiza una copia.
import { Client } from 'file:///G:/REA/node_modules/@modelcontextprotocol/client/dist/index.mjs';
import { StdioClientTransport } from 'file:///G:/REA/node_modules/@modelcontextprotocol/client/dist/stdio.mjs';
import { createInterface } from 'node:readline';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const client = new Client({ name: 'ao-league-investigation', version: '1' });
const transport = new StdioClientTransport({
  command: process.execPath,
  args: ['G:/REA/_npm/package/scripts/rea.mjs', 'mcp'],
  env: { ...process.env, GHIDRA_INSTALL_DIR: 'G:/ghidra',
    JAVA_HOME: 'C:/Program Files/Eclipse Adoptium/jdk-25.0.2.10-hotspot' },
  stderr: 'inherit',
});
await client.connect(transport);
const directory = resolve('docs/rea_evidence');
await mkdir(directory, { recursive: true });
console.log('REA_CONNECTED');
let opened = false;
const input = createInterface({ input: process.stdin, terminal: false });
try {
  for await (const line of input) {
    if (!line.trim()) continue;
    const request = JSON.parse(line);
    if (request.name === 'exit') break;
    if (request.name === 'tool_names') {
      console.log(JSON.stringify((await client.listTools()).tools.map(t => t.name)));
      continue;
    }
    if (request.name === 'schemas') {
      const list = await client.listTools();
      console.log(JSON.stringify(list.tools.filter(t => request.tools.includes('*') || request.tools.includes(t.name))
        .map(t => ({ name: t.name, inputSchema: t.inputSchema }))));
      continue;
    }
    try {
      const result = await client.callTool({ name: request.name, arguments: request.arguments ?? {} },
        { timeout: 600000, maxTotalTimeout: 1200000, resetTimeoutOnProgress: true });
      if (request.name === 'open_binary' && !result.isError) opened = true;
      if (request.name === 'close_binary' && !result.isError) opened = false;
      const file = `${Date.now()}_${request.name.replace(/[^a-z0-9_]/gi, '')}.json`;
      await writeFile(resolve(directory, file), JSON.stringify({ request, result }), { flag: 'wx' });
      const value = result.structuredContent ?? result.content;
      const normalized = value?.normalized_result ?? value;
      console.log(JSON.stringify({ file, isError: result.isError,
        evidence_id: value?.evidence_id,
        value: request.compact && normalized?.pseudocode
          ? { procedure: normalized.procedure?.name, pseudocode: normalized.pseudocode,
              references: normalized.references, limitations: normalized.limitations }
          : normalized }));
    } catch (error) {
      console.log(JSON.stringify({ error: String(error) }));
    }
  }
} finally {
  input.close();
  if (opened) {
    const result = await client.callTool({ name: 'close_binary', arguments: {} });
    console.log(JSON.stringify({ closed: result }));
  }
  await client.close();
}
