import * as vscode from 'vscode';
import WebSocket from 'ws';
import * as path from 'path';

let ws: WebSocket | null = null;
let panelView: vscode.WebviewView | null = null;

export function activate(context: vscode.ExtensionContext) {
    const provider = new AIAgentViewProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('ai-meeting-agent.sidebar', provider)
    );

    let startCmd = vscode.commands.registerCommand('ai-meeting-agent.start', () => {
        vscode.window.showInformationMessage('AI Meeting Agent Starting...');
        connectWebSocket();
    });
    
    context.subscriptions.push(startCmd);

    const sendCommand = (cmd: string) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            vscode.window.showErrorMessage('AI Meeting Agent is not connected.');
            return;
        }
        ws.send(JSON.stringify({ command: cmd }));
    };

    context.subscriptions.push(
        vscode.commands.registerCommand('ai-meeting-agent.generateProject', () => sendCommand('generate_project')),
        vscode.commands.registerCommand('ai-meeting-agent.updateProject', () => sendCommand('update_project')),
        vscode.commands.registerCommand('ai-meeting-agent.fixErrors', () => sendCommand('fix_errors')),
        vscode.commands.registerCommand('ai-meeting-agent.runProject', () => sendCommand('run_project'))
    );
}

function connectWebSocket() {
    if (ws) {
        ws.close();
    }
    ws = new WebSocket('ws://127.0.0.1:8080/ws');
    
    ws.on('open', () => {
        vscode.window.showInformationMessage('Connected to AI Meeting Agent backend!');
        if (panelView) {
            panelView.webview.postMessage({ type: 'status', message: 'Connected' });
        }
    });

    ws.on('message', async (data: any) => {
        try {
            const msg = JSON.parse(data.toString());
            
            // Send log to webview panel
            if (panelView) {
                panelView.webview.postMessage({ type: 'log', message: JSON.stringify(msg) });
            }

            if (msg.action === 'create_file' || msg.action === 'update_file') {
                const workspaceFolders = vscode.workspace.workspaceFolders;
                if (!workspaceFolders) {
                    vscode.window.showErrorMessage('No active workspace folder to write file to.');
                    return;
                }
                
                const filePath = path.join(workspaceFolders[0].uri.fsPath, msg.path);
                const fileUri = vscode.Uri.file(filePath);
                
                const writeData = Buffer.from(msg.content, 'utf8');
                await vscode.workspace.fs.writeFile(fileUri, writeData);
                
                vscode.window.showInformationMessage(`AI Agent updated: ${msg.path}`);
                
                // Open the file in editor
                const doc = await vscode.workspace.openTextDocument(fileUri);
                await vscode.window.showTextDocument(doc, { preview: false });
            }
        } catch (e) {
            console.error('WebSocket parsing error:', e);
        }
    });

    ws.on('close', () => {
        vscode.window.showWarningMessage('Disconnected from AI Meeting Agent.');
        if (panelView) {
            panelView.webview.postMessage({ type: 'status', message: 'Disconnected' });
        }
    });
}

class AIAgentViewProvider implements vscode.WebviewViewProvider {
    constructor(private readonly _extensionUri: vscode.Uri) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        panelView = webviewView;
        webviewView.webview.options = { enableScripts: true };
        
        webviewView.webview.onDidReceiveMessage(message => {
            switch (message.command) {
                case 'generateProject':
                    vscode.commands.executeCommand('ai-meeting-agent.generateProject');
                    return;
                case 'updateProject':
                    vscode.commands.executeCommand('ai-meeting-agent.updateProject');
                    return;
                case 'fixErrors':
                    vscode.commands.executeCommand('ai-meeting-agent.fixErrors');
                    return;
                case 'runProject':
                    vscode.commands.executeCommand('ai-meeting-agent.runProject');
                    return;
            }
        });

        webviewView.webview.html = this.getHtmlContent();
    }

    private getHtmlContent() {
        return `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <style>
                    body { font-family: sans-serif; padding: 10px; }
                    #status { font-weight: bold; margin-bottom: 10px; color: #4ade80; }
                    .log { background: #1e1e1e; padding: 8px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-bottom: 5px; word-wrap: break-word; }
                    .btn-group { display: flex; flex-direction: column; gap: 8px; margin-top: 15px; }
                    button { background: #6366f1; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; width: 100%; font-weight: bold; }
                    button:hover { background: #4f46e5; }
                    .btn-secondary { background: #374151; }
                    .btn-secondary:hover { background: #4b5563; }
                </style>
            </head>
            <body>
                <h2>AI Meeting Agent</h2>
                <div id="status">Disconnected</div>
                
                <div class="btn-group">
                    <button onclick="sendCommand('generateProject')">Generate Project</button>
                    <button class="btn-secondary" onclick="sendCommand('updateProject')">Update Project</button>
                    <button class="btn-secondary" onclick="sendCommand('fixErrors')">Fix Errors</button>
                    <button class="btn-secondary" onclick="sendCommand('runProject')">Run Project</button>
                </div>

                <div style="margin-top: 15px;">
                    <h3>Activity Log</h3>
                    <div id="logs"></div>
                </div>
                <script>
                    const vscode = acquireVsCodeApi();
                    
                    function sendCommand(cmd) {
                        vscode.postMessage({ command: cmd });
                    }

                    window.addEventListener('message', event => {
                        const message = event.data;
                        if (message.type === 'status') {
                            document.getElementById('status').innerText = message.message;
                            if (message.message === 'Disconnected') {
                                document.getElementById('status').style.color = '#ef4444';
                            } else {
                                document.getElementById('status').style.color = '#4ade80';
                            }
                        }
                        if (message.type === 'log') {
                            const logsDiv = document.getElementById('logs');
                            const div = document.createElement('div');
                            div.className = 'log';
                            div.innerText = message.message;
                            logsDiv.prepend(div);
                        }
                    });
                </script>
            </body>
            </html>
        `;
    }
}

export function deactivate() {
    if (ws) ws.close();
}
