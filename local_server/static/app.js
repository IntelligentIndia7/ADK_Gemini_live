const WS_PATH = `/ws/${crypto.randomUUID()}/${crypto.randomUUID()}`;
const INPUT_RATE = 16000;
const OUTPUT_RATE = 24000;

const logEl = document.getElementById("log");
const connectBtn = document.getElementById("connectBtn");
const micBtn = document.getElementById("micBtn");
const stopMicBtn = document.getElementById("stopMicBtn");
const sendBtn = document.getElementById("sendBtn");
const textInput = document.getElementById("textInput");

let ws = null;
let audioContext = null;
let playerNode = null;
let recorderNode = null;
let micStream = null;

function log(line) {
  logEl.textContent += line + "\n";
  logEl.scrollTop = logEl.scrollHeight;
}

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}${WS_PATH}`;
}

function floatTo16BitPCM(float32) {
  const out = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return new Uint8Array(out.buffer);
}

async function ensurePlayer() {
  if (playerNode) return;
  audioContext = new AudioContext({ sampleRate: OUTPUT_RATE });
  await audioContext.audioWorklet.addModule("/static/pcm-player-processor.js");
  playerNode = new AudioWorkletNode(audioContext, "pcm-player-processor");
  playerNode.connect(audioContext.destination);
}

async function startMic() {
  await ensurePlayer();
  const recCtx = new AudioContext({ sampleRate: INPUT_RATE });
  await recCtx.audioWorklet.addModule("/static/pcm-recorder-processor.js");
  micStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } });
  const source = recCtx.createMediaStreamSource(micStream);
  recorderNode = new AudioWorkletNode(recCtx, "pcm-recorder-processor");
  source.connect(recorderNode);
  recorderNode.port.onmessage = (e) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(floatTo16BitPCM(e.data));
    }
  };
  log("Mic started (16kHz PCM)");
}

function stopMic() {
  micStream?.getTracks().forEach((t) => t.stop());
  micStream = null;
  recorderNode = null;
  log("Mic stopped");
}

function handleEvent(raw) {
  let event;
  try { event = JSON.parse(raw); } catch { return; }

  const sc = event.serverContent || event.server_content;
  if (sc?.inputTranscription?.text || sc?.input_transcription?.text) {
    log("You: " + (sc.inputTranscription?.text || sc.input_transcription?.text));
  }
  if (sc?.outputTranscription?.text || sc?.output_transcription?.text) {
    log("Agent: " + (sc.outputTranscription?.text || sc.output_transcription?.text));
  }

  const parts = event.content?.parts || [];
  for (const part of parts) {
    if (part.text) log("Agent: " + part.text);
    const inline = part.inlineData || part.inline_data;
    if (inline?.data && playerNode) {
      const binary = atob(inline.data);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      playerNode.port.postMessage(bytes);
    }
  }
}

connectBtn.onclick = async () => {
  if (ws) { ws.close(); ws = null; }
  ws = new WebSocket(wsUrl());
  ws.binaryType = "arraybuffer";
  ws.onopen = () => {
    log("Connected to local server");
    micBtn.disabled = false;
    sendBtn.disabled = false;
    connectBtn.textContent = "Reconnect";
  };
  ws.onmessage = (m) => {
    if (typeof m.data === "string") handleEvent(m.data);
  };
  ws.onclose = () => log("Disconnected");
  ws.onerror = () => log("WebSocket error");
};

micBtn.onclick = async () => {
  await startMic();
  micBtn.disabled = true;
  stopMicBtn.disabled = false;
};

stopMicBtn.onclick = () => {
  stopMic();
  micBtn.disabled = false;
  stopMicBtn.disabled = true;
};

sendBtn.onclick = () => {
  const text = textInput.value.trim();
  if (!text || ws?.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "text", text }));
  log("You (text): " + text);
  textInput.value = "";
};
