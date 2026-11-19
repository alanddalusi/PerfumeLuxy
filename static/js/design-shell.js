const shellDisclosures = document.querySelectorAll("[data-eo-disclosure]");

for (const disclosure of shellDisclosures) {
    disclosure.addEventListener("toggle", () => {
        if (!disclosure.open) return;
        for (const other of shellDisclosures) {
            if (other !== disclosure) other.open = false;
        }
    });
    disclosure.addEventListener("keydown", event => {
        if (event.key !== "Escape" || !disclosure.open) return;
        disclosure.open = false;
        disclosure.querySelector("summary").focus();
    });
}

document.addEventListener("click", event => {
    for (const disclosure of shellDisclosures) {
        if (!disclosure.contains(event.target)) disclosure.open = false;
    }
});
