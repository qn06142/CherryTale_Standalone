const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');

async function run() {
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
    '--headless', '--remote-debugging-port=9229', '--disable-gpu',
    'http://localhost:8000/?char=b004_01_hcg1'
  ]);
  await new Promise(r => setTimeout(r, 2000));
  try {
    const tabs = await new Promise((res, rej) => http.get('http://localhost:9229/json', r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d)));
    }).on('error', rej));
    const target = tabs.find(t => t.url && t.url.includes('localhost:8000'));
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise(r => ws.onopen = r);
    let msgId = 1;
    const callbacks = new Map();
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.method === 'Console.messageAdded') {
        console.log('[BROWSER CONSOLE]', m.params.message.level, m.params.message.text);
      } else if (m.method === 'Runtime.consoleAPICalled') {
        console.log('[BROWSER LOG]', m.params.type, m.params.args.map(a => a.value || a.description || JSON.stringify(a)).join(' '));
      } else if (m.method === 'Runtime.exceptionThrown') {
        console.error('[BROWSER EXCEPTION]', m.params.exceptionDetails);
      } else if (m.id && callbacks.has(m.id)) {
        callbacks.get(m.id)(m);
        callbacks.delete(m.id);
      }
    };
    function send(m, p={}) {
      return new Promise(res => {
        const id = msgId++; callbacks.set(id, res); ws.send(JSON.stringify({id, method: m, params: p}));
      });
    }
    await send('Console.enable');
    await send('Runtime.enable');
    await send('Page.enable');

    console.log('Waiting 3s for gallery load...');
    await new Promise(r => setTimeout(r, 3000));

    // Test a sequence of animations for March Hare
    const animsToTest = ['Finished_01', 'Insert_01', 'Idle_01', 'Liquid_01', 'Womanbody_01'];
    
    for (const anim of animsToTest) {
      console.log(`\n=== Testing animation: ${anim} ===`);
      const clickRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const btns = Array.from(document.querySelectorAll('.anim-btn'));
          const btn = btns.find(b => b.textContent.includes('${anim}') && !b.textContent.includes('mark'));
          if (btn) {
            btn.click();
            return { found: true, label: btn.textContent.trim() };
          }
          return { found: false };
        })()`,
        returnByValue: true
      });
      console.log('Click result:', clickRes.result.result.value);

      // Wait 1.5s
      await new Promise(r => setTimeout(r, 1500));

      const state1 = await send('Runtime.evaluate', {
        expression: `(() => {
          const p = window.activePlayer;
          if (!p || !p.animationState) return { error: 'No player' };
          const entry = p.animationState.getCurrent(0);
          return {
            anim: entry ? entry.animation.name : null,
            trackTime: entry ? entry.trackTime : null,
            isPlaying: p.isPlaying,
            isPaused: p.isPaused
          };
        })()`,
        returnByValue: true
      });
      console.log('State at T0:', state1.result.result.value);

      // Wait another 1s to verify advance
      await new Promise(r => setTimeout(r, 1000));
      const state2 = await send('Runtime.evaluate', {
        expression: `(() => {
          const p = window.activePlayer;
          const entry = p && p.animationState ? p.animationState.getCurrent(0) : null;
          return {
            trackTime: entry ? entry.trackTime : null
          };
        })()`,
        returnByValue: true
      });
      console.log('State at T+1s:', state2.result.result.value);

      const delta = (state2.result.result.value.trackTime || 0) - (state1.result.result.value.trackTime || 0);
      console.log(`Playback advance delta: ${delta.toFixed(3)}s`);

      // Screenshot for this animation
      const shot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(`test_anim_${anim}.png`, Buffer.from(shot.result.data, 'base64'));
      console.log(`Saved screenshot test_anim_${anim}.png`);
    }

    // Now test March Hare Normal CG b004_01_CG
    console.log('\n=== Testing March Hare Normal CG (b004_01_CG) ===');
    await send('Runtime.evaluate', {
      expression: `(() => {
        const char = models.find(m => m.stem === 'b004_01_CG');
        if (char) openModal(char);
      })()`
    });

    await new Promise(r => setTimeout(r, 2000));
    const cgState = await send('Runtime.evaluate', {
      expression: `(() => {
        const p = window.activePlayer;
        if (!p || !p.animationState) return { error: 'No player' };
        const entry = p.animationState.getCurrent(0);
        return {
          stem: window.currentSpineStem,
          anim: entry ? entry.animation.name : null,
          trackTime: entry ? entry.trackTime : null
        };
      })()`,
      returnByValue: true
    });
    console.log('CG Initial State:', cgState.result.result.value);

    const shotCG = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('test_b004_cg.png', Buffer.from(shotCG.result.data, 'base64'));
    console.log('Saved screenshot test_b004_cg.png');

    ws.close();
  } finally {
    edge.kill();
  }
}

run();
