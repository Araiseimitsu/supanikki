import os
import threading

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD


class InputWindow:
    def __init__(self, submit_callback, upload_callback=None):
        self.submit_callback = submit_callback
        self.upload_callback = upload_callback

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # Drag & Drop を有効にするため TkinterDnD の root を使う
        # 透明化のキー色（Windowsの transparentcolor 用）
        self._transparent_key = "#000001"
        self.root = TkinterDnD.Tk()
        self.root.configure(bg=self._transparent_key)
        self.root.title("Supanikki")

        # Remove title bar for a cleaner look
        self.root.overrideredirect(True)

        # Make window data slightly transparent
        self._alpha_visible = 0.9
        self.root.attributes("-alpha", self._alpha_visible)
        # Make the background color fully transparent (for rounded corners)
        self.root.attributes("-transparentcolor", self._transparent_key)

        # Dimensions
        self.width = 680
        self.height = 70  # Initial height

        # Center the window
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (self.width // 2)
        y = screen_height // 3

        self.root.geometry(f"{self.width}x{self.height}+{int(x)}+{int(y)}")

        # Layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # "Capsule" Container
        # Blue outline as requested
        self.container = ctk.CTkFrame(
            self.root,
            corner_radius=32,
            fg_color=("white", "#2B2B2B"),
            border_width=2,
            border_color=("#3B8ED0", "#1F6AA5"),  # Blue theme
        )
        self.container.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_columnconfigure(1, weight=0)
        self.container.grid_rowconfigure(0, weight=1)

        # Input Field
        self.entry = ctk.CTkTextbox(
            self.container,
            font=("Segoe UI", 18),
            height=40,
            border_width=0,
            fg_color="transparent",
            wrap="word",
            # Remove internal padding/highlight to make it clean
            activate_scrollbars=False
        )
        self.entry.grid(row=0, column=0, padx=(20, 10), pady=(15, 15), sticky="nsew")

        # Send Button (Round Icon)
        self.send_button = ctk.CTkButton(
            self.container,
            text="↑",  # Minimalist arrow
            font=("Arial", 20, "bold"),
            width=40,
            height=40,
            corner_radius=20,
            fg_color=("#007AFF", "#0A84FF"),  # System Blue-ish
            hover_color=("#0051A8", "#0058A8"),
            command=self.on_send_click,
        )
        # Position at bottom-right of the capsule, or centered vertically depends on preference.
        # sticky="s" aligns it to bottom if multiline, but usually we want it bottom-aligned for chat style.
        self.send_button.grid(row=0, column=1, padx=(0, 12), pady=(0, 12), sticky="s")

        # Drag & Drop（ファイル）
        # CTkTextbox は内部に tk.Text を持つので、そちらにDnDを登録する
        drop_target = getattr(self.entry, "_textbox", self.entry)
        try:
            drop_target.drop_target_register(DND_FILES)
            drop_target.dnd_bind("<<Drop>>", self.on_drop_files)
        except Exception:
            # DnD初期化に失敗しても入力自体は使えるようにする
            pass

        self.entry.bind("<Return>", self.on_enter)
        self.entry.bind("<Escape>", self.on_escape)

        # Dynamic resize settings
        self._min_height = 40
        self._max_height = 260
        self._line_height_px = 24
        self._resize_after_id = None
        try:
            drop_target.bind("<<Modified>>", self.on_text_modified)
        except Exception:
            drop_target.bind("<KeyRelease>", self.on_text_modified)

        # Keep window on top
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.root.withdraw()  # Hide initially

        self.is_visible = False

    def on_enter(self, event):
        # Check if Shift is pressed (state & 0x1 or similar depending on OS, but simpler to check keysym if bound generally?)
        # For Tkinter events, event.state & 0x1 is usually Shift.
        # But 'Shift-Return' binding is better if we want to be explicit, but Return binds both.

        if event.state & 0x0001:  # Shift key is held
            return  # Allow default newline behavior

        self._submit_and_close()
        return "break"  # Prevent default newline for plain Enter

    def on_escape(self, event):
        self.entry.delete("0.0", "end")
        self.hide()

    def on_send_click(self):
        self._submit_and_close()

    def _submit_and_close(self):
        text = self.entry.get("0.0", "end")
        stripped_text = text.strip()
        if stripped_text:
            threading.Thread(
                target=self.submit_callback, args=(stripped_text,), daemon=True
            ).start()
            self.entry.delete("0.0", "end")
        self.hide()

    def on_text_modified(self, event=None):
        if self._resize_after_id:
            try:
                self.root.after_cancel(self._resize_after_id)
            except Exception:
                pass
        self._resize_after_id = self.root.after(80, self._adjust_height)

        drop_target = getattr(self.entry, "_textbox", self.entry)
        try:
            drop_target.edit_modified(False)
        except Exception:
            pass

    def _adjust_height(self):
        try:
            content = self.entry.get("0.0", "end-1c")
        except Exception:
            return

        line_count = max(1, content.count("\n") + 1)
        target_height = self._min_height + (line_count - 1) * self._line_height_px
        target_height = max(self._min_height, min(self._max_height, target_height))

        if int(self.entry.cget("height")) != int(target_height):
            self.entry.configure(height=target_height)
            # Add padding (15 top + 15 bottom = 30) for window height
            new_window_height = int(target_height) + 30
            new_window_height = max(self.height, min(320, new_window_height))
            self.root.geometry(
                f"{self.width}x{new_window_height}+{self.root.winfo_x()}+{self.root.winfo_y()}"
            )

    def on_drop_files(self, event):
        # upload_callback が無ければ何もしない
        if not self.upload_callback:
            return "break"

        # event.data は複数パスが来ることがある（スペースを含む場合は{}で囲われる）
        paths = self.root.tk.splitlist(event.data)

        # すぐに「アップロード中」表示を入れてユーザーに進行を見せる
        placeholder_start = self.entry.index("end-1c")
        display_names = [os.path.basename(p) for p in paths]
        placeholder_text = "アップロード中: " + ", ".join(display_names) + "\n"
        self.entry.insert("end", placeholder_text)
        self.entry.see("end")
        self._adjust_height()
        placeholder_end = self.entry.index("end-1c")

        # アップロード中は送信を誤って押せないように一時無効化
        try:
            self.send_button.configure(state="disabled")
        except Exception:
            pass

        def worker():
            urls = []
            for path in paths:
                try:
                    url = self.upload_callback(path)
                    urls.append(url)
                except Exception as e:
                    urls.append(f"[upload failed] {path} ({e})")

            def insert_urls():
                # プレースホルダを削除して結果に置き換え
                try:
                    self.entry.delete(placeholder_start, placeholder_end)
                except Exception:
                    # 失敗しても末尾に追記する
                    pass
                # 複数ファイルは改行で追記
                block = "\n".join(urls) + "\n"
                self.entry.insert("end", block)
                self.entry.see("end")
                self._adjust_height()
                try:
                    self.send_button.configure(state="normal")
                except Exception:
                    pass

            self.root.after(0, insert_urls)

        threading.Thread(target=worker, daemon=True).start()
        return "break"

    def show(self):
        if not self.is_visible:
            # 表示前に必ず内容をクリアして、前回のメッセージが一瞬見えるのを防ぐ
            try:
                self.entry.delete("0.0", "end")
                self.entry.configure(height=self._min_height)
                if self._resize_after_id:
                    self.root.after_cancel(self._resize_after_id)
                    self._resize_after_id = None
            except Exception:
                pass

            # OSの描画キャッシュで前回内容がフラッシュするのを避けるため、一旦透明で表示
            try:
                self.root.attributes("-alpha", 0.0)
            except Exception:
                pass
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.lift()  # Ensure it's on top

            # 軽量化: update_idletasksは最小限に
            try:
                self.root.update_idletasks()
                self.root.attributes("-alpha", self._alpha_visible)
            except Exception:
                pass

            # フォーカス処理を最適化
            try:
                self.root.focus_force()
                self.entry.focus_force()
            except Exception:
                pass

            # 遅延フォーカスは50msに短縮
            self.root.after(50, self._delayed_focus)
            self.is_visible = True

    def _delayed_focus(self):
        """遅延フォーカス処理（軽量化）"""
        try:
            self.entry.focus_force()
        except Exception:
            pass

    def hide(self):
        if self.is_visible:
            # 次回表示時のフラッシュ防止のため、隠す前に内容と高さをリセット
            try:
                self.entry.delete("0.0", "end")
                self.entry.configure(height=self._min_height)
                if self._resize_after_id:
                    self.root.after_cancel(self._resize_after_id)
                    self._resize_after_id = None
                # ウィンドウ高さも元に戻す
                self.root.geometry(
                    f"{self.width}x{self.height}+{self.root.winfo_x()}+{self.root.winfo_y()}"
                )
            except Exception:
                pass
            self.root.withdraw()
            self.is_visible = False

    def toggle(self):
        if self.is_visible:
            self.hide()
        else:
            self.show()

    def thread_safe_toggle(self):
        self.root.after(0, self.toggle)

    def quit(self):
        self.root.quit()

    def start_mainloop(self):
        self.root.mainloop()
