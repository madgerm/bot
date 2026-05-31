(function () {
  function scrollThreadToBottom() {
    var thread = document.getElementById("chat-feed");
    if (!thread) return;
    thread.scrollTop = thread.scrollHeight;
  }

  scrollThreadToBottom();

  document.body.addEventListener("htmx:afterSwap", function (ev) {
    if (ev.detail && ev.detail.target && ev.detail.target.id === "chat-feed") {
      scrollThreadToBottom();
    }
  });
})();
