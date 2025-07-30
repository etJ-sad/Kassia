export class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.listeners = [];
        this.connect();
    }

    connect() {
        this.ws = new WebSocket(this.url);
        this.ws.addEventListener('message', (e) => {
            const data = JSON.parse(e.data);
            this.listeners.forEach(cb => cb(data));
        });
        this.ws.addEventListener('close', () => {
            setTimeout(() => this.connect(), 1000);
        });
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    onMessage(cb) {
        this.listeners.push(cb);
    }
}
