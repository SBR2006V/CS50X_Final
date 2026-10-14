// Smart Routine Generator - Client-side scripts
console.log("Smart Routine Generator loaded.");

// Synchronize setup tab navigation with URL parameter
document.addEventListener("DOMContentLoaded", () => {
    const setupTabs = document.querySelectorAll('#setupTabs button[data-bs-toggle="pill"]');
    setupTabs.forEach(tabButton => {
        tabButton.addEventListener("shown.bs.tab", event => {
            const targetId = event.target.getAttribute("data-bs-target");
            const tabParam = targetId === "#teachers-pane" ? "teachers" : "subjects";
            const url = new URL(window.location.href);
            url.searchParams.set("tab", tabParam);
            window.history.replaceState({}, "", url.toString());
        });
    });
});
