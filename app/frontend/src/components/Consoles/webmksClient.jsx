export async function createWebMksClient({
  container,
  wsUrl,
  onConnect,
  onDisconnect,
  onError,
  fitToParent = true,
  rescale = true,
  changeResolution = true,
  background = 'rgb(24, 24, 24)',
}) {
  if (!container) throw new Error('WebMKS container is required');
  if (!wsUrl) throw new Error('WebMKS wsUrl is required');

  const WMKS = window.WMKS;
  if (!WMKS) throw new Error('WMKS is not loaded');

  container.innerHTML = '';
  container.style.position = 'relative';
  container.style.display = 'flex';
  container.style.alignItems = 'center';
  container.style.justifyContent = 'center';
  container.style.overflow = 'hidden';
  container.style.background = background;

  const mountNode = document.createElement('div');
  mountNode.id = `wmks-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  mountNode.style.width = '100%';
  mountNode.style.height = '100%';
  mountNode.style.display = 'flex';
  mountNode.style.alignItems = 'center';
  mountNode.style.justifyContent = 'center';
  mountNode.style.overflow = 'hidden';
  mountNode.style.position = 'relative';
  mountNode.style.background = background;

  container.appendChild(mountNode);

  const wmks = WMKS.createWMKS(mountNode.id, {
    fitToParent,
    rescale,
    changeResolution,
  });

  const centerConsoleContent = () => {
    try {
      const nodes = mountNode.querySelectorAll('canvas, img, video, svg');
      nodes.forEach((node) => {
        node.style.maxWidth = '100%';
        node.style.maxHeight = '100%';
        node.style.margin = 'auto';
        node.style.display = 'block';
      });

      const wrappers = mountNode.querySelectorAll('div');
      wrappers.forEach((node) => {
        if (node === mountNode) return;
        node.style.maxWidth = '100%';
        node.style.maxHeight = '100%';
      });
    } catch (error) {
      console.warn('WMKS centering adjustment failed:', error);
    }
  };

  const handleState = (event, data) => {
    const state = data?.state;

    if (state === WMKS.CONST.ConnectionState.CONNECTED) {
      centerConsoleContent();
      onConnect?.(data || null);
    }

    if (
      state === WMKS.CONST.ConnectionState.DISCONNECTED ||
      state === WMKS.CONST.ConnectionState.DISCONNECTING
    ) {
      onDisconnect?.(data || null);
    }
  };

  const handleError = (event, data) => {
    onError?.(data || event || null);
  };

  wmks.register(WMKS.CONST.Events.CONNECTION_STATE_CHANGE, handleState);
  wmks.register(WMKS.CONST.Events.ERROR, handleError);

  await wmks.connect(wsUrl);

  centerConsoleContent();

  const resizeObserver = new ResizeObserver(() => {
    centerConsoleContent();
  });

  resizeObserver.observe(container);
  resizeObserver.observe(mountNode);

  return {
    type: 'webmks',
    raw: wmks,

    disconnect() {
      try {
        resizeObserver.disconnect();
        wmks.unregister(WMKS.CONST.Events.CONNECTION_STATE_CHANGE, handleState);
        wmks.unregister(WMKS.CONST.Events.ERROR, handleError);
        wmks.disconnect?.();
        wmks.destroy?.();
      } finally {
        container.innerHTML = '';
      }
    },
  };
}