const { sendText, sendButtons, sendList } = require('./whatsapp');
const { DAY_ORDER, PRICE_TEXT, hoursText, slotsForDay } = require('./business');
const { getSession, setSession, resetSession } = require('./sessions');

const MENU_BUTTONS = [
  { id: 'menu_hours', title: 'שעות פתיחה' },
  { id: 'menu_price', title: 'מחיר' },
  { id: 'menu_book', title: 'קביעת תור' },
];

function ownerPhone() {
  return process.env.OWNER_PHONE;
}

async function sendMenu(to, greeting) {
  await sendButtons(to, greeting, MENU_BUTTONS);
}

async function startBooking(to) {
  setSession(to, 'awaiting_name', {});
  await sendText(to, 'מעולה! איך קוראים לך? (שם מלא)');
}

async function askDay(to) {
  const rows = DAY_ORDER.map((day) => ({ id: `day_${day}`, title: day }));
  await sendList(to, 'לאיזה יום תרצה/י לקבוע תור?', 'בחירת יום', [
    { title: 'ימים פתוחים', rows },
  ]);
}

async function askTime(to, day) {
  const slots = slotsForDay(day);
  if (!slots.length) {
    await sendText(to, 'ביום הזה אנחנו סגורים, אפשר לבחור יום אחר.');
    await askDay(to);
    return;
  }
  const rows = slots.map((slot) => ({ id: `time_${slot}`, title: slot }));
  await sendList(to, `שעות פנויות ביום ${day}:`, 'בחירת שעה', [
    { title: 'שעות זמינות', rows },
  ]);
}

async function confirmBooking(to, data) {
  const summary = `סיכום התור:\nשם: ${data.name}\nיום: ${data.day}\nשעה: ${data.time}\n\nלאשר?`;
  await sendButtons(to, summary, [
    { id: 'confirm_yes', title: 'אישור' },
    { id: 'confirm_no', title: 'ביטול' },
  ]);
}

async function notifyOwner(customerPhone, data) {
  const owner = ownerPhone();
  if (!owner) return;
  const text = [
    '📅 תור חדש דרך הבוט!',
    `שם: ${data.name}`,
    `טלפון: +${customerPhone}`,
    `יום: ${data.day}`,
    `שעה: ${data.time}`,
  ].join('\n');
  await sendText(owner, text);
}

async function forwardToOwner(customerPhone, text) {
  const owner = ownerPhone();
  if (!owner) return;
  await sendText(owner, `💬 הודעה חדשה מלקוח (+${customerPhone}):\n${text}`);
}

function normalize(text) {
  return (text || '').trim();
}

function matchesKeyword(text, keywords) {
  const lower = normalize(text).toLowerCase();
  return keywords.some((k) => lower.includes(k));
}

async function handleIncomingMessage(message) {
  const from = message.from;
  const session = getSession(from);

  let interactiveId = null;
  let text = null;

  if (message.type === 'interactive') {
    const interactive = message.interactive;
    if (interactive.type === 'button_reply') interactiveId = interactive.button_reply.id;
    if (interactive.type === 'list_reply') interactiveId = interactive.list_reply.id;
  } else if (message.type === 'text') {
    text = message.text.body;
  }

  // Global reset command, always available
  if (text && matchesKeyword(text, ['תפריט', 'menu', 'התחל'])) {
    resetSession(from);
    await sendMenu(from, 'הנה האפשרויות:');
    return;
  }

  if (interactiveId === 'menu_hours' || matchesKeyword(text, ['שעות', 'פתוח', 'פתוחים'])) {
    await sendText(from, hoursText());
    return;
  }

  if (interactiveId === 'menu_price' || matchesKeyword(text, ['מחיר', 'עולה', 'עלות'])) {
    await sendText(from, PRICE_TEXT);
    return;
  }

  if (
    interactiveId === 'menu_book' ||
    matchesKeyword(text, ['תור', 'לקבוע', 'להזמין', 'זמין'])
  ) {
    if (session.state === 'idle') {
      await startBooking(from);
      return;
    }
  }

  if (session.state === 'awaiting_name' && text) {
    setSession(from, 'awaiting_day', { name: normalize(text) });
    await askDay(from);
    return;
  }

  if (session.state === 'awaiting_day' && interactiveId && interactiveId.startsWith('day_')) {
    const day = interactiveId.replace('day_', '');
    setSession(from, 'awaiting_time', { ...session.data, day });
    await askTime(from, day);
    return;
  }

  if (session.state === 'awaiting_time' && interactiveId && interactiveId.startsWith('time_')) {
    const time = interactiveId.replace('time_', '');
    const data = { ...session.data, time };
    setSession(from, 'awaiting_confirm', data);
    await confirmBooking(from, data);
    return;
  }

  if (session.state === 'awaiting_confirm' && interactiveId === 'confirm_yes') {
    await notifyOwner(from, session.data);
    await sendText(from, 'התור נקבע ✅ אורי יצור איתך קשר לאישור סופי. תודה!');
    resetSession(from);
    return;
  }

  if (session.state === 'awaiting_confirm' && interactiveId === 'confirm_no') {
    await sendText(from, 'בוטל. אפשר לכתוב "תפריט" כדי להתחיל מחדש.');
    resetSession(from);
    return;
  }

  // Greeting for a brand-new conversation
  if (session.state === 'idle' && matchesKeyword(text, ['שלום', 'הי', 'hi', 'hello', 'בוקר', 'ערב'])) {
    await sendMenu(from, 'היי! כאן פדיקור של אורי 🦶 איך אפשר לעזור?');
    return;
  }

  // Fallback: forward anything unrecognized to the owner
  if (text) {
    await forwardToOwner(from, text);
    await sendText(from, 'תודה על ההודעה! אורי יחזור אליך בהקדם 🙏\n(אפשר לכתוב "תפריט" לאפשרויות מהירות)');
  }
}

module.exports = { handleIncomingMessage };
