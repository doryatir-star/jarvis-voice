require('dotenv').config();
const express = require('express');
const { handleIncomingMessage } = require('./lib/flow');

const app = express();
app.use(express.json());

app.get('/', (req, res) => {
  res.send('פדיקור של אורי – בוט וואטסאפ פעיל');
});

// Meta calls this once, when you register the webhook, to verify you own it.
app.get('/webhook', (req, res) => {
  const mode = req.query['hub.mode'];
  const token = req.query['hub.verify_token'];
  const challenge = req.query['hub.challenge'];

  if (mode === 'subscribe' && token === process.env.VERIFY_TOKEN) {
    res.status(200).send(challenge);
  } else {
    res.sendStatus(403);
  }
});

// Meta calls this for every incoming message / status update.
app.post('/webhook', async (req, res) => {
  res.sendStatus(200);

  try {
    const entry = req.body.entry?.[0];
    const change = entry?.changes?.[0];
    const value = change?.value;
    const message = value?.messages?.[0];

    if (message) {
      await handleIncomingMessage(message);
    }
  } catch (err) {
    console.error('Error handling webhook event', err);
  }
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`WhatsApp bot listening on port ${port}`);
});
