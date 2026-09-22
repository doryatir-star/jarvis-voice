const GRAPH_VERSION = 'v19.0';

function apiUrl() {
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  return `https://graph.facebook.com/${GRAPH_VERSION}/${phoneNumberId}/messages`;
}

async function callGraphApi(payload) {
  const res = await fetch(apiUrl(), {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${process.env.WHATSAPP_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const body = await res.text();
    console.error('WhatsApp API error', res.status, body);
  }

  return res;
}

function sendText(to, body) {
  return callGraphApi({
    messaging_product: 'whatsapp',
    to,
    type: 'text',
    text: { body },
  });
}

function sendButtons(to, bodyText, buttons) {
  return callGraphApi({
    messaging_product: 'whatsapp',
    to,
    type: 'interactive',
    interactive: {
      type: 'button',
      body: { text: bodyText },
      action: {
        buttons: buttons.map((b) => ({
          type: 'reply',
          reply: { id: b.id, title: b.title },
        })),
      },
    },
  });
}

function sendList(to, bodyText, buttonText, sections) {
  return callGraphApi({
    messaging_product: 'whatsapp',
    to,
    type: 'interactive',
    interactive: {
      type: 'list',
      body: { text: bodyText },
      action: { button: buttonText, sections },
    },
  });
}

module.exports = { sendText, sendButtons, sendList };
