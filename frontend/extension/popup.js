document.getElementById("btnPlay").addEventListener("click", () => {
    const status = document.getElementById("status");
    status.textContent = "Thinking...";

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        chrome.tabs.sendMessage(tabs[0].id, { action: "PLAY_MOVE" }, (response) => {
            status.textContent = "Done.";
        });
    });
});
