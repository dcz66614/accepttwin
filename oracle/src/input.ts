/**
 * Oracle input types and loading (P032 T007, PROJECT_BOOK §12.2).
 *
 * The Oracle reads exactly three things: the frozen contract JSON, the
 * raw per-request observations, and the origin-event / reset evidence.
 * It never reads a production verdict or a production diagnostic
 * (§12.3). The input file is `accepttwin.oracle-input/v1`, written by
 * the S0 harness from the same adjudication inputs the production
 * classifier received -- the Oracle judges the same evidence, with
 * its own logic.
 */

export interface Representation {
  accept: string;
  expected_status: number;
  expected_content_type: string;
  sentinel: string;
}

export interface ContractInput {
  schema: string;
  contract_id: string;
  name: string;
  url: string;
  origin_url: string;
  representations: Record<string, Representation>;
  request_headers: Record<string, unknown>;
  cache_behavior: {
    mode: string;
    vary_accept: string;
    max_age_seconds: number | null;
  };
  limits: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface Observation {
  request_index: number;
  experiment_id: string;
  requested_representation: string;
  response_status: number;
  response_content_type: string;
  body_sha256: string;
  sentinel_match: boolean;
  cache_status: string | null;
  cache_key_sha256: string | null;
  cache_entry_id: string | null;
  origin_counter_before: number;
  origin_counter_after: number;
  origin_counter_delta: number;
}

export interface RawObservation extends Observation {
  method: string;
  url: string;
  accept: string;
  body_size: number;
  sentinel_sha256: string;
  response_headers: Record<string, string>;
  cache_status_header: string | null;
  verified_cache_state: string | null;
  cache_verification_reasons: string[];
  cache_entry_count_before: number | null;
  cache_entry_count_after: number | null;
  origin_event_present: boolean | null;
  transport_error: string | null;
}

export interface OriginEventInput {
  index: number;
  method: string;
  path: string;
  accept: string;
  status: number;
}

export interface ResetInput {
  namespace: string;
  success: boolean;
  entries_before: number;
  entries_after: number;
  entries_removed: number;
}

export interface OracleInput {
  format: string;
  contract: ContractInput;
  observations: Observation[];
  raw_observations: RawObservation[];
  origin_events: OriginEventInput[];
  origin_events_available: boolean;
  resets: ResetInput[];
}

export function parseOracleInput(text: string): OracleInput {
  const data: unknown = JSON.parse(text);
  if (typeof data !== "object" || data === null) {
    throw new Error("oracle input must be a JSON object");
  }
  const input = data as OracleInput;
  if (input.format !== "accepttwin.oracle-input/v1") {
    throw new Error(`unexpected oracle input format: ${String(input.format)}`);
  }
  return input;
}
