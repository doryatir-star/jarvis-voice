const HOURS = {
  'ראשון': { start: '16:30', end: '18:00' },
  'שני': { start: '16:30', end: '18:00' },
  'שלישי': { start: '16:30', end: '18:00' },
  'רביעי': { start: '16:30', end: '18:00' },
  'חמישי': { start: '16:30', end: '18:00' },
  'שישי': { start: '11:00', end: '13:00' },
};

const DAY_ORDER = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי'];

const PRICE_TEXT = 'פדיקור רגליים יבש – 50 ₪';

function hoursText() {
  const lines = DAY_ORDER.map((day) => `${day}: ${HOURS[day].start}-${HOURS[day].end}`);
  lines.push('שבת: סגור');
  return 'שעות פתיחה:\n' + lines.join('\n');
}

function timeToMinutes(t) {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}

function minutesToTime(m) {
  const h = Math.floor(m / 60);
  const min = m % 60;
  return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
}

function slotsForDay(day) {
  const range = HOURS[day];
  if (!range) return [];
  const slots = [];
  for (let m = timeToMinutes(range.start); m < timeToMinutes(range.end); m += 30) {
    slots.push(minutesToTime(m));
  }
  return slots;
}

module.exports = { HOURS, DAY_ORDER, PRICE_TEXT, hoursText, slotsForDay };
