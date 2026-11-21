"""Mobile performance with the installed Edge via the DevTools protocol (no packages installed).
Mobile viewport 390x844 @3x, CPU 4x slower, network ~slow 4G (150 ms RTT, 1.6 Mbps down).
Usage (Git Bash): MSYS_NO_PATHCONV=1 python deploy/checks/mobile_perf.py / /products/ ..."""
import json
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

EDGE = r"D:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "https://perfumeriaelbuenolor.es"
PAGES = sys.argv[1:] or ["/", "/products/", "/products/carolina-herrera-good-girl-eau-de-parfum/",
                         "/products/marca/versace/", "/products/genero/mujer/"]
OBSERVER = """
  window.__eo = {lcp: 0, cls: 0};
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__eo.lcp = e.startTime; })
    .observe({type: 'largest-contentful-paint', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__eo.cls += e.value; })
    .observe({type: 'layout-shift', buffered: true});
"""
METRICS = """(() => {
  if (!window.__eo || document.readyState !== 'complete') return null;
  const fcp = performance.getEntriesByName('first-contentful-paint')[0];
  const res = performance.getEntriesByType('resource');
  const nav = performance.getEntriesByType('navigation')[0];
  const bytes = res.reduce((a, r) => a + (r.transferSize || 0), 0) + (nav ? nav.transferSize : 0);
  return {fcp: fcp ? fcp.startTime : 0, lcp: window.__eo.lcp, cls: window.__eo.cls, kb: bytes / 1024,
          requests: res.length + 1, overflow: document.documentElement.scrollWidth > innerWidth};
})()"""

profile = tempfile.mkdtemp(prefix="eo-edge-")
proc = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=9333", f"--user-data-dir={profile}",
                         "--no-first-run", "--disable-extensions", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            targets = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
            page = next(t for t in targets if t["type"] == "page")
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60)
    counter = [0]

    def send(method, **params):
        counter[0] += 1
        ws.send(json.dumps({"id": counter[0], "method": method, "params": params}))
        while True:
            message = json.loads(ws.recv())
            if message.get("id") == counter[0]:
                return message.get("result", {})

    send("Page.enable"); send("Network.enable"); send("Runtime.enable")
    send("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=3, mobile=True)
    send("Emulation.setUserAgentOverride", userAgent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36 eo-perf-check")
    send("Emulation.setCPUThrottlingRate", rate=4)
    send("Network.emulateNetworkConditions", offline=False, latency=150,
         downloadThroughput=1.6 * 1024 * 1024 / 8, uploadThroughput=750 * 1024 / 8)
    send("Network.setCacheDisabled", cacheDisabled=True)
    send("Page.addScriptToEvaluateOnNewDocument", source=OBSERVER)
    print(f"{'página':<52} {'FCP':>6} {'LCP':>6} {'CLS':>6} {'KB':>6} {'peticiones':>10} {'scroll-x':>8}")
    for path in PAGES:
        send("Page.navigate", url=BASE + path)
        time.sleep(6)   # load under throttling
        result = None
        for _ in range(10):   # wait until the document is complete and the observers exist
            value = send("Runtime.evaluate", returnByValue=True, expression=METRICS).get("result", {}).get("value")
            if isinstance(value, dict):
                time.sleep(1)  # let late layout shifts be recorded
                result = send("Runtime.evaluate", returnByValue=True, expression=METRICS)["result"]["value"]
                break
            time.sleep(1)
        if result is None:
            print(f"{path:<52} sin datos (la página no terminó de cargar)")
            continue
        print(f"{path:<52} {result['fcp']/1000:>5.1f}s {result['lcp']/1000:>5.1f}s {result['cls']:>6.3f} "
              f"{result['kb']:>6.0f} {result['requests']:>10} {'sí' if result['overflow'] else 'no':>8}")
    ws.close()
finally:
    proc.terminate()
