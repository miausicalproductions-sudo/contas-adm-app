// Contas ADM — Worker da Cloudflare para o WhatsApp (grátis)
// Recebe os avisos da Meta (mensagens dos clientes) e repassa ao Apps Script.
// O Apps Script não consegue responder direto à Meta (o Google redireciona o endereço), por isso este intermediário.
//
// Variáveis (Cloudflare → Workers → este Worker → Settings → Variables and Secrets), todas do tipo "Secret":
//   GAS_URL      = endereço do Apps Script, terminando em /exec
//   GAS_KEY      = a chave de acesso do painel (Config → Copiar a chave)
//   VERIFY_TOKEN = o "token de verificação" mostrado no painel (Config → WhatsApp dos clientes)
//   APP_SECRET   = a chave secreta do app da Meta (Configurações do app → Básico → Chave secreta do app)

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);

    // 1) A Meta confere o endereço uma vez, quando o webhook é cadastrado
    if (req.method === 'GET') {
      if (url.searchParams.get('hub.mode') === 'subscribe') {
        return url.searchParams.get('hub.verify_token') === env.VERIFY_TOKEN
          ? new Response(url.searchParams.get('hub.challenge') || '', { status: 200 })
          : new Response('token de verificação diferente do painel', { status: 403 });
      }
      return new Response('Contas ADM: Worker do WhatsApp no ar.' + (env.GAS_URL && env.GAS_KEY && env.VERIFY_TOKEN && env.APP_SECRET ? '' : ' Falta preencher as variáveis.'), { status: 200 });
    }
    if (req.method !== 'POST') return new Response('método não aceito', { status: 405 });

    // 2) Aviso da Meta: confere a assinatura (só a Meta conhece a chave secreta do app)
    const raw = await req.text();
    if (!(await assinaturaOk(raw, req.headers.get('x-hub-signature-256') || '', env.APP_SECRET || ''))) {
      return new Response('assinatura inválida', { status: 401 });
    }

    // 3) Responde "ok" na hora (a Meta exige) e repassa ao Apps Script em segundo plano
    let data = null;
    try { data = JSON.parse(raw); } catch (e) { return new Response('ok', { status: 200 }); }
    ctx.waitUntil(repassar(env, data));
    return new Response('ok', { status: 200 });
  }
};

async function repassar(env, data) {
  const body = JSON.stringify({ action: 'waHook', key: env.GAS_KEY, data });
  for (let i = 0; i < 2; i++) {                       // uma nova tentativa se o Google falhar
    try {
      const r = await fetch(env.GAS_URL, { method: 'POST', body, headers: { 'Content-Type': 'text/plain' }, redirect: 'follow' });
      if (r.ok) return;
    } catch (e) { /* tenta de novo */ }
    await new Promise(ok => setTimeout(ok, 1500));
  }
}

async function assinaturaOk(raw, header, secret) {
  if (!secret || !header.startsWith('sha256=')) return false;
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(raw)));
  const hex = [...sig].map(b => b.toString(16).padStart(2, '0')).join('');
  const got = header.slice(7);
  if (got.length !== hex.length) return false;
  let diff = 0; for (let i = 0; i < hex.length; i++) diff |= hex.charCodeAt(i) ^ got.charCodeAt(i);
  return diff === 0;
}
