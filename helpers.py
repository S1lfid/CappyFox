# helpers.py
import tkinter as tk
from PIL import Image, ImageTk
import os

# --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ---
# Создаем абсолютный путь к папке, где лежит этот скрипт (helpers.py)
# Это гарантирует, что папка icons будет найдена, откуда бы мы ни запускали main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_icon(icon_name, theme_name, size=(24, 24)):
    """
    Загружает иконку из папки, соответствующей теме, и изменяет её размер.
    Использует абсолютный путь для надежности.
    """
    # Теперь мы строим путь от абсолютного пути к скрипту
    icon_path = os.path.join(BASE_DIR, "icons", theme_name.lower(), f"{icon_name}.png")

    if not os.path.exists(icon_path):
        print(f"Иконка не найдена: {icon_path}")
        # Возвращаем полностью прозрачную заглушку, чтобы не было ошибок
        return ImageTk.PhotoImage(Image.new('RGBA', size, (0, 0, 0, 0)))

    try:
        img = Image.open(icon_path).convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Не удалось загрузить иконку {icon_name}: {e}")
        return ImageTk.PhotoImage(Image.new('RGBA', size, (0, 0, 0, 0)))

class Tooltip:
    """
    Создает всплывающую подсказку для виджета. (без изменений)
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify='left',
                      background="#333333", foreground="white", relief='solid', borderwidth=1,
                      font=("Arial", "9", "normal"), padx=8, pady=4)
        label.pack(ipadx=1)

    def leave(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None