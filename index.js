const { Client, LocalAuth } = require("whatsapp-web.js");
const axios = require("axios");
const qrcode = require("qrcode-terminal");
const express = require("express");
const fs = require("fs");

const QUEUE_FILE = "queue.json";


const client = new Client({
  authStrategy: new LocalAuth({
    dataPath: ".wwebjs_auth",
  }),
  puppeteer: {
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-accelerated-2d-canvas",
      "--no-first-run",
      "--no-zygote",
      "--disable-gpu",
      "--disable-features=site-per-process"
    ],
  },
});

const app = express();
app.use(express.json());

let isClientReady = false;

/* =========================
   QUEUE SYSTEM
========================= */

let sendFailCount = 0;
const MAX_FAILS = 3;

let messageQueue = [];
let isProcessingQueue = false;

/* Load queue */

if (fs.existsSync(QUEUE_FILE)) {
  try {
    const saved = JSON.parse(fs.readFileSync(QUEUE_FILE));
    if (Array.isArray(saved)) {
      messageQueue = saved;
      console.log("✅ Restored queue:", saved.length);
    }
  } catch {}
}

function saveQueue() {
  fs.writeFileSync(QUEUE_FILE, JSON.stringify(messageQueue));
}

function enqueueMessage(chatId, content, options = {}) {
  messageQueue.push({ chatId, content, options });
  saveQueue();
  processQueue();
}

async function processQueue() {

  if (isProcessingQueue) return;
  if (!isClientReady) return;
  if (messageQueue.length === 0) return;

  isProcessingQueue = true;

  const msg = messageQueue[0];

  try {

    await client.sendMessage(msg.chatId, msg.content, msg.options);
    console.log("✅ Sent to", msg.chatId);
    messageQueue.shift();
    saveQueue();

    sendFailCount = 0;

    /* 60-80 messages per minute */
    const delay = 800 + Math.random() * 200;
    await new Promise(r => setTimeout(r, delay));

  } catch (error) {

    console.log("❌ Send failed:", error.message);

    sendFailCount++;

    if (sendFailCount >= MAX_FAILS) {

      console.log("🚨 Restarting bot (safe send loop)");

      saveQueue();

      try { await client.destroy(); } catch {}

      process.exit(1);
    }

    await new Promise(r => setTimeout(r, 5000));
  }

  isProcessingQueue = false;

  processQueue();
}

/* =========================
   EVENTS
========================= */

client.on("qr", qr => {
  console.log("📱 Scan QR");
  qrcode.generate(qr, { small: true });
});

client.on("ready", () => {
  console.log("✅ Bot ready");
  isClientReady = true;
  processQueue();
});

client.on("disconnected", async reason => {
  console.log("❌ Disconnected:", reason);
  saveQueue();
  try { await client.destroy(); } catch {}
  process.exit(1);
});

client.on("auth_failure", msg => {
  console.log("❌ Auth failure:", msg);
  process.exit(1);
});

/* =========================
   INCOMING MESSAGE
========================= */

client.on("message", async msg => {

  try {

    const payload = {
      number: msg.from,
      message: msg.body,
      replied_message: null
    };

    if (msg.hasQuotedMsg) {
      try {
        const quoted = await msg.getQuotedMessage();
        payload.replied_message = quoted?.body || null;
      } catch {}
    }

    const response = await axios.post(
      "http://localhost:5000/process",
      payload,
      { timeout: 30000 }
    );

    const reply = response.data.reply;

    if (reply && reply.trim()) {
      enqueueMessage(msg.from, reply);
    }

  } catch (e) {
    console.log("❌ Incoming error:", e.message);
  }

});

/* =========================
   API SEND MESSAGE
========================= */

app.post("/send-message", (req, res) => {

  const { number, message } = req.body;

  if (!isClientReady)
    return res.status(503).json({ success: false });

  if (!number || !message)
    return res.status(400).json({ success: false });

  let chatId = number;

  if (!number.includes("@")) {
    chatId =
      number.startsWith("91") && number.length === 12
        ? `${number}@c.us`
        : `${number}@lid`;
  }

  enqueueMessage(chatId, message);

  res.json({ success: true });

});

/* =========================
   START
========================= */

client.initialize();

app.listen(3001, () => {
  console.log("🚀 Server running on port 3001");
});

/* =========================
   CLEAN EXIT
========================= */

process.on("SIGINT", async () => {

  console.log("🛑 Shutdown");

  saveQueue();

  try { await client.destroy(); } catch {}

  process.exit(0);
});