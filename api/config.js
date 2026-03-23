export default function handler(_request, response) {
  const apiBase = (process.env.CODE2VIDEO_API_BASE || '').replace(/\/+$/, '');
  response.setHeader('Content-Type', 'application/javascript; charset=utf-8');
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.status(200).send(`window.CODE2VIDEO_API_BASE = ${JSON.stringify(apiBase)};\n`);
}
