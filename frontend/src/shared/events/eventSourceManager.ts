/**
 * Single shared `EventSource` connection to `GET /events`, ref-counted
 * across every `useEventStream` call site.
 *
 * Why a module-level singleton rather than one `EventSource` per hook
 * call: `docs/contracts/ipc-rules.md` rule 1 says the sidecar is the
 * sole channel, and this Part's own adversarial-audit checklist names
 * "duplicate EventSource connections" and "one connection per render"
 * as things to avoid. A feature screen with, say, three
 * `useEventStream("analysis.progress", ...)` / `useEventStream(
 * "ti.enrichment.completed", ...)` calls mounted at once should open
 * exactly one HTTP connection to `/events`, not three — the backend
 * already supports many independent subscribers (Part 3's
 * `EventBroker`), but there is no reason for one browser tab to open
 * more than one when every listener wants events from the same stream.
 *
 * Lifecycle: the first `subscribe()` call triggers connection; the
 * `EventSource` is closed the moment the last subscriber unsubscribes
 * (`refCount` back to 0). React StrictMode's mount→unmount→mount does
 * not cause a double connection or a leaked one, because subscribe/
 * unsubscribe are symmetric and ref-counted rather than relying on any
 * one component's lifecycle alone.
 */

import { getSidecarOrigin } from "../api/client";
import type { EventName, SocIqEvent } from "./types";

export type EventStreamStatus =
  | "idle" // no subscriber has ever connected
  | "connecting" // resolving the sidecar origin, or EventSource is CONNECTING
  | "open" // EventSource is OPEN
  | "unavailable" // origin could not be resolved (expected pre-Part-4B state)
  | "closed"; // explicitly closed (ref count reached zero)

type Listener = (event: SocIqEvent<unknown>) => void;

interface Subscriber {
  eventName: EventName;
  listener: Listener;
}

let source: EventSource | null = null;
let status: EventStreamStatus = "idle";
let connectToken = 0; // guards against a stale async origin-resolution
// applying itself after a newer connect/disconnect cycle has already
// happened (e.g. subscribe() then immediately unsubscribe() before the
// origin promise settles).

const subscribers = new Set<Subscriber>();
const statusSubscribers = new Set<(status: EventStreamStatus) => void>();
const attachedListeners = new Map<EventName, (raw: MessageEvent) => void>();

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Structural validation against the actual wire shape produced by
 * `Event.to_dict()` (`app/application/events.py`) via
 * `_format_sse_event` (`app/api/app.py`) — re-verified directly this
 * Part, not assumed from the pre-existing placeholder type (see
 * `types.ts`'s module docstring for what changed). Returns `null` for
 * anything that doesn't match, rather than casting, per this Part's
 * "do not blindly cast `JSON.parse(...) as SomeType`" requirement — a
 * malformed frame must not reach a listener, and must not crash the
 * React tree that reads its result.
 */
export function parseSocIqEvent(raw: string): SocIqEvent<unknown> | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }

  if (!isPlainObject(parsed)) {
    return null;
  }

  const {
    event,
    version,
    correlation_id: correlationId,
    investigation_id: investigationId,
    timestamp,
    payload,
    event_id: eventId,
  } = parsed;

  if (typeof event !== "string") return null;
  if (typeof version !== "number") return null;
  if (typeof correlationId !== "string") return null;
  if (investigationId !== null && typeof investigationId !== "number") {
    return null;
  }
  if (typeof timestamp !== "string") return null;
  if (!isPlainObject(payload)) return null;
  if (typeof eventId !== "string") return null;

  return {
    event: event as EventName,
    version,
    correlation_id: correlationId,
    investigation_id: investigationId,
    timestamp,
    payload,
    event_id: eventId,
  };
}

function setStatus(next: EventStreamStatus): void {
  if (status === next) return;
  status = next;
  statusSubscribers.forEach((fn) => fn(next));
}

function dispatch(eventName: EventName, event: SocIqEvent<unknown>): void {
  subscribers.forEach((subscriber) => {
    if (subscriber.eventName === eventName) {
      subscriber.listener(event);
    }
  });
}

