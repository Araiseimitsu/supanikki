import os
import threading

import tempfile
from PIL import ImageGrab
import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD


class InputWindow:
    def __init__(self, submit_callback, upload_callback=None, history_manager=None, sheet_name_provider=None):
        self.submit_callback = submit_callback
        self.upload_callback = upload_callback
        self.history_manager = history_manager
        self.sheet_name_provider = sheet_name_provider

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
        self.height = 90  # Increased height to prevent clipping

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
        # More premium look: Pure white (or very light gray) for light mode, Dark gray for dark mode.
        # High corner radius for pill shape.
        self.container = ctk.CTkFrame(
            self.root,
            corner_radius=40,  # Slightly more rounded for larger height
            fg_color=("white", "#1c1c1e"),  # Apple-like dark mode gray
            border_width=2,
            border_color="#d3d3d3",
        )
        self.container.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_columnconfigure(1, weight=0)
        self.container.grid_rowconfigure(0, weight=0) # Input row
        self.container.grid_rowconfigure(1, weight=1) # History row

        # History Frame (Initially hidden)
        self.history_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.history_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=(0, 20))
        self.history_frame.grid_remove() # Hide initially

        self.history_label = ctk.CTkLabel(
            self.history_frame, 
            text="", 
            font=("Yu Gothic UI", 12), 
            text_color="gray", 
            justify="left",
            anchor="w"
        )
        self.history_label.pack(fill="x", expand=True)

        # Input Field
        # Premium font: Yu Gothic UI Semibold for better visibility + Meiryo UI fallback
        self.entry = ctk.CTkTextbox(
            self.container,
            font=("Yu Gothic UI Semibold", 20),
            height=50,  # Increased min height
            border_width=0,
            fg_color="transparent",
            text_color=("black", "white"),
            wrap="word",
            activate_scrollbars=False,
        )
        self.entry.grid(row=0, column=0, padx=(25, 10), pady=(20, 20), sticky="nsew")

        # Right Side (Sheet label + Send Button)
        self.right_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=(10, 20))
        self.right_frame.grid_rowconfigure(0, weight=0)
        self.right_frame.grid_rowconfigure(1, weight=0)

        # Current sheet label (small)
        self.sheet_label = ctk.CTkLabel(
            self.right_frame,
            text="",
            font=("Yu Gothic UI", 10),
            text_color=("gray40", "gray60"),
            anchor="e",
        )
        self.sheet_label.grid(row=0, column=0, sticky="e", pady=(0, 6))

        # Send Button (Round Icon)
        self.send_button = ctk.CTkButton(
            self.right_frame,
            text="→",
            font=("Yu Gothic UI Semibold", 20),
            width=50,
            height=50,
            corner_radius=25,
            fg_color=("#F2F2F2", "#2B2B2B"),
            hover_color=("#E8E8E8", "#3A3A3A"),
            border_width=1,
            border_color=("#D3D3D3", "#444444"),
            text_color=("gray20", "gray85"),
            command=self.on_send_click,
        )
        self.send_button.grid(row=1, column=0, sticky="e")

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
        # Bind paste to handle images
        self.entry.bind("<Control-v>", self.on_paste)

        # Dynamic resize settings
        self._min_height = 50  # Match new widget height
        self._max_height = 280
        self._line_height_px = 30  # Adjusted for larger font
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
        # Check if Shift is pressed
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
        
        # Calculate total window height including history
        history_height = 0
        # Use grid_info to check if it's managed, as ismapped is unreliable during rapid updates
        if self.history_frame.grid_info():
            # Estimate history height (label height + padding)
            lines = 0
            if self.history_label.cget("text"):
                 lines = self.history_label.cget("text").count("\n") + 1
            if lines > 0:
                history_height = lines * 30 + 20 # Increased line height estimate
        
        # Add padding for window height (20 + 20 = 40) + history
        new_window_height = int(target_height) + 40 + history_height
        new_window_height = max(self.height, min(600, new_window_height)) # increased max height
        
        print(f"DEBUG: target_entry_height={target_height}, history_height={history_height}, total={new_window_height}")

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

    def update_sheet_name(self, name: str):
        if not hasattr(self, "sheet_label"):
            return
        label = f"シート: {name}" if name else ""
        try:
            self.sheet_label.configure(text=label)
        except Exception:
            pass

    def show(self):
        if not self.is_visible:
            # Clear previous content to prevent flash
            try:
                self.entry.delete("0.0", "end")
                self.entry.configure(height=self._min_height)
                if self._resize_after_id:
                    self.root.after_cancel(self._resize_after_id)
                    self._resize_after_id = None
            except Exception:
                pass

            # Make transparent for initial render to avoid flash
            try:
                self.root.attributes("-alpha", 0.0)
            except Exception:
                pass
            
            self.root.deiconify()
            
            # Update sheet label
            if self.sheet_name_provider:
                try:
                    self.update_sheet_name(self.sheet_name_provider() or "")
                except Exception:
                    pass

            # Update history
            self.update_history_display()
            
            # AGGRESSIVE FOCUS LOGIC
            self.root.attributes("-topmost", True)
            self.root.lift()
            
            try:
                # Force focus to the main window first
                self.root.focus_force()
                # Then to the entry
                self.entry.focus_force()
            except Exception:
                pass

            # Lightweight update
            try:
                self.root.update_idletasks()
                self.root.attributes("-alpha", self._alpha_visible)
            except Exception:
                pass

            # Multiple attempts to steal focus (robustness)
            self.root.after(50, self._delayed_focus)
            self.root.after(150, self._delayed_focus)
            
            self.is_visible = True

    def _delayed_focus(self):
        """Force focus again slightly later to override other apps."""
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
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

    def on_paste(self, event):
        try:
            # Check for image in clipboard
            img = ImageGrab.grabclipboard()
            if img:
                # It's an image! Save to temp file and upload
                # Create a temp file
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    img.save(tmp.name, "PNG")
                    tmp_path = tmp.name
                
                # Mock a drop event-like behavior
                # Using the existing file upload logic
                # We can reuse the logic from on_drop_files if we refactor it, 
                # or just call the worker directly. 
                # Let's repurpose the logic by calling a helper
                self._handle_file_upload([tmp_path])
                return "break" # Prevent default paste
        except Exception as e:
            print(f"Paste error: {e}")
            pass
        return None # Allow default paste for text

    def _handle_file_upload(self, paths):
        if not self.upload_callback:
            return

        # Insert placeholder
        placeholder_start = self.entry.index("end-1c")
        display_names = [os.path.basename(p) for p in paths]
        placeholder_text = "画像アップロード中... " + "\n"
        self.entry.insert("end", placeholder_text)
        self.entry.see("end")
        self._adjust_height()
        placeholder_end = self.entry.index("end-1c")

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
                    # Cleanup temp file if it was generated by us (rudimentary check: starts with temp)
                    if path.startswith(tempfile.gettempdir()):
                         try:
                             os.remove(path)
                         except:
                             pass
                except Exception as e:
                    urls.append(f"[upload failed] {path} ({e})")

            def insert_urls():
                try:
                    self.entry.delete(placeholder_start, placeholder_end)
                except Exception:
                    pass
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

    def update_history_display(self):
        if not self.history_manager:
            return

        latest = self.history_manager.get_latest(3)
        if not latest:
            self.history_frame.grid_remove()
            return

        # Simple text representation for now
        history_text = "\n".join([f"• {item}" for item in latest])
        self.history_label.configure(text=history_text, text_color=("gray60", "gray70"))
        
        # Show the frame
        self.history_frame.grid()
        self.history_frame.configure(border_width=0)
        
        self._adjust_height()
