import json
import math
import os
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://getcomics.org"
SEARCH_URL = BASE_URL + "/?s={query}"
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
SITE_IMAGE_URL = "https://i0.wp.com/getcomics.org/share/uploads/2015/01/GetComics.INFO_.png?fit=2160%2C1080&ssl=1"
SITE_IMAGE_FILE = os.path.join(os.path.dirname(__file__), "getcomics_header.png")


@dataclass
class ComicItem:
    title: str
    url: str


@dataclass
class MirrorItem:
    name: str
    url: str


class SettingsStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self.data = {"download_folder": os.path.join(os.path.expanduser("~"), "Downloads")}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except Exception:
            pass

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    @property
    def download_folder(self) -> str:
        return self.data.get("download_folder", "")

    @download_folder.setter
    def download_folder(self, value: str) -> None:
        self.data["download_folder"] = value
        self.save()


class ComicsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("GetComics Downloader")
        self.root.geometry("1100x700")
        self._apply_dracula_theme()

        self.settings = SettingsStore(SETTINGS_FILE)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
            }
        )

        self.current_query = ""
        self.current_page = 1
        self.total_pages = 1
        self.current_results: list[ComicItem] = []
        self.current_mirrors: list[MirrorItem] = []
        self.logo_image: tk.PhotoImage | None = None

        self._build_ui()
        self._load_site_logo()
        self._set_status("Ready")
        self.search()

    def _build_ui(self) -> None:
        logo_bar = ttk.Frame(self.root, padding=(10, 10, 10, 0))
        logo_bar.pack(fill=tk.X)
        self.logo_label = ttk.Label(logo_bar, text="GetComics")
        self.logo_label.pack(side=tk.LEFT)

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top, textvariable=self.search_var, width=42)
        self.search_entry.pack(side=tk.LEFT, padx=(6, 8))
        self.search_entry.bind("<Return>", lambda _e: self.search(page=1))

        ttk.Button(top, text="Search", command=lambda: self.search(page=1)).pack(side=tk.LEFT)
        self.prev_button = ttk.Button(top, text="Prev", command=self.prev_page)
        self.prev_button.pack(side=tk.LEFT, padx=(12, 4))
        self.next_button = ttk.Button(top, text="Next", command=self.next_page)
        self.next_button.pack(side=tk.LEFT)

        self.page_label = ttk.Label(top, text="Page 1 out of 1")
        self.page_label.pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(top, text="Go to page:").pack(side=tk.LEFT, padx=(12, 4))
        self.goto_page_var = tk.StringVar()
        self.goto_page_entry = ttk.Entry(top, textvariable=self.goto_page_var, width=6)
        self.goto_page_entry.pack(side=tk.LEFT, padx=(0, 4))
        self.goto_page_entry.bind("<Return>", lambda _e: self.go_to_page())
        ttk.Button(top, text="Go", command=self.go_to_page).pack(side=tk.LEFT)

        folder_bar = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        folder_bar.pack(fill=tk.X)
        ttk.Label(folder_bar, text="Download folder:").pack(side=tk.LEFT)
        self.folder_var = tk.StringVar(value=self.settings.download_folder)
        self.folder_label = ttk.Label(folder_bar, textvariable=self.folder_var)
        self.folder_label.pack(side=tk.LEFT, padx=(8, 8))
        ttk.Button(folder_bar, text="Choose...", command=self.choose_folder).pack(side=tk.LEFT)

        splitter = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        splitter.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(splitter)
        right = ttk.Frame(splitter)
        splitter.add(left, weight=1)
        splitter.add(right, weight=1)

        ttk.Label(left, text="Comics").pack(anchor=tk.W, pady=(0, 6))
        self.comics_tree = ttk.Treeview(left, columns=("title",), show="headings", selectmode="browse")
        self.comics_tree.heading("title", text="Title")
        self.comics_tree.column("title", width=760, anchor=tk.W)
        self.comics_tree.pack(fill=tk.BOTH, expand=True)
        self.comics_tree.bind("<<TreeviewSelect>>", self.on_comic_selected)
        self.comics_tree.bind("<Double-1>", lambda _e: self.open_selected_comic())
        self.comics_tree.bind("<Button-3>", self.on_comic_right_click)

        ttk.Label(right, text="Mirrors / Download Options").pack(anchor=tk.W, pady=(0, 6))
        self.mirror_tree = ttk.Treeview(right, columns=("name", "url"), show="headings", selectmode="browse")
        self.mirror_tree.heading("name", text="Host")
        self.mirror_tree.heading("url", text="URL")
        self.mirror_tree.column("name", width=150, anchor=tk.W)
        self.mirror_tree.column("url", width=600, anchor=tk.W)
        self.mirror_tree.pack(fill=tk.BOTH, expand=True)
        self.mirror_tree.bind("<Double-1>", lambda _e: self.open_selected_mirror())
        self.mirror_tree.bind("<Button-3>", self.on_mirror_right_click)

        btns = ttk.Frame(right)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Open Comic Page", command=self.open_selected_comic).pack(side=tk.LEFT)
        ttk.Button(btns, text="Open Mirror in Browser", command=self.open_selected_mirror).pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar()
        status = ttk.Label(self.root, textvariable=self.status_var, anchor=tk.W, padding=10)
        status.pack(fill=tk.X)

        self.comic_menu = tk.Menu(self.root, tearoff=0)
        self.comic_menu.add_command(label="Copy comic URL", command=self.copy_selected_comic_url)
        self.comic_menu.add_command(label="Copy title", command=self.copy_selected_comic_title)

        self.mirror_menu = tk.Menu(self.root, tearoff=0)
        self.mirror_menu.add_command(label="Copy link address (JDownloader)", command=self.copy_selected_mirror_url)
        self.mirror_menu.add_command(label="Copy host name", command=self.copy_selected_mirror_name)
        self._update_pagination_buttons()

    def _apply_dracula_theme(self) -> None:
        # Dracula palette
        bg = "#282A36"
        surface = "#44475A"
        fg = "#F8F8F2"
        accent = "#BD93F9"
        muted = "#6272A4"
        select_bg = "#6272A4"
        select_fg = "#F8F8F2"

        self.root.configure(bg=bg)

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TPanedwindow", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=surface, foreground=fg, borderwidth=1)
        style.map(
            "TButton",
            background=[("active", accent), ("disabled", muted)],
            foreground=[("disabled", "#D0D0D0")],
        )
        style.configure(
            "TEntry",
            fieldbackground=surface,
            foreground=fg,
            insertcolor=fg,
            bordercolor=muted,
        )
        style.configure(
            "Treeview",
            background=surface,
            fieldbackground=surface,
            foreground=fg,
            bordercolor=muted,
            rowheight=24,
        )
        style.configure(
            "Treeview.Heading",
            background=bg,
            foreground=accent,
            bordercolor=muted,
        )
        style.map(
            "Treeview",
            background=[("selected", select_bg)],
            foreground=[("selected", select_fg)],
        )

        # Menu widgets are classic Tk widgets, set colors directly.
        menu_style = {
            "bg": surface,
            "fg": fg,
            "activebackground": accent,
            "activeforeground": "#282A36",
            "relief": "flat",
            "borderwidth": 0,
            "tearoff": 0,
        }
        self.root.option_add("*Menu.background", menu_style["bg"])
        self.root.option_add("*Menu.foreground", menu_style["fg"])
        self.root.option_add("*Menu.activeBackground", menu_style["activebackground"])
        self.root.option_add("*Menu.activeForeground", menu_style["activeforeground"])

    def _set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    def _load_site_logo(self) -> None:
        threading.Thread(target=self._load_site_logo_worker, daemon=True).start()

    def _load_site_logo_worker(self) -> None:
        try:
            if not os.path.exists(SITE_IMAGE_FILE):
                resp = self.session.get(SITE_IMAGE_URL, timeout=20)
                resp.raise_for_status()
                with open(SITE_IMAGE_FILE, "wb") as f:
                    f.write(resp.content)
            self.root.after(0, self._apply_site_logo)
        except Exception:
            # Keep text-only fallback if image download/load fails.
            pass

    def _apply_site_logo(self) -> None:
        try:
            raw = tk.PhotoImage(file=SITE_IMAGE_FILE)
            max_w = 420
            max_h = 90
            factor_w = math.ceil(raw.width() / max_w) if raw.width() > max_w else 1
            factor_h = math.ceil(raw.height() / max_h) if raw.height() > max_h else 1
            factor = max(1, factor_w, factor_h)
            self.logo_image = raw.subsample(factor, factor)
            self.logo_label.configure(image=self.logo_image, text="")
        except Exception:
            pass

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.settings.download_folder or os.path.expanduser("~"))
        if selected:
            self.settings.download_folder = selected
            self.folder_var.set(selected)
            self._set_status(f"Saved download folder: {selected}")

    def search(self, page: int | None = None) -> None:
        query = self.search_var.get().strip()
        if page is None:
            page = self.current_page
        self.current_query = query
        self.current_page = max(1, page)
        self.page_label.config(text=f"Page {self.current_page} out of {self.total_pages}")
        self._set_status("Loading search results...")
        threading.Thread(target=self._search_worker, daemon=True).start()

    def _search_worker(self) -> None:
        try:
            if self.current_query:
                search_root = SEARCH_URL.format(query=quote_plus(self.current_query))
            else:
                search_root = BASE_URL

            if self.current_page > 1:
                url = f"{BASE_URL}/page/{self.current_page}/?s={quote_plus(self.current_query)}"
            else:
                url = search_root

            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = self._parse_search_results(soup)
            total_pages = self._parse_total_pages(soup)
            self.root.after(0, lambda: self._update_results(items, total_pages))
        except Exception as ex:
            self.root.after(0, lambda: self._set_status(f"Search failed: {ex}"))

    def _parse_search_results(self, soup: BeautifulSoup) -> list[ComicItem]:
        results: list[ComicItem] = []
        seen = set()
        for h1 in soup.select("h1.post-title a"):
            href = h1.get("href", "").strip()
            title = h1.get_text(strip=True)
            if not href or not title:
                continue
            href = urljoin(BASE_URL, href)
            if href in seen:
                continue
            seen.add(href)
            results.append(ComicItem(title=title, url=href))
        return results

    def _parse_total_pages(self, soup: BeautifulSoup) -> int:
        nums: list[int] = []
        for a in soup.select(".wp-pagenavi a, .wp-pagenavi span, .pagination a, .pagination span"):
            text = a.get_text(strip=True)
            if text.isdigit():
                nums.append(int(text))
        return max(nums) if nums else 1

    def _update_results(self, items: list[ComicItem], total_pages: int) -> None:
        self.total_pages = max(1, total_pages)
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        self.page_label.config(text=f"Page {self.current_page} out of {self.total_pages}")
        self._update_pagination_buttons()
        self.current_results = items
        self.current_mirrors = []
        for row in self.comics_tree.get_children():
            self.comics_tree.delete(row)
        for row in self.mirror_tree.get_children():
            self.mirror_tree.delete(row)

        for idx, item in enumerate(items):
            self.comics_tree.insert("", tk.END, iid=str(idx), values=(item.title,))

        self._set_status(f"Loaded {len(items)} comics")

    def prev_page(self) -> None:
        if self.current_page > 1:
            self.search(page=self.current_page - 1)

    def next_page(self) -> None:
        if self.current_page < self.total_pages:
            self.search(page=self.current_page + 1)

    def go_to_page(self) -> None:
        raw = self.goto_page_var.get().strip()
        if not raw:
            return
        try:
            page = int(raw)
        except ValueError:
            self._set_status("Enter a valid page number")
            return
        page = max(1, min(page, self.total_pages))
        self.goto_page_var.set(str(page))
        if page != self.current_page:
            self.search(page=page)

    def _update_pagination_buttons(self) -> None:
        self.prev_button.configure(state=tk.NORMAL if self.current_page > 1 else tk.DISABLED)
        self.next_button.configure(state=tk.NORMAL if self.current_page < self.total_pages else tk.DISABLED)

    def on_comic_selected(self, _event: object = None) -> None:
        selection = self.comics_tree.selection()
        if not selection:
            return
        idx = int(selection[0])
        if 0 <= idx < len(self.current_results):
            comic = self.current_results[idx]
            self._set_status(f"Loading mirrors for: {comic.title}")
            threading.Thread(target=self._load_mirrors_worker, args=(comic.url,), daemon=True).start()

    def _load_mirrors_worker(self, comic_url: str) -> None:
        try:
            resp = self.session.get(comic_url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            mirrors = self._parse_mirrors(soup)
            self.root.after(0, lambda: self._update_mirrors(mirrors))
        except Exception as ex:
            self.root.after(0, lambda: self._set_status(f"Failed to load mirrors: {ex}"))

    def _parse_mirrors(self, soup: BeautifulSoup) -> list[MirrorItem]:
        mirrors: list[MirrorItem] = []
        seen = set()

        # GetComics commonly wraps links in "aio-button-center" buttons on post pages.
        for a in soup.select(".aio-button-center a"):
            href = a.get("href", "").strip()
            name = a.get_text(" ", strip=True) or "Mirror"
            if not href:
                continue
            href = urljoin(BASE_URL, href)
            key = (name.lower(), href)
            if key in seen:
                continue
            seen.add(key)
            mirrors.append(MirrorItem(name=name, url=href))

        # Fallback selector if theme changes.
        if not mirrors:
            for a in soup.select("a"):
                href = a.get("href", "").strip()
                text = a.get_text(" ", strip=True).lower()
                if not href:
                    continue
                host_keywords = ("mega", "mediafire", "pixeldrain", "viking", "rootz", "download")
                if any(k in text for k in host_keywords):
                    href = urljoin(BASE_URL, href)
                    name = a.get_text(" ", strip=True) or "Mirror"
                    key = (name.lower(), href)
                    if key in seen:
                        continue
                    seen.add(key)
                    mirrors.append(MirrorItem(name=name, url=href))

        return mirrors

    def _update_mirrors(self, mirrors: list[MirrorItem]) -> None:
        self.current_mirrors = mirrors
        for row in self.mirror_tree.get_children():
            self.mirror_tree.delete(row)
        for idx, mirror in enumerate(mirrors):
            self.mirror_tree.insert("", tk.END, iid=str(idx), values=(mirror.name, mirror.url))
        self._set_status(f"Found {len(mirrors)} mirror options")

    def open_selected_comic(self) -> None:
        item = self._get_selected_comic()
        if not item:
            return
        webbrowser.open(item.url)

    def open_selected_mirror(self) -> None:
        item = self._get_selected_mirror()
        if not item:
            return
        # Browser-first behavior: hosts often require legal wait/captcha steps.
        webbrowser.open(item.url)
        self._set_status("Opened mirror in browser")

    def _get_selected_comic(self) -> ComicItem | None:
        selection = self.comics_tree.selection()
        if not selection:
            return None
        idx = int(selection[0])
        if 0 <= idx < len(self.current_results):
            return self.current_results[idx]
        return None

    def _get_selected_mirror(self) -> MirrorItem | None:
        selection = self.mirror_tree.selection()
        if not selection:
            return None
        idx = int(selection[0])
        if 0 <= idx < len(self.current_mirrors):
            return self.current_mirrors[idx]
        return None

    def _copy_to_clipboard(self, text: str, status: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self._set_status(status)

    def copy_selected_comic_url(self) -> None:
        item = self._get_selected_comic()
        if item:
            self._copy_to_clipboard(item.url, "Comic URL copied")

    def copy_selected_comic_title(self) -> None:
        item = self._get_selected_comic()
        if item:
            self._copy_to_clipboard(item.title, "Comic title copied")

    def copy_selected_mirror_url(self) -> None:
        item = self._get_selected_mirror()
        if item:
            self._copy_to_clipboard(item.url, "Mirror URL copied for JDownloader")

    def copy_selected_mirror_name(self) -> None:
        item = self._get_selected_mirror()
        if item:
            self._copy_to_clipboard(item.name, "Mirror host name copied")

    def on_comic_right_click(self, event: tk.Event) -> None:
        row = self.comics_tree.identify_row(event.y)
        if row:
            self.comics_tree.selection_set(row)
            self.comic_menu.tk_popup(event.x_root, event.y_root)

    def on_mirror_right_click(self, event: tk.Event) -> None:
        row = self.mirror_tree.identify_row(event.y)
        if row:
            self.mirror_tree.selection_set(row)
            self.mirror_menu.tk_popup(event.x_root, event.y_root)


def check_dependencies() -> bool:
    missing = []
    try:
        import bs4  # noqa: F401
    except Exception:
        missing.append("beautifulsoup4")
    try:
        import requests  # noqa: F401
    except Exception:
        missing.append("requests")

    if missing:
        messagebox.showerror(
            "Missing packages",
            "Install required packages first:\n\npip install " + " ".join(missing),
        )
        return False
    return True


def main() -> None:
    root = tk.Tk()
    if not check_dependencies():
        root.destroy()
        return
    ComicsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