function handlerFor(eventName: EventName): (raw: MessageEvent) => void {
  return (raw: MessageEvent) => {
    // Malformed payloads are logged without the payload body itself --
    // this Part's "do not log entire potentially sensitive event
    // payloads to the console" requirement. The event name and length
    // are enough to diagnose a contract drift without risking a leak.
    const parsedEvent = parseSocIqEvent(
      typeof raw.data === "string" ? raw.data : "",
    );
    if (parsedEvent === null) {
      // eslint-disable-next-line no-console
      console.warn(
        `SOC-IQ: dropped malformed SSE frame for "${eventName}" ` +
          `(${typeof raw.data === "string" ? raw.data.length : 0} bytes)`,
      );
      return;
    }
    dispatch(eventName, parsedEvent);
  };
}

/** Attach a native listener for `eventName` if one isn't already on `source`. */
function ensureEventNameAttached(eventName: EventName): void {
  if (source === null || attachedListeners.has(eventName)) {
    return;
  }
  const handler = handlerFor(eventName);
  source.addEventListener(eventName, handler as EventListener);
  attachedListeners.set(eventName, handler);
}

function attachAllSubscribedEventNames(): void {
  subscribers.forEach((subscriber) => ensureEventNameAttached(subscriber.eventName));
}

function teardownSource(nextStatus: EventStreamStatus): void {
  if (source !== null) {
    source.close();
  }
  source = null;
  attachedListeners.clear();
  setStatus(nextStatus);
}

/**
 * Resolve the sidecar origin and open the `EventSource`. Safe to call
 * repeatedly (e.g. once per `subscribe()`) — a no-op if already
 * connecting/open, and re-attempts origin resolution if the previous
 * attempt left the connection `"unavailable"`. This is deliberately
 * *not* a timer-driven retry loop (this Part's "do not introduce
 * aggressive retry behavior" requirement) — it only retries when a
 * new subscriber actually shows up wanting the stream.
 */
function connect(): void {
  if (source !== null || status === "connecting") {
    return;
  }

  setStatus("connecting");
  const token = ++connectToken;

  getSidecarOrigin()
    .then((origin) => {
      if (token !== connectToken || subscribers.size === 0) {
        // Superseded by a newer connect() call, or every subscriber
        // unsubscribed while this promise was in flight.
        return;
      }

      const url = `${origin.replace(/\/+$/, "")}/events`;
      const nextSource = new EventSource(url);

      nextSource.onopen = () => {
        if (token === connectToken) setStatus("open");
      };

      // Native `EventSource` retries the connection on its own after
      // an error (per spec) unless `.close()` was called -- this
      // manager relies on that built-in, bounded-by-the-browser
      // behavior rather than adding a second reconnect mechanism on
      // top of it. `readyState` tells us which case we're in.
      nextSource.onerror = () => {
        if (token !== connectToken) return;
        if (nextSource.readyState === EventSource.CONNECTING) {
          setStatus("connecting");
        } else if (nextSource.readyState === EventSource.CLOSED) {
          setStatus("unavailable");
        }
      };

      source = nextSource;
      attachAllSubscribedEventNames();
    })
    .catch(() => {
      if (token === connectToken) {
        // Expected pre-Part-4B state -- see client.ts's
        // `getSidecarOrigin` doc comment. Not an application error.
        setStatus("unavailable");
      }
    });
}

/**
 * Subscribe to one event name. Returns an unsubscribe function; call it
 * from a `useEffect` cleanup (or equivalent) to guarantee no leaked
 * listener -- mirrors the backend's own disconnect-cleanup contract
 * (`app/api/app.py`'s `_sse_event_stream` `finally` block) on the
 * frontend side.
 */
export function subscribe(eventName: EventName, listener: Listener): () => void {
  const subscriber: Subscriber = { eventName, listener };
  subscribers.add(subscriber);

  if (source !== null) {
    ensureEventNameAttached(eventName);
  } else {
    connect();
  }

  return () => {
    subscribers.delete(subscriber);

    const stillNeedsEventName = Array.from(subscribers).some(
      (s) => s.eventName === eventName,
    );
    if (!stillNeedsEventName && source !== null) {
      const handler = attachedListeners.get(eventName);
      if (handler) {
        source.removeEventListener(eventName, handler as EventListener);
        attachedListeners.delete(eventName);
      }
    }

    if (subscribers.size === 0) {
      connectToken += 1; // invalidate any in-flight connect()
      teardownSource("closed");
    }
  };
}

/** Current connection status, for callers that want to surface it. */
export function getStatus(): EventStreamStatus {
  return status;
}

/** Subscribe to status changes. Returns an unsubscribe function. */
export function subscribeStatus(
  listener: (status: EventStreamStatus) => void,
): () => void {
  statusSubscribers.add(listener);
  return () => {
    statusSubscribers.delete(listener);
  };
}
