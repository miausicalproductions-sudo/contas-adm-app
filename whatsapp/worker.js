// Contas ADM — Worker da Cloudflare (grátis)
// 1) Recebe os avisos da Meta (WhatsApp dos clientes) e do Telegram e repassa ao Apps Script na hora.
//    O Apps Script não consegue responder direto (o Google redireciona o endereço), por isso este intermediário.
// 2) Página do Story (/s): a arte pronta para mandar aos Stories do Instagram, as telas para copiar e o botão "Postei".
//
// Variáveis (opcional: o painel já preenche os valores abaixo no botão "Copiar o código pronto"):
//   GAS_URL      = endereço do Apps Script, terminando em /exec
//   GAS_KEY      = a chave de acesso do painel (Config → Copiar a chave)
//   VERIFY_TOKEN = o "token de verificação" mostrado no painel (Config → WhatsApp dos clientes)
//   APP_SECRET   = a chave secreta do app da Meta (Configurações do app → Básico → Chave secreta do app)

// O painel já preenche estes valores no botão "Copiar o código pronto" (aí não precisa criar as variáveis na Cloudflare)
const CFG = { GAS_URL: '', GAS_KEY: '', VERIFY_TOKEN: '', APP_SECRET: '' };

export default {
  async fetch(req, env0, ctx) {
    const env = { GAS_URL: (env0 && env0.GAS_URL) || CFG.GAS_URL, GAS_KEY: (env0 && env0.GAS_KEY) || CFG.GAS_KEY, VERIFY_TOKEN: (env0 && env0.VERIFY_TOKEN) || CFG.VERIFY_TOKEN, APP_SECRET: (env0 && env0.APP_SECRET) || CFG.APP_SECRET };
    const url = new URL(req.url), path = url.pathname.replace(/\/+$/, '') || '/';

    // Página do Story e arquivos
    if (req.method === 'GET' && path === '/s') return storyPage(url, env);
    if (req.method === 'GET' && path === '/f') return storyFile(url, env);
    if (req.method === 'POST' && path === '/done') return storyDone(url, env);

    // Telegram (modo instantâneo): o segredo vem no cabeçalho e o Apps Script confere
    if (req.method === 'POST' && path === '/tg') {
      const sec = req.headers.get('x-telegram-bot-api-secret-token') || '', raw = await req.text();
      if (!sec) return new Response('sem segredo', { status: 401 });
      ctx.waitUntil(fetch(env.GAS_URL + '?tg=' + encodeURIComponent(sec), { method: 'POST', body: raw, headers: { 'Content-Type': 'text/plain' }, redirect: 'follow' }).catch(() => {}));
      return new Response('ok');
    }

    // WhatsApp: a Meta confere o endereço uma vez, quando o webhook é cadastrado
    if (req.method === 'GET') {
      if (url.searchParams.get('hub.mode') === 'subscribe') {
        return url.searchParams.get('hub.verify_token') === env.VERIFY_TOKEN
          ? new Response(url.searchParams.get('hub.challenge') || '', { status: 200 })
          : new Response('token de verificação diferente do painel', { status: 403 });
      }
      if (env.GAS_URL && env.GAS_KEY) ctx.waitUntil(gas(env, { action: 'wkHello', origin: url.origin }).catch(() => {}));   // o Apps Script aprende o endereço deste Worker
      return new Response('Contas ADM: Worker do WhatsApp no ar.' + (env.GAS_URL && env.GAS_KEY && env.VERIFY_TOKEN && env.APP_SECRET ? '' : ' Falta preencher as variáveis.'), { status: 200, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }
    if (req.method !== 'POST') return new Response('método não aceito', { status: 405 });

    // WhatsApp: confere a assinatura (só a Meta conhece a chave secreta do app)
    const raw = await req.text();
    if (!(await assinaturaOk(raw, req.headers.get('x-hub-signature-256') || '', env.APP_SECRET || ''))) {
      return new Response('assinatura inválida', { status: 401 });
    }
    // Responde "ok" na hora (a Meta exige) e repassa ao Apps Script em segundo plano
    let data = null;
    try { data = JSON.parse(raw); } catch (e) { return new Response('ok', { status: 200 }); }
    ctx.waitUntil(repassar(env, data, url.origin));
    return new Response('ok', { status: 200 });
  }
};

async function gas(env, body) {
  const r = await fetch(env.GAS_URL, { method: 'POST', body: JSON.stringify(Object.assign({ key: env.GAS_KEY }, body)), headers: { 'Content-Type': 'text/plain' }, redirect: 'follow' });
  const j = JSON.parse(await r.text()); if (j && j.error) throw new Error(j.error); return j;
}

async function repassar(env, data, origin) {
  for (let i = 0; i < 2; i++) {                       // uma nova tentativa se o Google falhar
    try { await gas(env, { action: 'waHook', data, origin }); return; } catch (e) { /* tenta de novo */ }
    await new Promise(ok => setTimeout(ok, 1500));
  }
}

async function hmacHex(secret, msg) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return [...new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(msg)))].map(b => b.toString(16).padStart(2, '0')).join('');
}
const igual = (a, b) => { if (a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i); return d === 0; };
async function linkOk(url, env) {
  const p = url.searchParams.get('p') || '', k = url.searchParams.get('k') || '';
  return !!p && !!env.GAS_KEY && igual(k, (await hmacHex(env.GAS_KEY, 's:' + p)).slice(0, 32)) ? { p, k } : null;
}

