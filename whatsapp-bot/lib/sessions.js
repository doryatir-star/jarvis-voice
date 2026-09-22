const SESSION_TTL_MS = 30 * 60 * 1000;

const sessions = new Map();

function getSession(phone) {
  const existing = sessions.get(phone);
  if (existing && Date.now() - existing.updatedAt < SESSION_TTL_MS) {
    return existing;
  }
  const fresh = { state: 'idle', data: {}, updatedAt: Date.now() };
  sessions.set(phone, fresh);
  return fresh;
}

function setSession(phone, state, data = {}) {
  sessions.set(phone, { state, data, updatedAt: Date.now() });
}

function resetSession(phone) {
  sessions.delete(phone);
}

setInterval(() => {
  const now = Date.now();
  for (const [phone, session] of sessions) {
    if (now - session.updatedAt > SESSION_TTL_MS) sessions.delete(phone);
  }
}, 5 * 60 * 1000).unref();

module.exports = { getSession, setSession, resetSession };
