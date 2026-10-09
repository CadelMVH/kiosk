KIOSK APP v1 - setup (run these in a terminal inside this folder)

1. Make sure data\floorplans.json exists.
2. Download PDFs and photos:   docker compose run --rm kiosk python download_assets.py
   (Failures are listed in data\download_report.txt)
3. Start the kiosk server:     docker compose up -d --build
4. On the host open:           http://localhost:8080
   On the kiosk computer open: http://HOST-TAILSCALE-NAME:8080
5. Kiosk mode in Chrome:       chrome.exe --kiosk --kiosk-printing http://HOST-TAILSCALE-NAME:8080

Customer contact requests are saved to data\leads.jsonl.
After editing floorplans.json the app picks up changes on its own. Re-run step 2 if you added new homes.
To stop: docker compose down
