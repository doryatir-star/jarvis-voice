(function () {
  var HOURS = {
    'ראשון': { start: '16:30', end: '18:00' },
    'שני': { start: '16:30', end: '18:00' },
    'שלישי': { start: '16:30', end: '18:00' },
    'רביעי': { start: '16:30', end: '18:00' },
    'חמישי': { start: '16:30', end: '18:00' },
    'שישי': { start: '11:00', end: '13:00' }
  };

  var PHONE_INTL = '972527338868';

  document.getElementById('year').textContent = new Date().getFullYear();

  var todayIndex = new Date().getDay(); // 0 = Sunday ... 6 = Saturday
  var todayRow = document.querySelector('#hoursTable tr[data-day="' + todayIndex + '"]');
  if (todayRow) todayRow.classList.add('today');

  function timeToMinutes(t) {
    var parts = t.split(':');
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  }

  function minutesToTime(m) {
    var h = Math.floor(m / 60);
    var min = m % 60;
    return (h < 10 ? '0' + h : h) + ':' + (min < 10 ? '0' + min : min);
  }

  function buildSlots(day) {
    var range = HOURS[day];
    if (!range) return [];
    var slots = [];
    var start = timeToMinutes(range.start);
    var end = timeToMinutes(range.end);
    for (var m = start; m < end; m += 30) {
      slots.push(minutesToTime(m));
    }
    return slots;
  }

  var daySelect = document.getElementById('day');
  var timeSelect = document.getElementById('time');

  daySelect.addEventListener('change', function () {
    var slots = buildSlots(daySelect.value);
    timeSelect.innerHTML = '';
    if (!slots.length) {
      var opt = document.createElement('option');
      opt.textContent = 'אין שעות זמינות';
      opt.disabled = true;
      opt.selected = true;
      timeSelect.appendChild(opt);
      return;
    }
    var placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.disabled = true;
    placeholder.selected = true;
    placeholder.textContent = 'בחר/י שעה';
    timeSelect.appendChild(placeholder);

    slots.forEach(function (slot) {
      var o = document.createElement('option');
      o.value = slot;
      o.textContent = slot;
      timeSelect.appendChild(o);
    });
  });

  var form = document.getElementById('bookingForm');
  form.addEventListener('submit', function (e) {
    e.preventDefault();

    var name = document.getElementById('name').value.trim();
    var phone = document.getElementById('phone').value.trim();
    var day = daySelect.value;
    var time = timeSelect.value;
    var notes = document.getElementById('notes').value.trim();

    if (!name || !phone || !day || !time) return;

    var lines = [
      'היי אורי, אשמח לקבוע תור לפדיקור יבש',
      'שם: ' + name,
      'טלפון: ' + phone,
      'יום: ' + day,
      'שעה: ' + time
    ];
    if (notes) lines.push('הערות: ' + notes);

    var message = encodeURIComponent(lines.join('\n'));
    var url = 'https://wa.me/' + PHONE_INTL + '?text=' + message;

    var fallback = document.getElementById('waFallback');
    fallback.href = url;
    fallback.hidden = false;

    var link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });
})();
