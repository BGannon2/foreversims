// Feedback button + dialog, injected on every page.  Posts to /api/feedback (Cloudflare Worker;
// server.py provides a local stand-in).
(function () {
  const specFromPage = () => document.body.dataset.spec || new URLSearchParams(location.search).get("spec") || "";
  const versionLabel = () => { const v = window.FOREVER_SIMS_VERSION; return v ? `v${v.version} ${v.build}` : ""; };

  function build() {
    const button = document.createElement("button");
    button.type = "button"; button.className = "feedback-button"; button.textContent = "Feedback";
    button.setAttribute("aria-haspopup", "dialog");
    const dialog = document.createElement("dialog");
    dialog.className = "feedback-dialog";
    dialog.innerHTML = `
      <form method="dialog" class="feedback-form" novalidate>
        <header><h2>Send feedback</h2><button type="button" class="feedback-close" aria-label="Close">×</button></header>
        <p class="feedback-intro">Found a wrong number, a broken page, or have an idea? Tell us. The page, spec and build are attached automatically.</p>
        <label>Type
          <select name="category">
            <option value="bug">Bug or broken page</option>
            <option value="data">Wrong number, talent or item data</option>
            <option value="idea">Idea or request</option>
            <option value="other">Something else</option>
          </select>
        </label>
        <label>Feedback <textarea name="message" rows="6" maxlength="4000" required placeholder="What happened, what you expected, and the spec or item involved."></textarea></label>
        <p class="feedback-intro">Your feedback may be shared in public GitHub issues or our community Discord. Keep private information out of the message. Contact details below are stored privately for the maintainers and are not forwarded.</p>
        <label>How to reach you <small>(optional, private: Discord handle or email)</small><input name="contact" maxlength="200" autocomplete="off"></label>
        <input name="website" class="feedback-hp" tabindex="-1" autocomplete="off" aria-hidden="true">
        <p class="feedback-status" aria-live="polite"></p>
        <footer><button type="button" class="feedback-cancel">Cancel</button><button type="submit" class="feedback-submit sim-button">Send</button></footer>
      </form>`;
    let tabs = document.getElementById("bottomTabs");
    if (!tabs) { tabs = document.createElement("div"); tabs.id = "bottomTabs"; tabs.className = "bottom-tabs"; document.body.append(tabs); }
    tabs.append(button); document.body.append(dialog);
    const form = dialog.querySelector("form"), status = dialog.querySelector(".feedback-status"), submit = dialog.querySelector(".feedback-submit");
    const open = () => { status.textContent = ""; status.className = "feedback-status"; form.reset(); dialog.showModal(); dialog.querySelector("textarea").focus(); };
    const close = () => dialog.close();
    button.addEventListener("click", open);
    dialog.querySelector(".feedback-close").addEventListener("click", close);
    dialog.querySelector(".feedback-cancel").addEventListener("click", close);
    dialog.addEventListener("click", e => { if (e.target === dialog) close(); });
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      if ((data.message || "").trim().length < 5) { status.textContent = "Please write a few words first."; status.className = "feedback-status error"; return; }
      submit.disabled = true; status.textContent = "Sending…"; status.className = "feedback-status";
      try {
        const res = await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...data, page: location.href, spec: specFromPage(), version: versionLabel() }) });
        const out = await res.json().catch(() => ({}));
        if (!res.ok || out.error) throw new Error(out.error || `Could not send (${res.status}).`);
        status.textContent = "Thanks! Your feedback was sent."; status.className = "feedback-status ok";
        setTimeout(close, 1400);
      } catch (err) {
        status.textContent = err.message; status.className = "feedback-status error";
      } finally { submit.disabled = false; }
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
})();
