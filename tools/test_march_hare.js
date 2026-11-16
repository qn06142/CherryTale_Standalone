const { spawn } = require('child_process');
const http = require('http');

async function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

async function run() {
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
    '--headless',
    '--remote-debugging-port=9223',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    'http://localhost:8000/?char=b004_01_hcg1'
  ]);

  await new Promise(r => setTimeout(r, 2000));

  try {
    const tabs = await getJson('http://localhost:9223/json');
    const target = tabs.find(t => t.url && t.url.includes('localhost:8000'));
    if (!target) {
      console.error('Could not find localhost:8000 tab! Tabs:', tabs.map(t => t.url));
      return;
    }

    console.log('Connecting to:', target.webSocketDebuggerUrl);
    const ws = new WebSocket(target.webSocketDebuggerUrl);

    let msgId = 1;
    const callbacks = new Map();

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.method === 'Console.messageAdded') {
        console.log('[BROWSER CONSOLE]', msg.params.message.level, msg.params.message.text);
      } else if (msg.method === 'Runtime.consoleAPICalled') {
        const args = msg.params.args.map(a => a.value || a.description || JSON.stringify(a)).join(' ');
        console.log('[BROWSER LOG]', msg.params.type, args);
      } else if (msg.method === 'Runtime.exceptionThrown') {
        console.error('[BROWSER EXCEPTION]', msg.params.exceptionDetails);
      } else if (msg.id && callbacks.has(msg.id)) {
        callbacks.get(msg.id)(msg);
        callbacks.delete(msg.id);
      }
    };

    function send(method, params = {}) {
      return new Promise((resolve) => {
        const id = msgId++;
        callbacks.set(id, resolve);
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    await new Promise(r => ws.onopen = r);

    await send('Console.enable');
    await send('Runtime.enable');
    await send('Page.enable');

    console.log('Waiting 3s for initial load...');
    await new Promise(r => setTimeout(r, 3000));

    // Evaluate state of player
    const res = await send('Runtime.evaluate', {
      expression: `JSON.stringify({
        typeofActivePlayer: typeof activePlayer,
        hasPlayer: !!activePlayer,
        currentStem: typeof currentSpineStem !== 'undefined' ? currentSpineStem : null,
        containerHtml: document.getElementById('spinePlayerContainer') ? document.getElementById('spinePlayerContainer').innerHTML.slice(0, 200) : null,
        modalDisplay: document.getElementById('modalOverlay').style.display,
        spineDisplay: document.getElementById('spinePlayerContainer').style.display
      })`,
      returnByValue: true
    });
    console.log('Initial State:', res.result ? res.result.result.value : res);

    // Try clicking an animation button
    console.log('\n--- Clicking Finished_01 button ---');
    const clickRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const btns = Array.from(document.querySelectorAll('.anim-btn'));
        const finishBtn = btns.find(b => b.textContent.includes('Finished_01') && !b.textContent.includes('mark'));
        if (finishBtn) {
          finishBtn.click();
          return JSON.stringify({ clicked: finishBtn.textContent });
        }
        return JSON.stringify({ clicked: false, error: 'Button not found' });
      })()`,
      returnByValue: true
    });
    console.log('Click result:', clickRes.result ? clickRes.result.result.value : clickRes);

    await new Promise(r => setTimeout(r, 2000));

    // Check player status after clicking
    const afterRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const p = activePlayer;
        if (!p) return JSON.stringify({ error: 'No activePlayer', typeofP: typeof activePlayer });
        const entry = p.animationState ? p.animationState.getCurrent(0) : null;
        return JSON.stringify({
          paused: p.isPaused,
          animName: entry ? entry.animation.name : null,
          trackTime: entry ? entry.trackTime : null,
          animationTime: entry ? entry.getAnimationTime() : null,
          isComplete: entry ? entry.isComplete() : null,
          skeletonBones: p.skeleton ? p.skeleton.bones.length : 0,
          skeletonSlots: p.skeleton ? p.skeleton.slots.length : 0,
          skin: p.skeleton && p.skeleton.skin ? p.skeleton.skin.name : null
        });
      })()`,
      returnByValue: true
    });
    console.log('After Click Player State:', afterRes.result ? afterRes.result.result.value : afterRes);

    // Wait 1s and check trackTime advances
    await new Promise(r => setTimeout(r, 1000));
    const advanceRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const p = activePlayer;
        const entry = p && p.animationState ? p.animationState.getCurrent(0) : null;
        return JSON.stringify({
          trackTime: entry ? entry.trackTime : null
        });
      })()`,
      returnByValue: true
    });
    console.log('Time after 1s:', advanceRes.result ? advanceRes.result.result.value : advanceRes);

    // Take screenshot
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    const fs = require('fs');
    fs.writeFileSync('test_screenshot.png', Buffer.from(shot.result.data, 'base64'));
    console.log('Saved test_screenshot.png');

    ws.close();
  } catch (err) {
    console.error('Test error:', err);
  } finally {
    edge.kill();
  }
}

run();
