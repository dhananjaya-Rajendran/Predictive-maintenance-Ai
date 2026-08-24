/**
 * AI Maintenance Copilot Chat Interface
 */
class AgentChat {
  constructor() {
    this.messagesContainer = document.getElementById('chatMessages');
    this.inputField = document.getElementById('chatInput');
    this.drawer = document.getElementById('copilotDrawer');
    this.currentMachineId = null;
    this.isOpen = false;
  }

  toggle() {
    this.isOpen = !this.isOpen;
    if (this.isOpen) {
      this.drawer.classList.add('open');
      this.inputField.focus();
    } else {
      this.drawer.classList.remove('open');
    }
  }

  setContext(machineId) {
    this.currentMachineId = machineId;
    if (!this.isOpen) {
      this.toggle();
    }
    this.appendMessage('user', `Analyze machine ${machineId}`);
    this.sendQuery(`Perform deep root-cause diagnosis on machine ${machineId}`);
  }

  appendMessage(sender, text) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender}`;

    // Simple markdown-to-html formatter for bold and lists
    let formatted = text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/### (.*?)\n/g, '<h4 style="margin:6px 0; color:#38bdf8;">$1</h4>')
      .replace(/- (.*?)\n/g, '<li>$1</li>')
      .replace(/`([^`]+)`/g, '<code style="background:#0f172a; padding:2px 4px; border-radius:3px; font-family:monospace; color:#38bdf8;">$1</code>');

    bubble.innerHTML = formatted;
    this.messagesContainer.appendChild(bubble);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }

  async sendQuery(queryText) {
    const text = queryText || this.inputField.value.trim();
    if (!text) return;

    if (!queryText) {
      this.appendMessage('user', text);
      this.inputField.value = '';
    }

    // Typing indicator
    const typingId = 'typing-' + Date.now();
    const typingBubble = document.createElement('div');
    typingBubble.id = typingId;
    typingBubble.className = 'chat-bubble agent';
    typingBubble.innerHTML = '<span style="color:#94a3b8; font-style:italic;">Agent analyzing telemetry & executing physical diagnostic tools...</span>';
    this.messagesContainer.appendChild(typingBubble);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;

    try {
      const response = await fetch('/api/v1/agent/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_message: text,
          machine_id: this.currentMachineId
        })
      });

      const data = await response.json();
      const typingEl = document.getElementById(typingId);
      if (typingEl) typingEl.remove();

      this.appendMessage('agent', data.message);

      if (data.diagnostic_card) {
        this.renderDiagnosticCard(data.diagnostic_card);
      }
    } catch (err) {
      const typingEl = document.getElementById(typingId);
      if (typingEl) typingEl.remove();
      this.appendMessage('agent', 'Error connecting to AutoPredict AI Agent core service.');
    }
  }

  renderDiagnosticCard(diag) {
    const card = document.createElement('div');
    card.style.cssText = "background:#0f172a; border:1px solid #334155; border-radius:8px; padding:12px; margin-top:8px; font-size:12px;";
    card.innerHTML = `
      <div style="font-weight:700; color:#38bdf8; margin-bottom:6px;">Autonomous Action Plan Generated</div>
      <div><strong>Target Window:</strong> ${diag.recommended_maintenance_window.window_type}</div>
      <div><strong>Work Order Draft:</strong> <code>${diag.sap_work_order_draft.work_order_id}</code></div>
      <div><strong>Potential ROI Savings:</strong> <span style="color:#10b981; font-weight:700;">$${diag.financial_impact.net_roi_savings_usd.toLocaleString()}</span></div>
    `;
    this.messagesContainer.appendChild(card);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }
}

const AGENT_CHAT = new AgentChat();
