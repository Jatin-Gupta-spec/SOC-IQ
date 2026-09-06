/**
 * Optional connection-status hook for the shared SSE connection.
 *
 * No existing UI consumes connection status yet (no status indicator
 * exists anywhere in `frontend/src/` today, confirmed by inspection --
 * this Part's own instructions say to integrate with one if it exists,
 * otherwise keep this internal and not build one). This hook exists so
 * a future feature component *can* show "connecting" / "live" /
 * "unavailable" without needing to reach into
 * `eventSourceManager.ts` directly -- it adds no UI itself.
 */

import { useEffect, useState } from "react";
import {
  getStatus,
  subscribeStatus,
  type EventStreamStatus,
} from "./eventSourceManager";

export function useEventStreamStatus(): EventStreamStatus {
  const [status, setStatus] = useState<EventStreamStatus>(getStatus);

  useEffect(() => {
    return subscribeStatus(setStatus);
  }, []);

  return status;
}
