import customtkinter as ctk
import threading
from tkinterdnd2 import TkinterDnD, DND_FILES

class InputWindow:
    def __init__(self, submit_callback, upload_callback=None):
        self.submit_callback = submit_callback
        self.upload_callback = upload_callback
        
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        # Drag & Drop を有効にするため TkinterDnD の root を使う
        # 透明化のキー色（Windowsの transparentcolor 用）
        self._transparent_key = '#000001'
        self.root = TkinterDnD.Tk()
        self.root.configure(bg=self._transparent_key)
        self.root.title("Supanikki")
        
        # Remove title bar for a cleaner look
        self.root.overrideredirect(True)

        # Make window data slightly transparent
        self.root.attributes("-alpha", 0.9)
        # Make the background color fully transparent (for rounded corners)
        self.root.attributes("-transparentcolor", self._transparent_key)
        
        # Dimensions
        self.width = 700
        self.height = 80
        
        # Center the window
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (self.width // 2)
        y = (screen_height // 3)  # Position at top 1/3
        
        self.root.geometry(f"{self.width}x{self.height}+{int(x)}+{int(y)}")
        
        # Layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Frame to add a border/background effect
        self.frame = ctk.CTkFrame(self.root, corner_radius=20)
        self.frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=1)

        self.entry = ctk.CTkTextbox(
            self.frame, 
            font=("Segoe UI", 18),
            height=60,
            border_width=0,
            fg_color="transparent",
            wrap="word"
        )
        self.entry.grid(row=0, column=0, padx=20, pady=10, sticky="ew")

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
        
        # Keep window on top
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.root.withdraw() # Hide initially
        
        self.is_visible = False

    def on_enter(self, event):
        # Check if Shift is pressed (state & 0x1 or similar depending on OS, but simpler to check keysym if bound generally?)
        # For Tkinter events, event.state & 0x1 is usually Shift.
        # But 'Shift-Return' binding is better if we want to be explicit, but Return binds both.
        
        if event.state & 0x0001: # Shift key is held
            return # Allow default newline behavior
        
        text = self.entry.get("0.0", "end")
        stripped_text = text.strip()
        if stripped_text:
            # Run submission in a separate thread to avoid blocking the UI
            threading.Thread(target=self.submit_callback, args=(stripped_text,), daemon=True).start()
            self.entry.delete("0.0", "end")
        self.hide()
        return "break" # Prevent default newline for plain Enter

    def on_escape(self, event):
        self.entry.delete("0.0", "end")
        self.hide()

    def on_drop_files(self, event):
        # upload_callback が無ければ何もしない
        if not self.upload_callback:
            return "break"

        # event.data は複数パスが来ることがある（スペースを含む場合は{}で囲われる）
        paths = self.root.tk.splitlist(event.data)

        def worker():
            urls = []
            for path in paths:
                try:
                    url = self.upload_callback(path)
                    urls.append(url)
                except Exception as e:
                    urls.append(f"[upload failed] {path} ({e})")

            def insert_urls():
                # 複数ファイルは改行で追記
                block = "\n".join(urls) + "\n"
                self.entry.insert("end", block)
                self.entry.see("end")

            self.root.after(0, insert_urls)

        threading.Thread(target=worker, daemon=True).start()
        return "break"

    def show(self):
        if not self.is_visible:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.lift() # Ensure it's on top
            self.root.focus_force()
            self.entry.focus_force()
            # Aggressively ensure focus happens after window is mapped
            self.root.after(50, lambda: self.entry.focus_force())
            self.is_visible = True

    def hide(self):
        if self.is_visible:
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
