/**
 * Oracle CLI (P032 T007, PROJECT_BOOK §12).
 *
 * Usage:
 *   node oracle/src/index.ts --input <oracle-input.json> --output <result.json>
 *
 * Reads only the contract + raw observations in the input file and
 * writes the independently computed verdict, diagnostics and first
 * error. It never imports production Python code and never reads a
 * production verdict (§12.3).
 */

import { readFileSync, writeFileSync } from "node:fs";
import { parseOracleInput } from "./input.ts";
import { evaluateScenario } from "./oracle.ts";

function parseArgs(argv: string[]): { input: string; output: string } {
  let input = "";
  let output = "";
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--input" && i + 1 < argv.length) input = argv[i + 1];
    if (argv[i] === "--output" && i + 1 < argv.length) output = argv[i + 1];
  }
  if (!input || !output) {
    throw new Error("usage: node oracle/src/index.ts --input <oracle-input.json> --output <result.json>");
  }
  return { input, output };
}

const { input, output } = parseArgs(process.argv.slice(2));
const oracleInput = parseOracleInput(readFileSync(input, "utf-8"));
const result = evaluateScenario(oracleInput);
writeFileSync(output, JSON.stringify(result, null, 2) + "\n", "utf-8");
