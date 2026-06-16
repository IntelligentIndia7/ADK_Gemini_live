class PcmPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.port.onmessage = (e) => this.queue.push(e.data);
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    if (!out) return true;

    let offset = 0;
    while (offset < out.length) {
      if (!this.queue.length) {
        out.fill(0, offset);
        break;
      }
      const chunk = this.queue[0];
      const view = new Int16Array(chunk.buffer, chunk.byteOffset, chunk.byteLength / 2);
      const needed = out.length - offset;
      const take = Math.min(needed, view.length);
      for (let i = 0; i < take; i++) {
        out[offset + i] = view[i] / 32768;
      }
      offset += take;
      if (take === view.length) {
        this.queue.shift();
      } else {
        const remain = new Uint8Array(chunk.buffer, chunk.byteOffset + take * 2);
        this.queue[0] = remain;
      }
    }
    return true;
  }
}
registerProcessor("pcm-player-processor", PcmPlayerProcessor);
