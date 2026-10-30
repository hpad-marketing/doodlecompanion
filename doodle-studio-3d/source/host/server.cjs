// Local server for Doodle Studio 3D: serves the editor and its /api (files, renders).
// Bound to 127.0.0.1 only. The 2D Doodle Studio's ports (54183 etc.) are never touched.
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

module.exports = function start({ root, port = 54190, api = {}, mcp = null }) {
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://127.0.0.1');
      if (url.pathname === '/mcp' && mcp) {
        let body = '';
        for await (const chunk of req) body += chunk;
        return mcp(req, res, body);
      }
      if (url.pathname.startsWith('/api/')) {
        // the editor's own calls: same-origin only
        const o = req.headers.origin;
        if (o && o !== `http://127.0.0.1:${port}`) { res.writeHead(403); return res.end('Forbidden origin'); }
        const name = url.pathname.slice(5);
        const fn = api[name];
        if (!fn) { res.writeHead(404); return res.end('No such action: ' + name); }
        let body = '';
        for await (const chunk of req) body += chunk;
        const out = await fn(body ? JSON.parse(body) : {}, req);
        res.writeHead(200, { 'content-type': 'application/json' });
        return res.end(JSON.stringify(out ?? {}));
      }
      let p = path.normalize(decodeURIComponent(url.pathname)).replace(/^([/\\])+/, '');
      if (!p) p = 'index.html';
      const file = path.join(root, p);
      if (!file.startsWith(root)) { res.writeHead(403); return res.end(); }
      const data = await fs.promises.readFile(file);
      res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
      res.end(data);
    } catch (e) {
      res.writeHead(e.code === 'ENOENT' ? 404 : 500, { 'content-type': 'text/plain' });
      res.end(String(e.message || e));
    }
  });
  return new Promise((ok, fail) => { server.once('error', fail); server.listen(port, '127.0.0.1', () => ok(server)); });
};
