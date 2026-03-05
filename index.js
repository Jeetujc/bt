const { Client, LocalAuth } = require("whatsapp-web.js");
const axios = require("axios");
const qrcode = require("qrcode-terminal");
const express = require("express");

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

const messageQueue = [];
let isProcessingQueue = false;

function enqueueMessage(chatId, content, options = {}) {
  messageQueue.push({ chatId, content, options });
  processQueue();
}

async function processQueue() {
  if (isProcessingQueue) return;
  if (messageQueue.length === 0) return;
  if (!isClientReady) return;

  isProcessingQueue = true;

  const { chatId, content, options } = messageQueue.shift();

  try {
    const chat = await client.getChatById(chatId);
    await chat.sendMessage(content, options);

    sendFailCount = 0;

    // Throttle (important)
    await new Promise(r => setTimeout(r, 500));

  } catch (error) {
    console.error("❌ Queue send failed:", error.message);

    sendFailCount++;

    if (sendFailCount >= MAX_FAILS) {
      console.error("🚨 Too many failures. Restarting app...");
      try { await client.destroy(); } catch {}
      process.exit(1); // Let PM2 restart
    }
  }

  isProcessingQueue = false;
  processQueue();
}

/* =========================
   EVENTS
========================= */

client.on("qr", (qr) => {
  console.log("📱 Scan this QR code:");
  qrcode.generate(qr, { small: true });
});

client.on("ready", async () => {
  console.log("✅ WhatsApp bot is ready!");
  isClientReady = true;

  try {
    await client.pupPage.evaluate(() => {
      if (window.WWebJS && window.WWebJS.sendSeen) {
        window.WWebJS.sendSeen = async () => true;
      }
    });
    console.log("✅ SendSeen function patched successfully");
  } catch (err) {
    console.log("⚠️ Could not patch sendSeen:", err.message);
  }
});

client.on("disconnected", async (reason) => {
  console.log("❌ Disconnected:", reason);
  try { await client.destroy(); } catch {}
  process.exit(1);
});

client.on("auth_failure", (msg) => {
  console.error("❌ Auth failure:", msg);
  process.exit(1);
});

/* =========================
   INCOMING MESSAGE
========================= */

client.on("message", async (msg) => {
  try {
    const payload = {
      number: msg.from,
      message: msg.body,
      replied_message: null,
    };

    if (msg.hasQuotedMsg) {
      try {
        const quotedMsg = await msg.getQuotedMessage();
        payload.replied_message = quotedMsg?.body || null;
      } catch {}
    }

    const response = await axios.post(
      "http://localhost:5000/process",
      payload,
      { timeout: 30000 }
    );

    const reply = response.data.reply;

    if (reply && reply.trim() !== "") {
      console.log("📨 Queueing reply...");
      enqueueMessage(msg.from, reply);
    }

  } catch (error) {
    console.error("❌ Error:", error.message);
  }
});

/* =========================
   API SEND MESSAGE
========================= */

app.post("/send-message", async (req, res) => {
  try {
    const { number, message } = req.body;

    if (!isClientReady) {
      return res.status(503).json({ success: false });
    }

    if (!number || !message) {
      return res.status(400).json({ success: false });
    }

    let chatId = number;
    if (!number.includes("@")) {
      chatId =
        number.startsWith("91") && number.length === 12
          ? `${number}@c.us`
          : `${number}@lid`;
    }

    enqueueMessage(chatId, message);

    res.json({ success: true });

  } catch (error) {
    console.error("❌ API Error:", error.message);
    res.status(500).json({ success: false });
  }
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
  console.log("🛑 Shutting down...");
  try { await client.destroy(); } catch {}
  process.exit(0);
});

