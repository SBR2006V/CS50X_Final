// Smart Routine Generator - Client-side scripts
console.log("Smart Routine Generator loaded.");

// Synchronize setup tab navigation with URL parameter
document.addEventListener("DOMContentLoaded", () => {
    const setupTabs = document.querySelectorAll('#setupTabs button[data-bs-toggle="pill"]');
    if (!setupTabs.length) {
        return;
    }

    // Helper to activate a tab by its parameter name ('subjects', 'teachers', 'sections')
    const activateTabByName = (tabName) => {
        const targetBtn = document.querySelector(`#${tabName}-tab`);
        if (targetBtn && window.bootstrap && !targetBtn.classList.contains("active")) {
            const tabInstance = bootstrap.Tab.getOrCreateInstance(targetBtn);
            tabInstance.show();
        }
    };

    // Update query parameter when tab changes via user interaction
    setupTabs.forEach(tabButton => {
        tabButton.addEventListener("shown.bs.tab", event => {
            const targetId = event.target.getAttribute("data-bs-target");
            let tabParam = "subjects";
            if (targetId === "#teachers-pane") {
                tabParam = "teachers";
            } else if (targetId === "#sections-pane") {
                tabParam = "sections";
            }
            const url = new URL(window.location.href);
            url.searchParams.set("tab", tabParam);
            window.history.replaceState({}, "", url.toString());
        });
    });

    // Ensure tab matching query parameter is active on initial load / refresh
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get("tab");
    if (tabParam && ["subjects", "teachers", "sections"].includes(tabParam.toLowerCase())) {
        activateTabByName(tabParam.toLowerCase());
    }

    // Keep tabs in sync with browser back / forward navigation
    window.addEventListener("popstate", () => {
        const params = new URLSearchParams(window.location.search);
        const currentTab = params.get("tab") || "subjects";
        activateTabByName(currentTab.toLowerCase());
    });
});
