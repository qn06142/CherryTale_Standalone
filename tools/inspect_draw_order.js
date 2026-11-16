const http = require('http');
const { spawn } = require('child_process');

async function run() {
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
    '--headless', '--remote-debugging-port=9225', '--disable-gpu',
    'http://localhost:8000/?char=b004_01_hcg1'
  ]);
  await new Promise(r => setTimeout(r, 2000));
  try {
    const tabs = await new Promise((res, rej) => http.get('http://localhost:9225/json', r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d)));
    }).on('error', rej));
    const target = tabs.find(t => t.url && t.url.includes('localhost:8000'));
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise(r => ws.onopen = r);
    let msgId = 1;
    const callbacks = new Map();
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.id && callbacks.has(m.id)) { callbacks.get(m.id)(m); callbacks.delete(m.id); }
    };
    function send(m, p={}) {
      return new Promise(res => {
        const id = msgId++; callbacks.set(id, res); ws.send(JSON.stringify({id, method: m, params: p}));
      });
    }
    await send('Runtime.enable');
    await new Promise(r => setTimeout(r, 3000));
    
    // Inspect drawOrder
    const res = await send('Runtime.evaluate', {
      expression: `(() => {
        const p = activePlayer;
        if (!p || !p.skeleton) return 'No skeleton';
        return JSON.stringify(p.skeleton.drawOrder.map((s, idx) => {
          const att = s.getAttachment();
          return {
            index: idx,
            slot: s.data.name,
            blendMode: s.data.blendMode,
            attachment: att ? att.name : null,
            color: s.color,
            bone: s.bone.data.name
          };
        }).filter(x => x.attachment));
      })()`,
      returnByValue: true
    });
    console.log(res.result.result.value);
    ws.close();
  } finally {
    edge.kill();
  }
}
run();
