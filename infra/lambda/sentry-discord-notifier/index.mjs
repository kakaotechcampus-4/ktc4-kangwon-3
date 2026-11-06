import { createHmac, timingSafeEqual } from 'node:crypto';

const COLORS = { fatal: 0x8b0000, error: 0xe03e2f, warning: 0xf2c94c, info: 0x3b82f6 };

// Sentry 프로젝트 id → 환경변수 이름
const ROUTES = {
  '4512179672907776': 'discord_webhook_be', // palgijeone-backend
  '4512373384675328': 'discord_webhook_fe', // palgijeone-fe
  '4512367873753088': 'discord_webhook_ai', // palgijeone-ai
};

const verified = (raw, signature) => {
  if (!signature || !process.env.CLIENT_SECRET) return false;
  const expected = createHmac('sha256', process.env.CLIENT_SECRET).update(raw, 'utf8').digest('hex');
  return expected.length === signature.length && timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
};

const pickWebhook = (projectId) => process.env[ROUTES[String(projectId)]];

export const handler = async (req) => {
  const h = req.headers ?? {};
  const resource = h['sentry-hook-resource'];
  const raw = req.body ? (req.isBase64Encoded ? Buffer.from(req.body, 'base64').toString() : req.body) : '';

  if (!verified(raw, h['sentry-hook-signature'])) return { statusCode: 401 };
  // 알림 규칙(event_alert)만 Discord로 보냄. issue 구독 등은 중복이라 무시
  if (resource !== 'event_alert' || !raw) return { statusCode: 200 };

  const body = JSON.parse(raw);
  const ev = body.data?.event ?? {};
  console.log(JSON.stringify({ project_id: ev.project, rule: body.data?.triggered_rule }));

  const webhook = pickWebhook(ev.project);
  if (!webhook) {
    console.log('no route for project', ev.project);
    return { statusCode: 200 };
  }

  const fields = [
    ['env', ev.environment], ['level', ev.level],
  ].filter(([, v]) => v).map(([name, v]) => ({ name, value: String(v).slice(0, 1024), inline: true }));

  const res = await fetch(webhook, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      embeds: [{
        title: String(ev.title ?? 'Sentry alert').slice(0, 256),
        url: ev.web_url,
        description: String(ev.culprit ?? '').slice(0, 4000),
        color: COLORS[ev.level] ?? 0x808080,
        fields,
      }],
    }),
  });
  if (!res.ok) console.log('discord', res.status, await res.text());
  return { statusCode: res.ok ? 200 : 502 };
};
