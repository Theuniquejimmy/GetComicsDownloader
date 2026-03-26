# Comics Browser (GUI)

This app lets you:

- Search GetComics by keyword
- Move between result pages (`Prev` / `Next`)
- Click a comic to load mirror options
- Right-click comic or mirror rows to copy URLs (useful for JDownloader)
- Save a default download folder (remembered in `settings.json`)

## Important behavior

This app does **not** bypass hoster waits, captchas, or anti-bot protections.
For host pages (Vikingfile, Mediafire, Mega, etc.), it opens the selected mirror in your browser so you can complete normal steps.

## Setup

```powershell
cd "C:\Users\theun\Desktop\comic_downloader_gui"
python -m pip install -r requirements.txt
python app.py
```

## Hoster notes (high level)

- **Mega**: typically opens a host page/app workflow.
- **Mediafire**: often a landing page with a download button.
- **Pixeldrain**: may provide direct file links on its page.
- **Vikingfile/Rootz**: often include wait timers and redirect steps.

Because these flows can change frequently, this tool focuses on extracting and copying links reliably, then letting browser/JDownloader handle host-specific processing.
