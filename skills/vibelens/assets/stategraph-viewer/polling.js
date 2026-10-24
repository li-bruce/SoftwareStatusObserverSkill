// Owns the polling lifetime; the view controller only handles a returned snapshot.
/** Poll one task at a time and expose pause/disposal controls for the active view. */
export function createPoller(
  task,
  { enabled = () => true, interval = 400, onError = console.error } = {},
) {
  let timer = null,
    inFlight = false,
    closed = false;
  function pause() {
    clearTimeout(timer);
    timer = null;
  }
  async function run() {
    if (closed || inFlight || !enabled()) return;
    pause();
    inFlight = true;
    try {
      await task();
    } catch (error) {
      onError(error);
    } finally {
      inFlight = false;
      if (!closed && enabled()) timer = setTimeout(run, interval);
    }
  }
  return {
    run,
    pause,
    close() {
      closed = true;
      pause();
    },
    get inFlight() {
      return inFlight;
    },
  };
}
