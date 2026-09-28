/* voice.js - microphone, speech recognition, language switching and sending commands. */
const Voice = {
  recognition: null,
  listening: false,
  gotResult: false,
  lang: localStorage.getItem("voiceLang") || "en-IN",

  EXAMPLES: {
    "en-IN": ["Add milk", "I need apples", "Buy 2 bottles of water", "Change milk quantity to 3",
              "Remove milk", "Find toothpaste under 100", "Find Amul milk"],
    "hi-IN": ["दूध जोड़ो", "मुझे सेब चाहिए", "2 बोतल पानी जोड़ो", "दूध हटाओ",
              "दूध खोजो", "टूथपेस्ट 100 रुपये से कम खोजो"],
  },

  init() {
    this.els = {
      mic: document.getElementById("micButton"),
      label: document.querySelector("#micButton .mic-label"),
      status: document.getElementById("voiceStatus"),
      transcript: document.getElementById("transcript"),
      result: document.getElementById("commandResult"),
      hint: document.getElementById("commandHint"),
      lang: document.getElementById("languageSelect"),
      examples: document.getElementById("examples"),
      typedForm: document.getElementById("typedCommandForm"),
      typed: document.getElementById("typedCommand"),
    };

    this.els.lang.value = this.lang;
    this.els.lang.addEventListener("change", () => this.setLanguage(this.els.lang.value));
    this.els.mic.addEventListener("click", () => this.toggle());
    this.els.examples.addEventListener("click", (event) => {
      const chip = event.target.closest("button[data-text]");
      if (chip) this.handleText(chip.dataset.text);
    });
    this.els.typedForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const text = this.els.typed.value.trim();
      if (text) { this.els.typed.value = ""; this.handleText(text); }
    });

    this.renderExamples();
    this.setupRecognition();
    this.setState("ready");
  },

  // ---------------------------------------------------------- set-up
  setupRecognition() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      this.els.mic.disabled = true;
      this.els.label.textContent = "Voice not supported";
      this.setState("error", "Voice input isn't supported in this browser. Use Chrome or Edge, or type a command below.");
      return;
    }
    const recognition = new Recognition();
    recognition.lang = this.lang;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      this.listening = true;
      this.gotResult = false;
      this.showTranscript("");
      this.setState("listening");
    };

    recognition.onresult = (event) => {
      let text = "";
      let isFinal = false;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        text += event.results[i][0].transcript;
        if (event.results[i].isFinal) isFinal = true;
      }
      this.showTranscript(text);
      if (isFinal) {
        this.gotResult = true;
        this.handleText(text.trim());
      }
    };

    recognition.onerror = (event) => {
      this.listening = false;
      const messages = {
        "not-allowed": "Microphone permission is required for voice commands.",
        "service-not-allowed": "Microphone permission is required for voice commands.",
        "no-speech": "I didn't hear anything. Tap the mic and try again.",
        "audio-capture": "No microphone was found. Check that one is connected.",
        "network": "Speech recognition needs an internet connection in this browser.",
        "language-not-supported": "This browser can't recognise the selected language.",
      };
      if (event.error === "aborted") return;
      const message = messages[event.error] || `Speech recognition failed (${event.error}).`;
      this.setState("error", message);
      App.toast(message, "error");
    };

    recognition.onend = () => {
      this.listening = false;
      this.els.mic.setAttribute("aria-pressed", "false");
      this.els.label.textContent = "Tap to speak";
      this.els.mic.classList.remove("is-listening");
      if (this.els.status.dataset.state === "listening") this.setState("ready");
    };

    this.recognition = recognition;
  },

  setLanguage(lang) {
    this.lang = lang;
    localStorage.setItem("voiceLang", lang);
    if (this.recognition) {
      if (this.listening) this.recognition.abort();
      this.recognition.lang = lang;
    }
    this.renderExamples();
  },

  renderExamples() {
    const list = this.EXAMPLES[this.lang] || this.EXAMPLES["en-IN"];
    this.els.examples.innerHTML = list.map((text) =>
      `<button type="button" class="chip chip-action" data-text="${App.escapeHtml(text)}">${App.escapeHtml(text)}</button>`
    ).join("");
  },

  // ------------------------------------------------------ microphone
  toggle() {
    if (!this.recognition) return;
    if (this.listening) { this.recognition.stop(); return; }
    this.clearMessages();
    try {
      this.recognition.lang = this.lang;
      this.recognition.start();
      this.els.mic.setAttribute("aria-pressed", "true");
      this.els.mic.classList.add("is-listening");
      this.els.label.textContent = "Tap to stop";
    } catch (error) {
      this.setState("error", "The microphone is busy. Try again in a moment.");
    }
  },

  // -------------------------------------------------------- status UI
  setState(state, detail) {
    const labels = {
      ready: "Ready",
      listening: "🎙️ Listening...",
      processing: "⏳ Processing...",
      recognized: "Command recognized",
      success: "✓ Success",
      error: "Error",
    };
    this.els.status.dataset.state = state;
    this.els.status.textContent = labels[state] + (state === "error" && detail ? `: ${detail}` : "");
  },

  showTranscript(text) {
    this.els.transcript.hidden = !text;
    this.els.transcript.textContent = text ? `"${text}"` : "";
  },

  showResult(text, ok) {
    this.els.result.hidden = false;
    this.els.result.dataset.ok = ok ? "true" : "false";
    this.els.result.textContent = (ok ? "✓ " : "✕ ") + text;
  },

  clearMessages() {
    this.els.result.hidden = true;
    this.els.hint.hidden = true;
  },

  // ------------------------------------------------ send to backend
  async handleText(text) {
    this.showTranscript(text);
    this.clearMessages();
    this.setState("processing");
    try {
      const response = await App.api("/command", { method: "POST", body: { text } });
      await this.applyResponse(response);
    } catch (error) {
      this.setState("error");
      this.showResult(error.message, false);
      App.toast(error.message, "error");
    }
  },

  async applyResponse(response) {
    if (!response.understood) {
      this.setState("error");
      this.showResult("I didn't understand that command.", false);
      this.els.hint.hidden = false;
      this.els.hint.textContent = `Try: "${this.EXAMPLES[this.lang][0]}"`;
      App.toast("I didn't understand that command.", "error");
      return;
    }

    this.setState("recognized");
    await App.sleep(350);

    if (!response.success) {
      this.setState("error");
      this.showResult(response.message, false);
      if (response.hint) {
        this.els.hint.hidden = false;
        this.els.hint.textContent = response.hint.replace("Add milk", this.EXAMPLES[this.lang][0]);
      }
      if (response.substitutes) Substitutes.show(response);
      App.toast(response.message, "error");
      return;
    }

    this.setState("success");
    this.showResult(response.message, true);
    App.toast(response.message, "success");
    if (response.intent === "SEARCH") Search.showVoiceResults(response);
    else await App.refreshAfterListChange();
    await App.sleep(2500);
    if (this.els.status.dataset.state === "success") this.setState("ready");
  },
};
