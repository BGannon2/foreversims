// Contribute + Discord links, injected next to the Feedback button on every page.
(function () {
  function build() {
    let tabs = document.getElementById("bottomTabs");
    if (!tabs) { tabs = document.createElement("div"); tabs.id = "bottomTabs"; tabs.className = "bottom-tabs"; document.body.append(tabs); }
    const contribute = document.createElement("a");
    contribute.href = "https://github.com/BGannon2/foreversims"; contribute.target = "_blank"; contribute.rel = "noopener";
    contribute.className = "feedback-button community-link"; contribute.textContent = "Contribute";
    const discord = document.createElement("a");
    discord.href = "https://discord.gg/Ncgu5GfC6n"; discord.target = "_blank"; discord.rel = "noopener";
    discord.className = "feedback-button community-link"; discord.textContent = "Discord";
    tabs.append(contribute, discord);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
})();
