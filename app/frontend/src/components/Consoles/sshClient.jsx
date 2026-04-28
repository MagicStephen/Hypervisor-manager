import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import {
  createNodeConsoleSession,
  getNodeConsoleWsUrl,
} from "../../services/NodeService";

export default function SimpleSSHConsole({
  serverId,
  nodeId,
  sshUsername,
  sshPassword,
  sshPort = 22,
}) {
  const terminalRef = useRef(null);

  useEffect(() => {
    if (!terminalRef.current || !serverId || !nodeId) return;

    const term = new Terminal({
      cursorBlink: true,
      convertEol: true,
      cols: 120,
      rows: 50,
    });

    term.open(terminalRef.current);
    term.writeln("Připojuji se...");

    let ws = null;
    let inputDisposable = null;

    const start = async () => {
      try {
        const result = await createNodeConsoleSession(serverId, nodeId);

        const consoleToken = result.console_token;

        if (!consoleToken) {
          throw new Error("Console token chybí v odpovědi");
        }

        const wsUrl = getNodeConsoleWsUrl(serverId, nodeId, consoleToken);

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          term.writeln("Připojeno");

          ws.send(
            JSON.stringify({
              type: "auth",
              ssh_username: sshUsername,
              ssh_password: sshPassword,
              ssh_port: sshPort,
              cols: 120,
              rows: 30,
            })
          );
        };

        ws.onmessage = (event) => {
          term.write(event.data);
        };

        ws.onclose = () => {
          term.writeln("\r\nOdpojeno");
        };

        ws.onerror = () => {
          term.writeln("\r\nChyba websocketu");
        };

        inputDisposable = term.onData((data) => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(
              JSON.stringify({
                type: "input",
                data,
              })
            );
          }
        });
      } catch (e) {
        term.writeln(`\r\nChyba: ${e instanceof Error ? e.message : "unknown"}`);
      }
    };

    start();

    return () => {
      if (inputDisposable) inputDisposable.dispose();
      if (ws) ws.close();
      term.dispose();
    };
  }, [serverId, nodeId, sshUsername, sshPassword, sshPort]);

  return (
    <div
      ref={terminalRef}
      className="rounded h-100 overflow-y-auto overflow-x-hidden p-0"
      style={{
        width: "100%",
       
        minHeight: 0,
      }}
    />
  );
}