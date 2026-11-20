document.querySelectorAll("[data-search-url]").forEach(input => {
    const form = input.form;
    const results = form.querySelector(".search-results");
    let timer;
    let request;

    function close() {
        clearTimeout(timer);
        request?.abort();
        results.replaceChildren();
        results.classList.remove("active", "show");
    }

    input.addEventListener("input", () => {
        close();
        const query = input.value.trim();
        if (query.length < 2) return;

        timer = setTimeout(async () => {
            request = new AbortController();
            const { signal } = request;
            try {
                const url = new URL(input.dataset.searchUrl, window.location.origin);
                url.searchParams.set("q", query);
                const response = await fetch(url, { signal });
                if (!response.ok) return;
                const data = await response.json();
                if (signal.aborted || !data.results.length) return;
                for (const product of data.results) {
                    const link = document.createElement("a");
                    link.className = "search-result-item";
                    link.href = product.url;
                    // Same square frame as the catalog: the photo is contained, never cropped.
                    const frame = document.createElement("span");
                    frame.className = "search-result-image";
                    if (product.image) {
                        const img = document.createElement("img");
                        img.src = product.image.src;
                        img.alt = "";
                        img.width = product.image.width;
                        img.height = product.image.height;
                        img.loading = "lazy";
                        img.decoding = "async";
                        frame.append(img);
                    }
                    const label = document.createElement("span");
                    label.className = "search-result-name";
                    label.textContent = product.brand
                        ? product.brand + " · " + product.name
                        : product.name;
                    link.append(frame, label);
                    results.append(link);
                }
                results.classList.add("active", "show");
            } catch (error) {
                if (!signal.aborted) close();
            }
        }, 250);
    });

    form.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            close();
            input.focus();
        }
        if (event.key === "ArrowDown" && event.target === input) {
            const firstResult = results.querySelector("a");
            if (firstResult) {
                event.preventDefault();
                firstResult.focus();
            }
        }
    });

    document.addEventListener("click", event => {
        if (!form.contains(event.target)) close();
    });
});
