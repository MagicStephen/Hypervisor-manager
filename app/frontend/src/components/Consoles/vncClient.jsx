import RFB from '@novnc/novnc/';

export async function createVncClient({
  container,
  wsUrl,
  password,
  shared = true,
  viewOnly = false,
  scaleViewport = false,
  resizeSession = false,
  clipViewport = true,
  dragViewport = true,
  background = 'rgb(24, 24, 24)',
  onConnect,
  onDisconnect,
  onCredentialsRequired,
  onSecurityFailure,
  onDesktopName,
}) {
  if (!container) {
    throw new Error('VNC container is required');
  }

  if (!wsUrl) {
    throw new Error('VNC wsUrl is required');
  }

  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.alignItems = 'flex-start';
  container.style.justifyContent = 'flex-start';
  container.style.overflow = 'hidden';
  container.style.lineHeight = '0';
  container.style.background = background;

  const rfb = new RFB(container, wsUrl, { shared });

  rfb.viewOnly = viewOnly;
  rfb.scaleViewport = scaleViewport;
  rfb.resizeSession = resizeSession;
  rfb.clipViewport = clipViewport;
  rfb.dragViewport = dragViewport;
  rfb.focusOnClick = true;
  rfb.background = background;

  const handleConnect = () => {
    onConnect?.();
  };

  const handleDisconnect = (event) => {
    console.error('RFB disconnect event:', event?.detail);
    onDisconnect?.(event?.detail || null);
  };

  const handleCredentialsRequired = () => {
    console.warn('RFB credentials required');

    if (password) {
      try {
        rfb.sendCredentials({ password });
      } catch (error) {
        console.error('Failed to send VNC credentials:', error);
      }
    }

    onCredentialsRequired?.();
  };

  const handleSecurityFailure = (event) => {
    console.error('RFB security failure:', event?.detail);
    onSecurityFailure?.(event?.detail || null);
  };

  const handleDesktopName = (event) => {
    onDesktopName?.(event?.detail?.name || null);
  };

  rfb.addEventListener('connect', handleConnect);
  rfb.addEventListener('disconnect', handleDisconnect);
  rfb.addEventListener('credentialsrequired', handleCredentialsRequired);
  rfb.addEventListener('securityfailure', handleSecurityFailure);
  rfb.addEventListener('desktopname', handleDesktopName);

  return {
    type: 'vnc',

    focus() {
      try {
        rfb.focus();
      } catch (error) {
        console.error('VNC focus error:', error);
      }
    },

    sendCtrlAltDel() {
      try {
        rfb.sendCtrlAltDel();
      } catch (error) {
        console.error('VNC sendCtrlAltDel error:', error);
      }
    },

    setViewportMode({ scale, clip, drag }) {
      try {
        if (typeof scale === 'boolean') rfb.scaleViewport = scale;
        if (typeof clip === 'boolean') rfb.clipViewport = clip;
        if (typeof drag === 'boolean') rfb.dragViewport = drag;
      } catch (error) {
        console.error('VNC viewport mode error:', error);
      }
    },

    disconnect() {
      try {
        rfb.removeEventListener('connect', handleConnect);
        rfb.removeEventListener('disconnect', handleDisconnect);
        rfb.removeEventListener('credentialsrequired', handleCredentialsRequired);
        rfb.removeEventListener('securityfailure', handleSecurityFailure);
        rfb.removeEventListener('desktopname', handleDesktopName);
        rfb.disconnect();
      } catch (error) {
        console.error('VNC disconnect error:', error);
      }
    },

    raw: rfb,
  };
}