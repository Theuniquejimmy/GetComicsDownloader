# GetComics Downloader

A desktop GUI app for browsing `getcomics.org`, searching comics, paging through results, and quickly sending mirror links to JDownloader.

<img width="1377" height="915" alt="image" src="https://github.com/user-attachments/assets/ec9325d7-acf2-4231-9d64-094e3e8fe5d6" />


## Features

- Search comics by keyword
- Browse pages with `Prev`, `Next`, and `Go to page`
- Page indicator with total pages (`Page X out of Y`)
- Select a comic to load available mirrors/host links
- Right-click actions for fast copying:
  - Comic URL
  - Mirror URL (`Copy link address (JDownloader)`)
- Open comic pages or mirror links directly in your browser
- Save and remember your default download folder
- Dracula-themed UI

## How It Works

1. Enter a search term and click `Search`.
2. Pick a comic from the left panel.
3. Review mirrors in the right panel.
4. Right-click a mirror and copy the URL for JDownloader, or open it in browser.

## Install

```powershell
cd "C:\Users\theun\Desktop\comic_downloader_gui"
python -m pip install -r requirements.txt
or
just run GetComicsDownloader.exe
```

## Run

```powershell
python app.py
or
just run GetComicsDownloader.exe
```

## Notes on Hoster Pages

This app does **not** bypass host wait timers, captchas, login prompts, or anti-bot protections.

Some hosts use multi-step flows that change over time. This tool is designed to:

- extract and display mirror links reliably
- let you copy links for JDownloader
- open host pages in your browser for normal completion

## Local Config

- `settings.json` stores your saved download folder
- `getcomics_header.png` is a cached header image
- Both are excluded from git via `.gitignore`
