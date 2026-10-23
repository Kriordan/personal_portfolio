import type { ErrorEvent } from '@sentry/react-native';

const uuid = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const codes = new Set([
  'invalid_job', 'invalid_request', 'provider_auth', 'provider_quota',
  'invalid_summary', 'failed', 'unknown',
]);
export type FailurePhase = 'read' | 'summary' | 'status';
export interface OperationFailure {
  phase: FailurePhase;
  requestId: string;
  status: number;
  code: unknown;
}

/** Expected validation/offline/recovery outcomes are not incidents. */
export function failureTags(failure: OperationFailure) {
  if (!uuid.test(failure.requestId)) return null;
  const code = typeof failure.code === 'string' && codes.has(failure.code)
    ? failure.code : 'unknown';
  if (failure.status === 404 || failure.status === 410 || failure.status === 401 ||
      failure.status === 403 || failure.status === 409 || failure.status === 429 ||
      failure.code === 'unsupported' || failure.code === 'unavailable') return null;
  if (failure.status !== 400 && failure.status < 500) return null;
  return {
    operation: 'jobwizard.extraction', phase: failure.phase,
    request_id: failure.requestId, status: String(failure.status), code,
  };
}

/** Only source locations are retained from frames; never locals or source excerpts. */
function safeFilename(value: unknown) {
  if (typeof value !== 'string') return undefined;
  // Preserve the bundle path needed for source-map matching, without query tokens.
  return value.split(/[?#]/, 1)[0].slice(0, 512);
}

/** Rebuild JS events from an allowlist; arbitrary message/context data is excluded. */
export function scrubMobileEvent(event: ErrorEvent, hint?: { attachments?: unknown[] }): ErrorEvent {
  if (hint) delete hint.attachments;
  const tags: Record<string, string> = {};
  const incoming = event.tags ?? {};
  if (incoming.operation === 'jobwizard.extraction') tags.operation = incoming.operation;
  if (['read', 'summary', 'status'].includes(String(incoming.phase))) tags.phase = String(incoming.phase);
  if (uuid.test(String(incoming.request_id))) tags.request_id = String(incoming.request_id);
  if (/^[45]\d\d$/.test(String(incoming.status))) tags.status = String(incoming.status);
  if (codes.has(String(incoming.code))) tags.code = String(incoming.code);
  if (/^[a-f0-9]{7,40}$/.test(String(incoming.commit))) tags.commit = String(incoming.commit);
  const contexts: NonNullable<ErrorEvent['contexts']> = {};
  for (const [kind, fields] of Object.entries({
    os: ['name', 'version', 'build'],
    device: ['family', 'model', 'arch', 'simulator'],
    app: ['app_identifier', 'app_version', 'app_build'],
    runtime: ['name', 'version'],
  })) {
    const original = event.contexts?.[kind];
    if (!original) continue;
    contexts[kind] = Object.fromEntries(fields.flatMap((field) => {
      const value = original[field];
      return typeof value === 'boolean' || typeof value === 'string' && value.length <= 100
        ? [[field, value]] : [];
    }));
  }
  return {
    type: event.type,
    event_id: event.event_id,
    timestamp: event.timestamp,
    platform: event.platform,
    level: event.level,
    release: event.release,
    dist: event.dist,
    environment: event.environment,
    // Debug IDs link the uploaded bundle/source map to this specific build.
    debug_meta: event.debug_meta,
    sdk: event.sdk,
    user: { ip_address: '0.0.0.0' },
    tags,
    contexts,
    message: tags.operation ? 'Jobwizard extraction request failed' : undefined,
    exception: event.exception ? {
      values: event.exception.values?.map((exception) => ({
        type: /^[\w.$]{1,100}$/.test(exception.type ?? '') ? exception.type : 'Error',
        value: 'Unexpected application error',
        mechanism: exception.mechanism ? {
          type: exception.mechanism.type,
          handled: exception.mechanism.handled,
        } : undefined,
        stacktrace: exception.stacktrace ? {
          frames: exception.stacktrace.frames?.map((frame) => ({
            filename: safeFilename(frame.filename),
            abs_path: safeFilename(frame.abs_path),
            function: frame.function,
            lineno: frame.lineno,
            colno: frame.colno,
            in_app: frame.in_app,
            instruction_addr: frame.instruction_addr,
            module: frame.module,
          })),
        } : undefined,
      })),
    } : undefined,
  };
}