async function assinaturaOk(raw, header, secret) {
  if (!secret || !header.startsWith('sha256=')) return false;
  return igual(header.slice(7), await hmacHex(secret, raw));
}

const esc = t => String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const TN = { reels: 'Reels', stories: 'Stories', feed: 'Feed', carrossel: 'Carrossel' };

async function storyFile(url, env) {
  const ok = await linkOk(url, env); if (!ok) return new Response('link inválido', { status: 403 });
  try {
    const f = await gas(env, { action: 'fileGet', post: ok.p, id: url.searchParams.get('f') || '' });
    const bin = Uint8Array.from(atob(f.b64), c => c.charCodeAt(0));
    return new Response(bin, { headers: { 'Content-Type': f.mime || 'application/octet-stream', 'Content-Disposition': 'inline; filename="' + (f.name || 'arte').replace(/"/g, '') + '"', 'Cache-Control': 'private, max-age=900' } });
  } catch (e) { return new Response('não consegui buscar o arquivo: ' + e.message, { status: 502 }); }
}

async function storyDone(url, env) {
  const ok = await linkOk(url, env); if (!ok) return new Response('link inválido', { status: 403 });
  try { await gas(env, { action: 'storyDone', id: ok.p, k: ok.k }); return new Response('{"ok":1}', { headers: { 'Content-Type': 'application/json' } }); }
  catch (e) { return new Response(JSON.stringify({ error: e.message }), { status: 502, headers: { 'Content-Type': 'application/json' } }); }
}

async function storyPage(url, env) {
  const ok = await linkOk(url, env); if (!ok) return new Response('Link inválido ou antigo. Abra de novo pelo aviso mais recente.', { status: 403, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
  let d; try { d = await gas(env, { action: 'storyData', id: ok.p }); } catch (e) { return new Response('Não consegui abrir o post agora: ' + e.message, { status: 502, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }); }
  const p = d.post, c = d.co, q = 'p=' + encodeURIComponent(ok.p) + '&k=' + ok.k;
  const media = (d.files || []).filter(f => /^(image|video)\//.test(f.mime)).map(f => ({ src: '/f?' + q + '&f=' + encodeURIComponent(f.id), mime: f.mime, name: f.name }));
  const html = `<!doctype html><html lang=pt-BR><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><title>${esc(p.txt || 'Story')} · ${esc(c.name)}</title>
<style>:root{--c:${esc(c.color)}}*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;background:#141320;color:#fff;padding:16px 16px calc(24px + env(safe-area-inset-bottom))}
.top{display:flex;align-items:center;gap:10px;margin-bottom:12px}.dot{width:12px;height:12px;border-radius:50%;background:var(--c);flex:none}.top b{font-size:17px}.top small{display:block;opacity:.65}
.media{display:grid;gap:10px}.m{position:relative;border-radius:18px;overflow:hidden;background:#000;max-width:420px;margin:0 auto;width:100%}.m img,.m video{display:block;width:100%;max-height:68vh;object-fit:contain;background:#000}
.m button{position:absolute;left:10px;right:10px;bottom:10px;border:0;border-radius:14px;padding:14px;font:700 16px system-ui;color:#fff;background:linear-gradient(90deg,#f58529,#dd2a7b 50%,#8134af)}
.m button:disabled{opacity:.6}.card{background:#1f1d30;border-radius:16px;padding:12px 14px;margin-top:12px}.card h3{margin:0 0 6px;font-size:13px;opacity:.7;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.card p{margin:0;white-space:pre-wrap}.row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}.b2{border:1px solid #ffffff30;background:none;color:#fff;border-radius:12px;padding:10px 14px;font:600 14px system-ui}
.ok{background:#2F9E44;border-color:#2F9E44}.fig{border-left:4px solid var(--c)}.mu{opacity:.65;font-size:13px}#msg{min-height:20px;text-align:center;margin-top:10px;opacity:.85}</style></head><body>
<div class=top><i class=dot></i><div><b>${esc(p.txt || TN[p.type] || 'Post')}</b><small>${esc(c.name)} · ${esc(TN[p.type] || '')} · ${esc(d.when || '')}${p.st === 'postado' ? ' · ✓ postado' : ''}</small></div></div>
<div class=media>${media.length ? media.map((m, i) => `<div class=m>${/^video/.test(m.mime) ? `<video src="${m.src}" controls playsinline preload=metadata></video>` : `<img src="${m.src}" alt="">`}<button data-i=${i}>${media.length > 1 ? (i + 1) + '/' + media.length + ' · ' : ''}${p.type === 'stories' ? 'Mandar para os Stories' : 'Mandar para o Instagram'}</button></div>`).join('') : '<div class=card><p>A arte ainda não está no Drive.</p></div>'}</div>
<div id=msg class=mu>${p.type === 'stories' ? 'Toque no botão e escolha <b>Instagram → Stories</b>. Lá você coloca a música e a figurinha.' : 'Toque no botão e escolha <b>Instagram</b> (Feed ou Reels). A legenda está logo abaixo para copiar.'}</div>
${p.fig ? `<div class="card fig"><h3>Figurinha: ${esc(p.figName)}</h3><p>${esc(p.figtx || '')}</p>${p.figtx ? `<div class=row><button class=b2 data-copy="${esc(p.figtx)}">Copiar o texto da figurinha</button></div>` : ''}</div>` : ''}
${p.cap ? `<div class=card><h3>${p.type === 'stories' ? 'Telas' : 'Legenda'}</h3><p>${esc(p.cap)}</p><div class=row><button class=b2 data-copy="${esc(p.cap)}">Copiar</button></div></div>` : ''}
<div class=row style="justify-content:center;margin-top:16px"><button class="b2 ok" id=done>${p.st === 'postado' ? '✓ Já está como postado' : '✅ Postei'}</button></div>
<script>
const M=${JSON.stringify(media)},F=[],msg=t=>document.getElementById('msg').textContent=t;
M.forEach((m,i)=>fetch(m.src).then(r=>r.blob()).then(b=>{F[i]=new File([b],(m.name||('arte'+(i+1))).replace(/[^\\w.-]+/g,'_'),{type:m.mime})}).catch(()=>{}));
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;
 if(b.dataset.copy!==undefined){try{await navigator.clipboard.writeText(b.dataset.copy);b.textContent='Copiado ✓'}catch(x){prompt('Copie:',b.dataset.copy)}return}
 if(b.id=='done'){b.disabled=true;const r=await fetch('/done?${q}',{method:'POST'}).then(r=>r.json()).catch(()=>({}));b.textContent=r.ok?'✓ Marcado como postado':'Não deu, tente de novo';b.disabled=!!r.ok;return}
 const i=+b.dataset.i,f=F[i];if(!f){msg('Carregando a arte… toque de novo em 2 segundos.');return}
 if(navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f]});msg('No Instagram, escolha Stories.')}catch(x){}}
 else{const a=document.createElement('a');a.href=URL.createObjectURL(f);a.download=f.name;a.click();msg('Arte salva. Abra o Instagram e escolha a arte na galeria.')}});
</script></body></html>`;
  return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
}
