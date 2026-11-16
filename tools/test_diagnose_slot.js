const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');

async function run() {
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
    '--headless', '--remote-debugging-port=9227', '--disable-gpu',
    'http://localhost:8000/?char=b004_01_hcg1'
  ]);
  await new Promise(r => setTimeout(r, 2000));
  try {
    const tabs = await new Promise((res, rej) => http.get('http://localhost:9227/json', r => {
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
    await send('Page.enable');
    await new Promise(r => setTimeout(r, 3000));

    // Check each light slot bounds, blendMode, attachment
    const res = await send('Runtime.evaluate', {
      expression: `(() => {
        const p = activePlayer;
        if (!p) return 'no player';
        return JSON.stringify(p.skeleton.slots.filter(s => /light/i.test(s.data.name)).map(s => {
          return {
            name: s.data.name,
            blendMode: s.data.blendMode,
            att: s.attachment ? s.attachment.name : null,
            color: s.color
          };
        }));
      })()`,
      returnByValue: true
    });
    console.log('Light slots details:', res.result.result.value);

    // Disable only BG_Light
    await send('Runtime.evaluate', {
      expression: `(() => {
        const p = activePlayer;
        const s = p.skeleton.findSlot('BG_Light');
        if (s) s.attachment = null;
      })()`
    });

    await new Promise(r => setTimeout(r, 500));
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('test_no_bg_light_only.png', Buffer.from(shot.result.data, 'base64'));
    console.log('Saved test_no_bg_light_only.png');
    ws.close();
  } finally {
    edge.kill();
  }
}
run();
