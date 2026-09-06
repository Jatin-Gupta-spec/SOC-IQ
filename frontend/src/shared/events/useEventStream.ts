/**
 * Real SSE event subscription hook, backed by the shared connection in
 * `eventSourceManager.ts`.
 *
 * `GET /events` is now a live `StreamingResponse`
 * (`docs/phase4/PHASE4D_SSE_PART3_IMPLEMENTATION.md`), so this is no
 * longer the shape-only placeholder it was in Phase 4E Part 1 — it
 * actually opens (indirectly, via the shared manager) a native
 * `EventSource` and delivers parsed, validated events to `handler`.
 *
 * The one thing this hook still cannot do end-to-end in this
 * environment is resolve a real sidecar origin — no Tauri command
 * exists yet to hand the frontend the sidecar's loopback port (see
 * `shared/api/client.ts`'s `getSidecarOrigin` doc comment and
 * `docs/phase4/PHASE4D_SSE_PART4A_IMPLEMENTATION.md`). Until that
 * exists, every subscription here settles into the manager's
 * `"unavailable"` status rather than ever reaching `"open"` — that is
 * expected, not a bug in this hook.
 */

import { useEffect, useRef } from "react";
import { subscribe } from "./eventSourceManager";
import type { EventName, SocIqEvent } from "./types";

export type EventHandler<TPayload = unknown> = (
  event: SocIqEvent<TPayload>,
) => void;

/**
 * Subscribe to one `EventName` for the lifetime of the calling
 * component. Cleans up via the manager's ref-counted `unsubscribe` on
 * unmount or when `eventName` changes, so no listener or connection
 * can leak past the component that asked for it.
 *
 * `handler` is read through a ref on every event (not captured at
 * effect-setup time), so passing a new inline function on every render
 * -- the common case for a component-scoped callback -- never causes a
 * stale closure and never needs to be memoized by the caller to stay
 * correct. The effect itself only re-subscribes when `eventName`
 * changes, not on every render (this Part's "not create one connection
 * per render" / "avoid stale closures" requirements).
 */
export function useEventStream<TPayload = unknown>(
  eventName: EventName,
  handler: EventHandler<TPayload>,
): void {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const unsubscribe = subscribe(eventName, (event) => {
      handlerRef.current(event as SocIqEvent<TPayload>);
    });
    return unsubscribe;
  }, [eventName]);
}
