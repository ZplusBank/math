#!/usr/bin/env python3
"""
Exam Engine Editor - Multi-Section Version
Manages multiple subjects/sections with chapters.json structure
"""

import uuid
import tkinter as tk
from tkinter import messagebox, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import json
import os
from pathlib import Path
import re
import shutil
import zipfile
import tempfile
import urllib.parse
import urllib.request
import webbrowser
from difflib import SequenceMatcher
from diagram_support import validate_diagram_blocks

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

# -- Dark Theme Color Constants (matches web app CSS dark theme) --
COLORS = {
    "bg_body": "#0f172a",
    "bg_card": "#1e293b",
    "bg_input": "#0f172a",
    "bg_input_alt": "#1a2332",
    "text_main": "#f1f5f9",
    "text_muted": "#94a3b8",
    "text_secondary": "#cbd5e1",
    "border": "#334155",
    "primary": "#6366f1",
    "primary_light": "#818cf8",
    "secondary": "#8b5cf6",
    "accent": "#06b6d4",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "selection_bg": "#6366f1",
    "selection_fg": "#ffffff",
    "treeview_row_odd": "#1e293b",
    "treeview_row_even": "#172033",
}


def _configure_custom_styles(style):
    """Override ttkbootstrap darkly theme to match web app indigo/purple palette."""
    style.configure("Treeview",
                     background=COLORS["bg_card"],
                     foreground=COLORS["text_main"],
                     fieldbackground=COLORS["bg_card"],
                     rowheight=28,
                     borderwidth=0,
                     font=("Segoe UI", 10))
    style.configure("Treeview.Heading",
                     background=COLORS["bg_body"],
                     foreground=COLORS["text_muted"],
                     font=("Segoe UI", 10, "bold"),
                     borderwidth=0,
                     relief="flat")
    style.map("Treeview",
              background=[("selected", COLORS["primary"])],
              foreground=[("selected", COLORS["selection_fg"])])

    style.configure("TLabelframe",
                     background=COLORS["bg_card"],
                     foreground=COLORS["primary_light"],
                     bordercolor=COLORS["border"])
    style.configure("TLabelframe.Label",
                     background=COLORS["bg_card"],
                     foreground=COLORS["primary_light"],
                     font=("Segoe UI", 10, "bold"))

    style.configure("Header.TLabel",
                     font=("Segoe UI", 12, "bold"),
                     foreground=COLORS["text_main"])
    style.configure("SubHeader.TLabel",
                     font=("Segoe UI", 10, "bold"),
                     foreground=COLORS["text_secondary"])
    style.configure("Muted.TLabel",
                     foreground=COLORS["text_muted"])
    style.configure("Status.TLabel",
                     font=("Segoe UI", 9))

    style.configure("TPanedwindow",
                     background=COLORS["bg_body"],
                     sashthickness=6)


def _style_tk_text(widget, height=None):
    """Apply dark theme to a tk.Text widget."""
    widget.configure(
        bg=COLORS["bg_input"],
        fg=COLORS["text_main"],
        insertbackground=COLORS["text_main"],
        selectbackground=COLORS["selection_bg"],
        selectforeground=COLORS["selection_fg"],
        relief="flat",
        borderwidth=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["primary"],
        highlightthickness=1,
        font=("Segoe UI", 10),
        padx=8,
        pady=6,
    )
    if height is not None:
        widget.configure(height=height)


def _style_tk_listbox(widget):
    """Apply dark theme to a tk.Listbox widget."""
    widget.configure(
        bg=COLORS["bg_card"],
        fg=COLORS["text_main"],
        selectbackground=COLORS["primary"],
        selectforeground=COLORS["selection_fg"],
        relief="flat",
        borderwidth=0,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["primary"],
        highlightthickness=1,
        font=("Segoe UI", 10),
        activestyle="none",
    )


def _style_dialog(dialog, title, geometry):
    """Apply dark theme to a tk.Toplevel dialog."""
    dialog.title(title)
    dialog.geometry(geometry)
    dialog.configure(bg=COLORS["bg_body"])


def _replace_escaped_newlines(value):
    """Convert literal escaped newline sequences (\\n) to real newlines."""
    text = str(value or "")
    replacements = 0

    count = text.count("\\n")
    if count:
        text = text.replace("\\n", "\n")
        replacements += count

    return text, replacements


def _fix_escaped_newlines_in_question(question):
    """Fix escaped newline sequences in common question text fields."""
    if not isinstance(question, dict):
        return 0

    replacements = 0
    for field in ("text", "explanation"):
        fixed, count = _replace_escaped_newlines(question.get(field, ""))
        if count:
            question[field] = fixed
            replacements += count

    for choice in question.get("choices", []) or []:
        if not isinstance(choice, dict):
            continue
        fixed, count = _replace_escaped_newlines(choice.get("text", ""))
        if count:
            choice["text"] = fixed
            replacements += count

    return replacements


def _load_json_file(path):
    """Load JSON using UTF-8 BOM-safe decoding."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

class FormattedTextEditor(ttk.Frame):
    """Rich text editor with formatting toolbar, syntax highlighting, and live preview."""

    FORMATS = [
        # (label, prefix, suffix, bootstyle)
        ("B", "**", "**", "warning-outline"),
        ("I", "*", "*", "info-outline"),
        ("SEP", None, None, None),
        ("<>", "`", "`", "success-outline"),
        ("{..}", "```java\n", "\n```", "success-outline"),
        ("MM", "```mermaid\nflowchart LR\n  A[Start] --> B[End]\n```", "", "primary-outline"),
        ("UML", "```uml\n[User]-[Order]\n```", "", "primary-outline"),
        ("DOT", "```dot\ndigraph G {\n  A -> B;\n}\n```", "", "primary-outline"),
        ("SEP", None, None, None),
        ("f(x)", "\\(", "\\)", "primary-outline"),
        ("[=]", "\\[", "\\]", "primary-outline"),
        ("SEP", None, None, None),
        ("BR", "<br>", "", "danger-outline"),
        ("SP", "&nbsp;", "", "secondary-outline"),
    ]

    def __init__(self, parent, height=6, show_preview=True):
        super().__init__(parent)
        self.show_preview = show_preview
        self._highlight_job = None
        self._build_toolbar()
        self._build_text(height)
        if show_preview:
            self._build_preview()
        self._setup_tags()
        self._bind_events()

    def _build_toolbar(self):
        tb = ttk.Frame(self)
        tb.pack(fill=tk.X, pady=(0, 2))

        for label, prefix, suffix, bstyle in self.FORMATS:
            if label == "SEP":
                sep = ttk.Separator(tb, orient=tk.VERTICAL)
                sep.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
                continue
            btn = ttk.Button(
                tb, text=label, width=max(len(label) + 1, 4),
                bootstyle=bstyle, takefocus=0,
                command=lambda p=prefix, s=suffix: self._insert_format(p, s),
            )
            btn.pack(side=tk.LEFT, padx=1, pady=1)

        if self.show_preview:
            self._preview_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                tb, text="Preview", variable=self._preview_var,
                command=self._toggle_preview, bootstyle="info-round-toggle",
            ).pack(side=tk.RIGHT, padx=4)

    def _build_text(self, height):
        self.text = tk.Text(self, height=height, wrap=tk.WORD, undo=True,
                            exportselection=False)
        _style_tk_text(self.text, height=height)
        self.text.pack(fill=tk.BOTH, expand=True)

    def _build_preview(self):
        self._preview_frame = ttk.LabelFrame(self, text="Preview")
        self._preview_frame.pack(fill=tk.X, pady=(3, 0))
        self._preview_text = tk.Text(
            self._preview_frame, height=3, wrap=tk.WORD,
            state="disabled", cursor="arrow",
        )
        self._preview_text.configure(
            bg=COLORS["bg_input_alt"], fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"],
            selectbackground=COLORS["selection_bg"],
            selectforeground=COLORS["selection_fg"],
            relief="flat", borderwidth=0, highlightthickness=0,
            font=("Segoe UI", 10), padx=8, pady=4,
        )
        self._preview_text.pack(fill=tk.BOTH, expand=True)

        # Preview rendering tags
        self._preview_text.tag_configure("bold", font=("Segoe UI", 10, "bold"))
        self._preview_text.tag_configure("italic", font=("Segoe UI", 10, "italic"))
        self._preview_text.tag_configure("code", font=("Consolas", 10),
                                          foreground=COLORS["success"],
                                          background="#1a2332")
        self._preview_text.tag_configure("codeblock", font=("Consolas", 9),
                                          foreground=COLORS["success"],
                                          background="#1a2332")
        self._preview_text.tag_configure("math", foreground=COLORS["accent"],
                                          font=("Cambria Math", 10))

    def _toggle_preview(self):
        if self._preview_var.get():
            self._preview_frame.pack(fill=tk.X, pady=(3, 0))
            self._update_preview()
        else:
            self._preview_frame.pack_forget()

    def _setup_tags(self):
        """Configure syntax highlighting tags for the editor."""
        t = self.text
        t.tag_configure("fmt_bold_marker", foreground="#f59e0b")
        t.tag_configure("fmt_bold_text", font=("Segoe UI", 10, "bold"),
                         foreground="#fbbf24")
        t.tag_configure("fmt_italic_marker", foreground="#38bdf8")
        t.tag_configure("fmt_italic_text", font=("Segoe UI", 10, "italic"),
                         foreground="#7dd3fc")
        t.tag_configure("fmt_code_marker", foreground="#065f46")
        t.tag_configure("fmt_code", font=("Consolas", 10),
                         foreground=COLORS["success"])
        t.tag_configure("fmt_codeblock", font=("Consolas", 9),
                         foreground=COLORS["success"], background="#1a2332")
        t.tag_configure("fmt_math_marker", foreground="#0e7490")
        t.tag_configure("fmt_math", foreground=COLORS["accent"])
        t.tag_configure("fmt_html", foreground=COLORS["warning"])
        t.tag_configure("fmt_entity", foreground=COLORS["text_muted"],
                         background="#1c1c2e")
        t.tag_configure("fmt_diagram_marker", foreground="#a78bfa")
        t.tag_configure("fmt_diagram_lang", foreground="#c4b5fd", font=("Consolas", 9, "bold"))

    def _bind_events(self):
        self.text.bind("<KeyRelease>", self._schedule_highlight)

        # Keyboard shortcuts
        def make_handler(p, s):
            def handler(event):
                self._insert_format(p, s)
                return "break"
            return handler

        for key, p, s in [("b", "**", "**"), ("i", "*", "*"),
                           ("e", "`", "`"), ("m", "\\(", "\\)")]:
            self.text.bind(f"<Control-{key}>", make_handler(p, s))
            self.text.bind(f"<Control-{key.upper()}>", make_handler(p, s))

    def _schedule_highlight(self, event=None):
        if self._highlight_job:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(250, self._do_highlight)

    def _do_highlight(self):
        self._highlight_syntax()
        if (self.show_preview and hasattr(self, '_preview_var')
                and self._preview_var.get()):
            self._update_preview()

    def _char_to_index(self, content, pos):
        """Convert character offset to tkinter text index."""
        line = content[:pos].count('\n') + 1
        col = pos - content[:pos].rfind('\n') - 1
        return f"{line}.{col}"

    def _highlight_syntax(self):
        """Apply syntax highlighting to the editor text."""
        content = self.text.get("1.0", "end-1c")
        idx = lambda pos: self._char_to_index(content, pos)

        # Clear existing formatting tags
        for tag in list(self.text.tag_names()):
            if tag.startswith("fmt_"):
                self.text.tag_remove(tag, "1.0", tk.END)

        # Code blocks (highest priority)
        codeblock_ranges = []
        for m in re.finditer(r'```([\w\-]*)\n?([\s\S]*?)```', content):
            s, e = m.start(), m.end()
            codeblock_ranges.append((s, e))
            self.text.tag_add("fmt_codeblock", idx(s), idx(e))
            self.text.tag_add("fmt_diagram_marker", idx(s), idx(s + 3))
            lang = (m.group(1) or "")
            if lang:
                lang_start = s + 3
                self.text.tag_add("fmt_diagram_lang", idx(lang_start), idx(lang_start + len(lang)))
            self.text.tag_add("fmt_diagram_marker", idx(e - 3), idx(e))

        def in_codeblock(pos):
            return any(s <= pos < e for s, e in codeblock_ranges)

        # Bold **...**
        for m in re.finditer(r'\*\*(.+?)\*\*', content):
            if in_codeblock(m.start()):
                continue
            self.text.tag_add("fmt_bold_marker", idx(m.start()), idx(m.start() + 2))
            self.text.tag_add("fmt_bold_text", idx(m.start() + 2), idx(m.end() - 2))
            self.text.tag_add("fmt_bold_marker", idx(m.end() - 2), idx(m.end()))

        # Italic *...*
        for m in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', content):
            if in_codeblock(m.start()):
                continue
            self.text.tag_add("fmt_italic_marker", idx(m.start()), idx(m.start() + 1))
            self.text.tag_add("fmt_italic_text", idx(m.start() + 1), idx(m.end() - 1))
            self.text.tag_add("fmt_italic_marker", idx(m.end() - 1), idx(m.end()))

        # Inline code `...`
        for m in re.finditer(r'(?<!`)`(?!`)([^`]+?)(?<!`)`(?!`)', content):
            if in_codeblock(m.start()):
                continue
            self.text.tag_add("fmt_code_marker", idx(m.start()), idx(m.start() + 1))
            self.text.tag_add("fmt_code", idx(m.start() + 1), idx(m.end() - 1))
            self.text.tag_add("fmt_code_marker", idx(m.end() - 1), idx(m.end()))

        # Math inline \(...\)
        for m in re.finditer(r'\\\((.+?)\\\)', content, re.DOTALL):
            if in_codeblock(m.start()):
                continue
            self.text.tag_add("fmt_math_marker", idx(m.start()), idx(m.start() + 2))
            self.text.tag_add("fmt_math", idx(m.start() + 2), idx(m.end() - 2))
            self.text.tag_add("fmt_math_marker", idx(m.end() - 2), idx(m.end()))

        # Math display \[...\]
        for m in re.finditer(r'\\\[(.+?)\\\]', content, re.DOTALL):
            if in_codeblock(m.start()):
                continue
            self.text.tag_add("fmt_math_marker", idx(m.start()), idx(m.start() + 2))
            self.text.tag_add("fmt_math", idx(m.start() + 2), idx(m.end() - 2))
            self.text.tag_add("fmt_math_marker", idx(m.end() - 2), idx(m.end()))

        # HTML tags
        for m in re.finditer(r'<[^>]+>', content):
            if in_codeblock(m.start()):
                continue
            self.text.tag_add("fmt_html", idx(m.start()), idx(m.end()))

        # Entities &nbsp; etc
        for m in re.finditer(r'&\w+;', content):
            if in_codeblock(m.start()):
                continue
            self.text.tag_add("fmt_entity", idx(m.start()), idx(m.end()))

    def _update_preview(self):
        """Update the live preview panel."""
        content = self.text.get("1.0", "end-1c")
        self._preview_text.configure(state="normal")
        self._preview_text.delete("1.0", tk.END)
        self._render_preview(content)
        self._preview_text.configure(state="disabled")

    def _render_preview(self, content):
        """Render simplified formatted preview."""
        # Pre-process HTML line breaks and entities
        text = re.sub(r'<br\s*/?>', '\n', content)
        text = text.replace('&nbsp;', ' ')

        all_matches = []

        # Code blocks
        for m in re.finditer(r'```\w*\n?([\s\S]*?)```', text):
            all_matches.append((m.start(), m.end(), m.group(1).strip(), 'codeblock'))
        # Bold
        for m in re.finditer(r'\*\*(.+?)\*\*', text):
            all_matches.append((m.start(), m.end(), m.group(1), 'bold'))
        # Italic
        for m in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', text):
            all_matches.append((m.start(), m.end(), m.group(1), 'italic'))
        # Inline code
        for m in re.finditer(r'(?<!`)`(?!`)([^`]+?)(?<!`)`(?!`)', text):
            all_matches.append((m.start(), m.end(), m.group(1), 'code'))
        # Math inline
        for m in re.finditer(r'\\\((.+?)\\\)', text):
            all_matches.append((m.start(), m.end(), m.group(1), 'math'))
        # Math display
        for m in re.finditer(r'\\\[(.+?)\\\]', text):
            all_matches.append((m.start(), m.end(), m.group(1), 'math'))
        # Remaining HTML tags (remove from preview)
        for m in re.finditer(r'<[^>]+>', text):
            all_matches.append((m.start(), m.end(), '', '_skip'))
        # Remaining entities
        for m in re.finditer(r'&\w+;', text):
            all_matches.append((m.start(), m.end(), '', '_skip'))

        # Sort by position, longer matches first for same position
        all_matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))

        # Remove overlapping matches
        filtered = []
        last_end = 0
        for start, end, inner, tag in all_matches:
            if start >= last_end:
                filtered.append((start, end, inner, tag))
                last_end = end

        # Render segments into preview
        pw = self._preview_text
        pos = 0
        for start, end, inner, tag in filtered:
            if pos < start:
                pw.insert(tk.END, text[pos:start])
            if tag != '_skip':
                pw.insert(tk.END, inner, tag)
            pos = end
        if pos < len(text):
            pw.insert(tk.END, text[pos:])

    def _insert_format(self, prefix, suffix):
        """Insert formatting around selection or at cursor."""
        try:
            sel_start = self.text.index(tk.SEL_FIRST)
            sel_end = self.text.index(tk.SEL_LAST)
            selected = self.text.get(sel_start, sel_end)
            self.text.delete(sel_start, sel_end)
            self.text.insert(sel_start, f"{prefix}{selected}{suffix}")
        except tk.TclError:
            # No selection - insert at cursor
            pos = self.text.index(tk.INSERT)
            self.text.insert(pos, f"{prefix}{suffix}")
            if suffix:
                new_pos = f"{pos}+{len(prefix)}c"
                self.text.mark_set(tk.INSERT, new_pos)
        self.text.focus_set()
        self._schedule_highlight()

    def get_warnings(self, subject_id=""):
        """Return non-blocking content warnings for the current text body."""
        content = self.text.get("1.0", "end-1c")
        return validate_diagram_blocks(content, subject_id=subject_id)

    # -- Compatibility proxy methods (match tk.Text interface) --

    def get(self, *args, **kwargs):
        return self.text.get(*args, **kwargs)

    def insert(self, *args, **kwargs):
        result = self.text.insert(*args, **kwargs)
        self._schedule_highlight()
        return result

    def delete(self, *args, **kwargs):
        result = self.text.delete(*args, **kwargs)
        self._schedule_highlight()
        return result


class AdvancedChapterEditor:
    """Advanced editor for chapter questions, choices, and images"""
    def __init__(self, parent, chapter_file, section_path, base_path):
        self.parent = parent
        self.chapter_file = Path(chapter_file)
        self.section_path = Path(section_path)
        self.base_path = Path(base_path)
        # Create images folder with correct absolute path
        self.images_folder = self.base_path / self.section_path / "images"
        
        # Create images folder if it doesn't exist
        self.images_folder.mkdir(parents=True, exist_ok=True)
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"Advanced Chapter Editor - {self.chapter_file.stem}")
        self.window.geometry("1100x800")
        self.window.configure(bg=COLORS["bg_body"])
        self.window.transient(parent)
        
        self.chapter_data = None
        self.current_question_idx = None
        self.questions = []
        self.current_image_path = None
        self.question_search_var = tk.StringVar(value="")
        self.search_in_text_var = tk.BooleanVar(value=True)
        self.search_in_explanation_var = tk.BooleanVar(value=True)
        self.search_in_choices_var = tk.BooleanVar(value=True)
        self.search_in_meta_var = tk.BooleanVar(value=False)
        self.filtered_question_indices = []
        self.is_maximized = True
        self.question_search_var.trace_add("write", lambda *_: self.refresh_questions_list())
        self.search_in_text_var.trace_add("write", lambda *_: self.refresh_questions_list())
        self.search_in_explanation_var.trace_add("write", lambda *_: self.refresh_questions_list())
        self.search_in_choices_var.trace_add("write", lambda *_: self.refresh_questions_list())
        self.search_in_meta_var.trace_add("write", lambda *_: self.refresh_questions_list())

        self.window.bind("<F11>", self.toggle_maximize)
        self.window.bind("<Control-m>", self.toggle_maximize)
        self.window.bind("<Configure>", self.on_window_configure)
        
        self.load_chapter_data()
        self.setup_ui()
        self.refresh_questions_list()
        
    def load_chapter_data(self):
        """Load chapter JSON file"""
        try:
            data = _load_json_file(self.chapter_file)
            
            # Handle both list and dict formats
            if isinstance(data, list) and data:
                self.chapter_data = data[0]
            else:
                self.chapter_data = data
            
            if not self.chapter_data:
                self.chapter_data = {"questions": [], "title": ""}
            
            self.questions = self.chapter_data.get("questions", [])
            self.sync_question_count()
            
            # Debug: Show how many questions loaded and if they have images
            print(f"DEBUG: Loaded {len(self.questions)} questions from {self.chapter_file.name}")
            questions_with_images = sum(1 for q in self.questions if q.get('image'))
            print(f"DEBUG: {questions_with_images} questions have image paths")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load chapter: {e}")
            self.window.destroy()
    
    def setup_ui(self):
        """Create the UI for advanced editor"""
        # Top toolbar
        toolbar = ttk.Frame(self.window)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        ttk.Button(toolbar, text="Add Question", command=self.add_question,
                  width=15, bootstyle="success").pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Delete Question", command=self.delete_question,
                  width=18, bootstyle="danger-outline").pack(side=tk.LEFT, padx=5)

        self.tools_menu = tk.Menu(
            self.window,
            tearoff=0,
            bg=COLORS["bg_card"],
            fg=COLORS["text_main"],
            activebackground=COLORS["primary"],
            activeforeground=COLORS["selection_fg"],
            relief=tk.FLAT,
            font=("Segoe UI", 9),
        )
        self.tools_menu.add_command(label="Delete Duplicates", command=self.delete_duplicate_questions)
        self.tools_menu.add_command(label="Smart Duplicates", command=self.delete_similar_questions)
        self.tools_menu.add_command(label="Fix Numbering", command=self.fix_question_numbering)
        self.tools_menu.add_command(label="Fix Escaped \\n", command=self.fix_escaped_newlines)
        self.tools_menu.add_command(label="Fix Choice IDs", command=self.fix_choice_ids)
        self.tools_menu.add_command(label="Fix Input Typing", command=self.fix_input_typing)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label="Validate Diagram Blocks", command=self.validate_diagram_blocks_for_chapter)

        self.tools_btn = ttk.Button(
            toolbar,
            text="Tools ▼",
            width=10,
            bootstyle="warning-outline",
            command=self.show_tools_menu,
        )
        self.tools_btn.pack(side=tk.LEFT, padx=5)
        self.tools_btn.bind("<Enter>", self.show_tools_menu)

        ttk.Button(toolbar, text="▲", command=self.move_question_up,
                  width=3, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="▼", command=self.move_question_down,
                  width=3, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=2)
        self.maximize_btn = ttk.Button(
            toolbar,
            text="Maximize",
            command=self.toggle_maximize,
            width=12,
            bootstyle="secondary-outline",
        )
        self.maximize_btn.pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="Save Changes", command=self.save_chapter,
                  width=15, bootstyle="primary").pack(side=tk.RIGHT, padx=5)

        # Main container
        container = ttk.Panedwindow(self.window, orient=tk.HORIZONTAL)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Left panel - Questions list
        left_frame = ttk.Frame(container)
        container.add(left_frame, weight=1)

        questions_header = ttk.Frame(left_frame)
        questions_header.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(questions_header, text="Questions", style="Header.TLabel").pack(
            side=tk.LEFT, anchor=tk.W)

        search_frame = ttk.Frame(questions_header)
        search_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        ttk.Label(search_frame, text="Search:", style="Muted.TLabel").pack(
            side=tk.LEFT, padx=(0, 6))
        search_entry = ttk.Entry(search_frame, textvariable=self.question_search_var, bootstyle="info")
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(search_frame, text="Clear", command=self.clear_question_search,
                  width=6, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=(6, 0))

        search_options_frame = ttk.Frame(left_frame)
        search_options_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Checkbutton(
            search_options_frame,
            text="Text",
            variable=self.search_in_text_var,
            bootstyle="info-round-toggle",
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Checkbutton(
            search_options_frame,
            text="Explanation",
            variable=self.search_in_explanation_var,
            bootstyle="info-round-toggle",
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            search_options_frame,
            text="Choices",
            variable=self.search_in_choices_var,
            bootstyle="info-round-toggle",
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            search_options_frame,
            text="Meta",
            variable=self.search_in_meta_var,
            bootstyle="info-round-toggle",
        ).pack(side=tk.LEFT, padx=4)

        list_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL)
        self.questions_listbox = tk.Listbox(
            left_frame,
            yscrollcommand=list_scroll.set,
            selectmode=tk.EXTENDED,
            exportselection=False,
        )
        _style_tk_listbox(self.questions_listbox)
        list_scroll.config(command=self.questions_listbox.yview)

        self.questions_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.questions_listbox.bind("<<ListboxSelect>>", self.on_question_select)
        self.questions_listbox.bind("<Button-3>", self.show_question_context_menu)

        # Right panel - Question editor
        right_frame = ttk.Frame(container)
        container.add(right_frame, weight=2)

        ttk.Label(right_frame, text="Edit Question", style="Header.TLabel").pack(
            fill=tk.X, pady=(0, 5))

        # Create scrollable frame for question editor
        self.editor_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL)
        self.editor_canvas = tk.Canvas(right_frame, yscrollcommand=self.editor_scroll.set,
                                        bg=COLORS["bg_card"], highlightthickness=0)
        self.editor_scroll.config(command=self.editor_canvas.yview)

        self.editor_frame = ttk.Frame(self.editor_canvas)
        self.editor_frame.bind("<Configure>", lambda e: self.editor_canvas.configure(
            scrollregion=self.editor_canvas.bbox("all")))

        self.canvas_window = self.editor_canvas.create_window((0, 0), window=self.editor_frame,
                                                               anchor=tk.NW)

        # Stretch editor frame to fill canvas width
        self.editor_canvas.bind('<Configure>',
            lambda e: self.editor_canvas.itemconfigure(self.canvas_window, width=e.width))

        self.editor_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Initialize editor widgets (will be populated when question is selected)
        self.init_editor_widgets()

    def show_tools_menu(self, event=None):
        """Show the tools menu below the tools button."""
        if not hasattr(self, "tools_btn") or not hasattr(self, "tools_menu"):
            return "break"

        x = self.tools_btn.winfo_rootx()
        y = self.tools_btn.winfo_rooty() + self.tools_btn.winfo_height()
        try:
            self.tools_menu.tk_popup(x, y)
        finally:
            self.tools_menu.after_idle(self.tools_menu.grab_release)
        return "break"

    def on_window_configure(self, event=None):
        """Keep maximize button label in sync with current window state."""
        new_state = self._window_is_maximized()
        if new_state != self.is_maximized:
            self.is_maximized = new_state
            if hasattr(self, "maximize_btn"):
                self.maximize_btn.configure(text="Restore" if self.is_maximized else "Maximize")

    def _window_is_maximized(self):
        """Return True when the chapter editor window is maximized."""
        try:
            return self.window.state() == "zoomed"
        except tk.TclError:
            try:
                return bool(self.window.attributes("-zoomed"))
            except tk.TclError:
                return False

    def toggle_maximize(self, event=None):
        """Toggle between maximized and normal chapter editor window size."""
        should_maximize = not self._window_is_maximized()

        try:
            self.window.state("zoomed" if should_maximize else "normal")
        except tk.TclError:
            try:
                self.window.attributes("-zoomed", should_maximize)
            except tk.TclError:
                pass

        self.on_window_configure()
        return "break"
    
    def init_editor_widgets(self):
        """Initialize editor widget placeholders"""
        for widget in self.editor_frame.winfo_children():
            widget.destroy()

        # Question ID
        ttk.Label(self.editor_frame, text="Question ID:", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(10, 5))
        self.q_id = ttk.Entry(self.editor_frame, bootstyle="info")
        self.q_id.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Question Number
        ttk.Label(self.editor_frame, text="Question Number:", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 5))
        self.q_number = ttk.Entry(self.editor_frame, bootstyle="info")
        self.q_number.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Question Text
        ttk.Label(self.editor_frame, text="Question Text:", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 5))
        self.q_text = FormattedTextEditor(self.editor_frame, height=6, show_preview=True)
        self.q_text.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Image
        ttk.Label(self.editor_frame, text="Question Image:", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 5))

        img_frame = ttk.Frame(self.editor_frame)
        img_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.q_image = ttk.Entry(img_frame, state="readonly", bootstyle="info")
        self.q_image.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(img_frame, text="Browse", command=self.select_image,
                  width=10, bootstyle="info-outline").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(img_frame, text="Clear", command=self.clear_image,
                  width=8, bootstyle="warning-outline").pack(side=tk.LEFT, padx=2)

        # Image preview section
        ttk.Label(self.editor_frame, text="Image Preview:", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(10, 5))
        self.image_preview_frame = ttk.Frame(self.editor_frame, bootstyle="dark")
        self.image_preview_frame.pack(fill=tk.BOTH, padx=10, pady=(0, 10), ipady=20, expand=False)

        self.image_preview_label = ttk.Label(self.image_preview_frame, text="No image selected",
                                              style="Muted.TLabel")
        self.image_preview_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Input Type
        ttk.Label(self.editor_frame, text="Input Type:", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 5))
        self.q_input_type = ttk.Combobox(self.editor_frame, values=["radio", "checkbox"],
                                        state="readonly", width=20, bootstyle="info")
        self.q_input_type.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Correct Answer
        ttk.Label(self.editor_frame, text="Correct Answer(s):", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 5))
        self.q_correct = ttk.Entry(self.editor_frame, bootstyle="info")
        self.q_correct.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Explanation
        ttk.Label(self.editor_frame, text="Explanation:", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 5))
        self.q_explanation = FormattedTextEditor(self.editor_frame, height=4, show_preview=False)
        self.q_explanation.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Choices section
        ttk.Label(self.editor_frame, text="Choices:", style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(10, 5))

        # Choices listbox
        choices_frame = ttk.Frame(self.editor_frame)
        choices_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        choices_scroll = ttk.Scrollbar(choices_frame, orient=tk.VERTICAL)
        self.choices_listbox = tk.Listbox(choices_frame, height=5,
                                         yscrollcommand=choices_scroll.set)
        _style_tk_listbox(self.choices_listbox)
        choices_scroll.config(command=self.choices_listbox.yview)

        self.choices_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        choices_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.choices_listbox.bind("<<ListboxSelect>>", self.on_choice_select)

        # Choice edit buttons
        choice_btn_frame = ttk.Frame(self.editor_frame)
        choice_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(choice_btn_frame, text="Add Choice", command=self.add_choice,
                  width=12, bootstyle="success-outline").pack(side=tk.LEFT, padx=2)
        ttk.Button(choice_btn_frame, text="Edit Choice", command=self.edit_choice,
                  width=12, bootstyle="info-outline").pack(side=tk.LEFT, padx=2)
        ttk.Button(choice_btn_frame, text="Delete Choice", command=self.delete_choice,
                  width=14, bootstyle="danger-outline").pack(side=tk.LEFT, padx=2)

        ttk.Button(choice_btn_frame, text="Update Question", command=self.update_current_question,
                  width=16, bootstyle="primary").pack(side=tk.RIGHT, padx=2)
    
    def refresh_questions_list(self):
        """Refresh questions list"""
        selected_actual_indices = self.get_selected_question_indices()
        if not selected_actual_indices and self.current_question_idx is not None:
            selected_actual_indices = [self.current_question_idx]

        self.filtered_question_indices = self.get_filtered_question_indices()
        self.questions_listbox.delete(0, tk.END)
        for display_idx, question_idx in enumerate(self.filtered_question_indices):
            q = self.questions[question_idx]
            display = f"{question_idx + 1}. {q.get('number', '')} - {q.get('text', '')[:60]}"
            self.questions_listbox.insert(tk.END, display)

        self.restore_question_selection(selected_actual_indices)

    def get_filtered_question_indices(self):
        """Return question indexes that match the current search filter."""
        term = self._normalize_for_compare(self.question_search_var.get())
        if not term:
            return list(range(len(self.questions)))

        matches = []
        for idx, question in enumerate(self.questions):
            haystack = self._question_search_blob(question)
            if term in haystack:
                matches.append(idx)
        return matches

    def _question_search_blob(self, question):
        """Build searchable text for a question."""
        parts = []

        # Keep text searchable by default even if all options are unchecked.
        search_text = self.search_in_text_var.get()
        search_explanation = self.search_in_explanation_var.get()
        search_choices = self.search_in_choices_var.get()
        search_meta = self.search_in_meta_var.get()
        if not any([search_text, search_explanation, search_choices, search_meta]):
            search_text = True

        if search_text:
            parts.append(question.get("text", ""))

        if search_explanation:
            parts.append(question.get("explanation", ""))

        if search_choices:
            for choice in question.get("choices", []) or []:
                parts.extend([
                    choice.get("value", ""),
                    choice.get("label", ""),
                    choice.get("text", ""),
                ])

        if search_meta:
            parts.extend([
                question.get("id", ""),
                question.get("number", ""),
                question.get("correctAnswer", ""),
                question.get("inputType", ""),
                question.get("image", ""),
            ])

        return self._normalize_for_compare(" ".join(str(part) for part in parts if part is not None))

    def get_selected_question_indices(self):
        """Map selected listbox rows to actual question indexes."""
        if not hasattr(self, "questions_listbox"):
            return []

        selected = []
        for row_idx in self.questions_listbox.curselection():
            if 0 <= row_idx < len(self.filtered_question_indices):
                selected.append(self.filtered_question_indices[row_idx])
        return selected

    def restore_question_selection(self, selected_actual_indices):
        """Restore listbox selection from actual question indexes."""
        if not hasattr(self, "questions_listbox"):
            return

        self.questions_listbox.selection_clear(0, tk.END)
        if not selected_actual_indices:
            return

        selected_rows = []
        for actual_idx in selected_actual_indices:
            if actual_idx in self.filtered_question_indices:
                selected_rows.append(self.filtered_question_indices.index(actual_idx))

        for row_idx in selected_rows:
            self.questions_listbox.selection_set(row_idx)
        if selected_rows:
            self.questions_listbox.activate(selected_rows[0])

    def clear_question_search(self):
        """Clear the question search filter."""
        self.question_search_var.set("")
        self.refresh_questions_list()
    
    def on_question_select(self, event):
        """Handle question selection"""
        selected_indices = self.get_selected_question_indices()
        if not selected_indices:
            return
        
        self.current_question_idx = selected_indices[0]
        self.display_question()
    
    def show_question_context_menu(self, event):
        """Show context menu on right-click"""
        # Select the item under the cursor
        idx = self.questions_listbox.nearest(event.y)
        if idx < 0:
            return
        
        # Ensure the clicked item is selected
        if idx not in self.questions_listbox.curselection():
            self.questions_listbox.selection_clear(0, tk.END)
            self.questions_listbox.selection_set(idx)
            self.questions_listbox.activate(idx)
            self.current_question_idx = idx
            self.display_question()
        
        # Create context menu
        context_menu = tk.Menu(self.window, tearoff=0, bg=COLORS['bg_card'], 
                               fg=COLORS['text_main'], activebackground=COLORS['primary'],
                               activeforeground=COLORS['selection_fg'], relief=tk.FLAT,
                               font=("Segoe UI", 9))
        
        context_menu.add_command(label="Edit", command=self.display_question)
        context_menu.add_separator()
        context_menu.add_command(label="Delete", command=self.delete_question)
        context_menu.add_separator()
        context_menu.add_command(label="Move Up", command=self.move_question_up)
        context_menu.add_command(label="Move Down", command=self.move_question_down)
        context_menu.add_separator()
        context_menu.add_command(label="Duplicate", command=self.duplicate_question)
        
        # Display menu at cursor position
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.after_idle(context_menu.grab_release)
    
    def display_question(self):
        """Display current question in editor"""
        if self.current_question_idx is None or self.current_question_idx >= len(self.questions):
            return
        
        q = self.questions[self.current_question_idx]
        
        self.q_id.delete(0, tk.END)
        self.q_id.insert(0, q.get('id', ''))
        
        self.q_number.delete(0, tk.END)
        self.q_number.insert(0, q.get('number', ''))
        
        self.q_text.delete(1.0, tk.END)
        self.q_text.insert(1.0, q.get('text', ''))
        
        # Update image field and preview
        image_path = q.get('image', '')
        self.q_image.config(state="normal")
        self.q_image.delete(0, tk.END)
        if image_path:
            self.q_image.insert(0, str(image_path))  # Ensure it's a string
        self.q_image.config(state="readonly")
        
        # Update image preview - with better path handling
        if image_path and str(image_path).strip():
            image_path_str = str(image_path).strip()
            # Convert forward slashes to backslashes for Windows
            normalized_path = image_path_str.replace('/', '\\')
            full_path = self.base_path / normalized_path
            
            print(f"DEBUG: Checking image path")
            print(f"  Stored path: {image_path_str}")
            print(f"  Normalized: {normalized_path}")
            print(f"  Full path: {full_path}")
            print(f"  Exists: {full_path.exists()}")
            
            if full_path.exists():
                try:
                    img_size = full_path.stat().st_size / 1024
                    img_name = Path(image_path_str).name
                    preview_text = f"✓ Image: {img_name}\nSize: {img_size:.1f} KB"
                    self.image_preview_label.config(text=preview_text)
                except Exception as e:
                    self.image_preview_label.config(text=f"Error: {str(e)}")
            else:
                # File not found - show diagnostic info
                self.image_preview_label.config(text=f"⚠️ Image not found\n\nPath: {image_path_str}\n\n(Checked: {full_path})")
        else:
            self.image_preview_label.config(text="No image selected")
        
        self.q_input_type.set(q.get('inputType', 'radio'))
        
        self.q_correct.delete(0, tk.END)
        self.q_correct.insert(0, q.get('correctAnswer', ''))
        
        self.q_explanation.delete(1.0, tk.END)
        self.q_explanation.insert(1.0, q.get('explanation', ''))
        
        # Load choices
        self.refresh_choices_list()
    
    def refresh_choices_list(self):
        """Refresh choices list"""
        if self.current_question_idx is None:
            return
        
        self.choices_listbox.delete(0, tk.END)
        q = self.questions[self.current_question_idx]
        choices = q.get('choices', [])
        
        for choice in choices:
            display = f"{choice.get('value', '')} - {choice.get('text', '')}"
            self.choices_listbox.insert(tk.END, display)
    
    def on_choice_select(self, event):
        """Handle choice selection"""
        pass  # Can add more features later
    
    def add_choice(self):
        """Add new choice to current question"""
        if self.current_question_idx is None:
            messagebox.showwarning("Warning", "Select a question first")
            return

        dialog = tk.Toplevel(self.window)
        _style_dialog(dialog, "Add Choice", "550x380")
        dialog.transient(self.window)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Choice Value (A, B, C, D):", style="SubHeader.TLabel").pack(
            fill=tk.X, pady=(0, 5))
        val_entry = ttk.Entry(frame, bootstyle="info")
        val_entry.pack(fill=tk.X, pady=(0, 10))
        val_entry.focus()

        ttk.Label(frame, text="Choice Text:", style="SubHeader.TLabel").pack(
            fill=tk.X, pady=(0, 5))
        text_entry = FormattedTextEditor(frame, height=4, show_preview=False)
        text_entry.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        def save():
            value = val_entry.get().strip()
            text = text_entry.get(1.0, tk.END).strip()

            if not value or not text:
                messagebox.showwarning("Warning", "Value and text are required")
                return

            q = self.questions[self.current_question_idx]
            new_choice = {
                "value": value,
                "label": value,
                "text": text
            }

            if "choices" not in q:
                q["choices"] = []

            q["choices"].append(new_choice)
            self.refresh_choices_list()
            dialog.destroy()

        ttk.Button(frame, text="Add", command=save, width=20, bootstyle="success").pack(pady=10)
        dialog.bind('<Return>', lambda e: save())
    
    def edit_choice(self):
        """Edit selected choice"""
        if self.current_question_idx is None:
            messagebox.showwarning("Warning", "Select a question first")
            return

        selection = self.choices_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a choice first")
            return

        choice_idx = selection[0]
        q = self.questions[self.current_question_idx]
        choice = q.get('choices', [])[choice_idx]

        dialog = tk.Toplevel(self.window)
        _style_dialog(dialog, "Edit Choice", "550x380")
        dialog.transient(self.window)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Choice Value:", style="SubHeader.TLabel").pack(
            fill=tk.X, pady=(0, 5))
        val_entry = ttk.Entry(frame, bootstyle="info")
        val_entry.insert(0, choice.get('value', ''))
        val_entry.pack(fill=tk.X, pady=(0, 10))
        val_entry.focus()

        ttk.Label(frame, text="Choice Text:", style="SubHeader.TLabel").pack(
            fill=tk.X, pady=(0, 5))
        text_entry = FormattedTextEditor(frame, height=4, show_preview=False)
        text_entry.insert(1.0, choice.get('text', ''))
        text_entry.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        def save():
            value = val_entry.get().strip()
            text = text_entry.get(1.0, tk.END).strip()

            if not value or not text:
                messagebox.showwarning("Warning", "Value and text are required")
                return

            choice["value"] = value
            choice["label"] = value
            choice["text"] = text
            self.refresh_choices_list()
            dialog.destroy()

        ttk.Button(frame, text="Save", command=save, width=20, bootstyle="success").pack(pady=10)
        dialog.bind('<Return>', lambda e: save())
    
    def delete_choice(self):
        """Delete selected choice"""
        selection = self.choices_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a choice first")
            return
        
        choice_idx = selection[0]
        q = self.questions[self.current_question_idx]
        del q.get('choices', [])[choice_idx]
        self.refresh_choices_list()
    
    def select_image(self):
        """Select image for current question"""
        if self.current_question_idx is None:
            messagebox.showwarning("Warning", "Select a question first")
            return
        
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.gif"), ("All Files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            src = Path(file_path)
            
            # Get question number for image naming
            q = self.questions[self.current_question_idx]
            q_number = q.get('number', str(self.current_question_idx + 1))
            file_ext = src.suffix.lower()  # Get extension like .jpg, .png
            
            # Rename image to imageN_UUID.ext format (unique to prevent overwrites)
            safe_q_number = q_number.replace('.', '_')
            unique_id = uuid.uuid4().hex[:8]
            image_name = f"image{safe_q_number}_{unique_id}{file_ext}"
            dest = self.images_folder / image_name
            
            # Copy image to images folder
            shutil.copy2(src, dest)
            
            # Get the section name from section_path
            section_name = Path(self.section_path).name
            
            # Update image path (relative path for web)
            rel_path = f"data/{section_name}/images/{image_name}"
            
            # Store path and update entry field
            self.current_image_path = rel_path
            
            # Update entry field (readonly, so use different method)
            self.q_image.config(state="normal")
            self.q_image.delete(0, tk.END)
            self.q_image.insert(0, rel_path)
            self.q_image.config(state="readonly")
            
            # Update preview
            self.update_image_preview(dest, image_name)
            
            messagebox.showinfo("Success", f"Image saved as:\n{image_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy image: {e}")
            self.image_preview_label.config(text=f"Error: {str(e)}")
    
    def clear_image(self):
        """Clear image for current question"""
        self.q_image.config(state="normal")
        self.q_image.delete(0, tk.END)
        self.q_image.config(state="readonly")
        self.current_image_path = None
        self.image_preview_label.config(text="No image selected")
    
    def update_image_preview(self, image_path, image_name):
        """Update image preview in UI"""
        try:
            if not Path(image_path).exists():
                self.image_preview_label.config(text="Image file not found ❌")
                return
            
            # Show file info as text (file size and name)
            img_size = Path(image_path).stat().st_size / 1024  # Size in KB
            preview_text = f"✓ Image loaded: {image_name}\nSize: {img_size:.1f} KB"
            self.image_preview_label.config(text=preview_text)
        except Exception as e:
            self.image_preview_label.config(text=f"Error: {str(e)}")
    
    def update_current_question(self):
        """Update current question with edited values"""
        if self.current_question_idx is None:
            messagebox.showwarning("Warning", "No question selected")
            return
        
        q = self.questions[self.current_question_idx]
        
        q['id'] = self.q_id.get()
        q['number'] = self.q_number.get()
        q['text'] = self.q_text.get(1.0, tk.END).strip()
        
        # Get image path from entry field and save it properly
        image_path = self.q_image.get().strip()
        if image_path:
            q['image'] = image_path
        else:
            # Remove image key if empty
            q.pop('image', None)
        
        q['inputType'] = self.q_input_type.get()
        q['correctAnswer'] = self.q_correct.get()
        self._normalize_question_answer_fields(q, force_input_type=True)
        q['explanation'] = self.q_explanation.get(1.0, tk.END).strip()
        self.sync_question_count()
        
        self.refresh_questions_list()
        self.restore_question_selection([self.current_question_idx])
        # Force display refresh to show updated data including image path
        self.display_question()
        messagebox.showinfo("Success", "Question updated ✓\n(Click 'Save Changes' to save to file)")

    def validate_diagram_blocks_for_chapter(self):
        """Validate diagram fenced code blocks in question text and explanation."""
        if not self.questions:
            messagebox.showinfo("Validate Diagrams", "No questions available.")
            return

        subject_id = self.section_path.name if self.section_path else ""
        issues = []

        for i, q in enumerate(self.questions):
            q_num = str(q.get("number") or i + 1)
            text_warnings = validate_diagram_blocks(q.get("text", ""), subject_id=subject_id)
            for warning in text_warnings:
                issues.append(f"Q{q_num} text L{warning['line']}: {warning['message']}")

            exp_warnings = validate_diagram_blocks(q.get("explanation", ""), subject_id=subject_id)
            for warning in exp_warnings:
                issues.append(f"Q{q_num} explanation L{warning['line']}: {warning['message']}")

        if not issues:
            messagebox.showinfo("Validate Diagrams", "No diagram warnings found.")
            return

        preview = "\n".join(issues[:20])
        if len(issues) > 20:
            preview += f"\n... and {len(issues) - 20} more"
        messagebox.showwarning("Diagram Warnings", preview)

    def _normalize_answer_letters(self, value, question=None):
        """Normalize answer keys to compact uppercase form (e.g., A, B, C -> ABC)."""
        raw = str(value or "").upper()
        allowed = []
        if isinstance(question, dict):
            for choice in question.get("choices", []) or []:
                key = str(choice.get("value", "")).strip().upper()
                if len(key) == 1:
                    allowed.append(key)

        allowed_set = set(allowed)
        letters = []
        for ch in re.findall(r"[A-Z0-9]", raw):
            if allowed_set and ch not in allowed_set:
                continue
            if ch not in letters:
                letters.append(ch)
        return "".join(letters)

    def _normalize_question_answer_fields(self, question, force_input_type=False):
        """Normalize a question's correctAnswer and optionally enforce matching inputType."""
        if not isinstance(question, dict):
            return False, False

        old_answer = str(question.get("correctAnswer", ""))
        old_input_type = str(question.get("inputType", "radio") or "radio").lower()

        normalized_answer = self._normalize_answer_letters(old_answer, question)
        question["correctAnswer"] = normalized_answer

        type_changed = False
        if force_input_type:
            new_type = "checkbox" if len(normalized_answer) > 1 else "radio"
            if old_input_type != new_type:
                type_changed = True
            question["inputType"] = new_type
        elif old_input_type not in {"radio", "checkbox"}:
            question["inputType"] = "radio"
            type_changed = True

        answer_changed = normalized_answer != old_answer
        return answer_changed, type_changed

    def _choice_id_for_index(self, index):
        """Return a stable choice label for a zero-based choice index."""
        index += 1
        letters = []
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            letters.append(chr(65 + remainder))
        return "".join(reversed(letters))

    def _normalize_question_choice_ids(self, question):
        """Renumber choice IDs and remap correctAnswer to the new IDs."""
        if not isinstance(question, dict):
            return False, False

        choices = question.get("choices", []) or []
        if not choices:
            return False, False

        old_to_new = {}
        new_values = []
        old_answer = str(question.get("correctAnswer", "") or "").upper()
        choice_changed = False

        for idx, choice in enumerate(choices):
            new_value = self._choice_id_for_index(idx)
            old_value = str(choice.get("value", "")).strip().upper()
            if old_value:
                old_to_new[old_value] = new_value

            if old_value != new_value or str(choice.get("label", "")).strip().upper() != new_value:
                choice_changed = True

            choice["value"] = new_value
            choice["label"] = new_value
            new_values.append(new_value)

        remapped_answer = []
        for char in re.findall(r"[A-Z0-9]", old_answer):
            mapped_value = old_to_new.get(char)
            if mapped_value and mapped_value not in remapped_answer:
                remapped_answer.append(mapped_value)
            elif char in new_values and char not in remapped_answer:
                remapped_answer.append(char)

        normalized_answer = "".join(remapped_answer)
        question["correctAnswer"] = normalized_answer

        return choice_changed, normalized_answer != old_answer

    def fix_input_typing(self, show_message=True):
        """Normalize correctAnswer and force matching inputType for all questions."""
        if not self.questions:
            if show_message:
                messagebox.showinfo("No Questions", "There are no questions to fix.")
            return (0, 0)

        answer_changes = 0
        type_changes = 0
        for question in self.questions:
            answer_changed, type_changed = self._normalize_question_answer_fields(
                question,
                force_input_type=True,
            )
            if answer_changed:
                answer_changes += 1
            if type_changed:
                type_changes += 1

        self.refresh_questions_list()
        if self.current_question_idx is not None and self.questions:
            keep_idx = max(0, min(self.current_question_idx, len(self.questions) - 1))
            self.current_question_idx = keep_idx
            self.restore_question_selection([keep_idx])
            self.display_question()

        if show_message:
            if answer_changes or type_changes:
                messagebox.showinfo(
                    "Input Typing Fixed",
                    f"Normalized correct answers in {answer_changes} question(s).\n"
                    f"Adjusted input type in {type_changes} question(s)."
                )
            else:
                messagebox.showinfo(
                    "Already Correct",
                    "Input types and correct answers are already consistent."
                )

        return answer_changes, type_changes

    def fix_choice_ids(self, show_message=True):
        """Renumber choice IDs and keep correctAnswer aligned with the new IDs."""
        if not self.questions:
            if show_message:
                messagebox.showinfo("No Questions", "There are no questions to fix.")
            return (0, 0)

        choice_changes = 0
        answer_changes = 0
        for question in self.questions:
            choices_changed, answer_changed = self._normalize_question_choice_ids(question)
            if choices_changed:
                choice_changes += 1
            if answer_changed:
                answer_changes += 1

        self.refresh_questions_list()
        if self.current_question_idx is not None and self.questions:
            keep_idx = max(0, min(self.current_question_idx, len(self.questions) - 1))
            self.current_question_idx = keep_idx
            self.restore_question_selection([keep_idx])
            self.display_question()

        if show_message:
            if choice_changes or answer_changes:
                messagebox.showinfo(
                    "Choice IDs Fixed",
                    f"Renumbered choice IDs in {choice_changes} question(s).\n"
                    f"Adjusted correct answers in {answer_changes} question(s)."
                )
            else:
                messagebox.showinfo(
                    "Already Correct",
                    "Choice IDs and correct answers are already consistent."
                )

        return choice_changes, answer_changes
    
    def add_question(self):
        """Add new question"""
        new_q = {
            "id": f"{len(self.questions) + 1}",
            "number": f"{len(self.questions) + 1}",
            "text": "New question",
            "image": "",
            "choices": [
                {"value": "A", "label": "A", "text": "Choice A"},
                {"value": "B", "label": "B", "text": "Choice B"}
            ],
            "inputName": f"Q{len(self.questions)}",
            "inputType": "radio",
            "correctAnswer": "A",
            "explanation": ""
        }
        
        self.questions.append(new_q)
        self.sync_question_count()
        self.refresh_questions_list()
        self.current_question_idx = len(self.questions) - 1
        self.restore_question_selection([self.current_question_idx])
        # Force display of the new question
        self.display_question()
        messagebox.showinfo("Success", "New question added")

    def duplicate_question(self):
        """Duplicate the currently selected question"""
        if self.current_question_idx is None or self.current_question_idx >= len(self.questions):
            messagebox.showwarning("Warning", "Select a question first")
            return
        
        # Deep copy the current question
        import copy
        original = self.questions[self.current_question_idx]
        duplicated = copy.deepcopy(original)
        
        # Generate new ID and update other fields
        duplicated["id"] = str(uuid.uuid4())
        duplicated["number"] = str(len(self.questions) + 1)
        duplicated["inputName"] = f"Q{len(self.questions)}"
        
        # Insert after current question
        self.questions.insert(self.current_question_idx + 1, duplicated)
        self.sync_question_count()
        self.refresh_questions_list()
        self.current_question_idx = self.current_question_idx + 1
        self.restore_question_selection([self.current_question_idx])
        self.display_question()
        messagebox.showinfo("Success", "Question duplicated")

    def _normalize_for_compare(self, value):
        """Normalize text so duplicate checks are whitespace/case insensitive."""
        return re.sub(r"\s+", " ", str(value or "")).strip().lower()

    def _question_signature(self, question):
        """Build a stable signature from question title and choices."""
        title = self._normalize_for_compare(question.get("text", ""))
        normalized_choices = []
        for choice in question.get("choices", []) or []:
            normalized_choices.append((
                self._normalize_for_compare(choice.get("value", "")),
                self._normalize_for_compare(choice.get("text", "")),
            ))
        # Sort so duplicate detection works even if choice order differs.
        return title, tuple(sorted(normalized_choices))

    def _select_duplicates_to_delete(self, duplicate_groups):
        """Show interactive duplicate selector and return selected duplicate indexes."""
        dlg = tk.Toplevel(self.window)
        _style_dialog(dlg, "Select Duplicates To Delete", "900x560")
        dlg.transient(self.window)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=12, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Duplicate Questions", style="Header.TLabel").pack(
            anchor=tk.W, pady=(0, 4)
        )
        ttk.Label(
            frame,
            text=(
                "Choose which duplicate entries to delete. "
                "The original question in each group is kept."
            ),
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        dup_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            yscrollcommand=list_scroll.set,
            exportselection=False,
        )
        _style_tk_listbox(dup_listbox)
        list_scroll.config(command=dup_listbox.yview)

        listbox_entries = []
        for original_idx, dup_idx in duplicate_groups:
            original_q = self.questions[original_idx]
            dup_q = self.questions[dup_idx]
            original_number = original_q.get("number", str(original_idx + 1))
            dup_number = dup_q.get("number", str(dup_idx + 1))

            title = str(dup_q.get("text", "")).strip().replace("\n", " ")
            title = re.sub(r"\s+", " ", title)
            if len(title) > 85:
                title = title[:85] + "..."

            row_text = f"Delete Q{dup_number} (duplicate of Q{original_number})  |  {title}"
            listbox_entries.append((dup_idx, row_text))
            dup_listbox.insert(tk.END, row_text)

        # Default behavior: all duplicates selected.
        if listbox_entries:
            dup_listbox.selection_set(0, tk.END)

        dup_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.pack(fill=tk.X, pady=(10, 6))

        def select_all():
            dup_listbox.selection_set(0, tk.END)

        def clear_selection():
            dup_listbox.selection_clear(0, tk.END)

        def toggle_selection():
            selected = set(dup_listbox.curselection())
            for i in range(dup_listbox.size()):
                if i in selected:
                    dup_listbox.selection_clear(i)
                else:
                    dup_listbox.selection_set(i)

        ttk.Button(ctrl_frame, text="Select All", command=select_all,
                   width=12, bootstyle="success-outline").pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl_frame, text="Clear", command=clear_selection,
                   width=10, bootstyle="warning-outline").pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl_frame, text="Toggle", command=toggle_selection,
                   width=10, bootstyle="info-outline").pack(side=tk.LEFT, padx=3)

        result = {"selected": None}

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(4, 0))

        def confirm():
            selected_rows = dup_listbox.curselection()
            if not selected_rows:
                messagebox.showwarning("No Selection", "Select at least one duplicate to delete.")
                return
            selected_dups = [listbox_entries[i][0] for i in selected_rows]
            result["selected"] = sorted(set(selected_dups))
            dlg.destroy()

        def cancel():
            dlg.destroy()

        ttk.Button(btn_frame, text="Delete Selected", command=confirm,
                   width=16, bootstyle="danger").pack(side=tk.RIGHT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=cancel,
                   width=12, bootstyle="secondary-outline").pack(side=tk.RIGHT)

        dlg.bind("<Escape>", lambda e: cancel())
        dlg.bind("<Return>", lambda e: confirm())
        dlg.wait_window()
        return result["selected"]

    def _select_similar_to_delete(self, similar_pairs):
        """Show interactive similar-question selector and return selected duplicate indexes."""
        dlg = tk.Toplevel(self.window)
        _style_dialog(dlg, "Select Similar Questions To Delete", "920x580")
        dlg.transient(self.window)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=12, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Similar Questions (Smart Detector)", style="Header.TLabel").pack(
            anchor=tk.W, pady=(0, 4)
        )
        ttk.Label(
            frame,
            text=(
                "These are likely duplicates based on similar wording and choices. "
                "Select which entries to delete."
            ),
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        sim_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            yscrollcommand=list_scroll.set,
            exportselection=False,
        )
        _style_tk_listbox(sim_listbox)
        list_scroll.config(command=sim_listbox.yview)

        listbox_entries = []
        for keep_idx, dup_idx, score in similar_pairs:
            keep_q = self.questions[keep_idx]
            dup_q = self.questions[dup_idx]
            keep_number = keep_q.get("number", str(keep_idx + 1))
            dup_number = dup_q.get("number", str(dup_idx + 1))

            title = str(dup_q.get("text", "")).strip().replace("\n", " ")
            title = re.sub(r"\s+", " ", title)
            if len(title) > 80:
                title = title[:80] + "..."

            row_text = (
                f"Delete Q{dup_number} (similar to Q{keep_number}) "
                f"| score: {score:.0%} | {title}"
            )
            listbox_entries.append((dup_idx, row_text))
            sim_listbox.insert(tk.END, row_text)

        if listbox_entries:
            sim_listbox.selection_set(0, tk.END)

        sim_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.pack(fill=tk.X, pady=(10, 6))

        def select_all():
            sim_listbox.selection_set(0, tk.END)

        def clear_selection():
            sim_listbox.selection_clear(0, tk.END)

        def toggle_selection():
            selected = set(sim_listbox.curselection())
            for i in range(sim_listbox.size()):
                if i in selected:
                    sim_listbox.selection_clear(i)
                else:
                    sim_listbox.selection_set(i)

        ttk.Button(ctrl_frame, text="Select All", command=select_all,
                   width=12, bootstyle="success-outline").pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl_frame, text="Clear", command=clear_selection,
                   width=10, bootstyle="warning-outline").pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl_frame, text="Toggle", command=toggle_selection,
                   width=10, bootstyle="info-outline").pack(side=tk.LEFT, padx=3)

        result = {"selected": None}

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(4, 0))

        def confirm():
            selected_rows = sim_listbox.curselection()
            if not selected_rows:
                messagebox.showwarning("No Selection", "Select at least one similar question to delete.")
                return
            selected_dups = [listbox_entries[i][0] for i in selected_rows]
            result["selected"] = sorted(set(selected_dups))
            dlg.destroy()

        def cancel():
            dlg.destroy()

        ttk.Button(btn_frame, text="Delete Selected", command=confirm,
                   width=16, bootstyle="danger").pack(side=tk.RIGHT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=cancel,
                   width=12, bootstyle="secondary-outline").pack(side=tk.RIGHT)

        dlg.bind("<Escape>", lambda e: cancel())
        dlg.bind("<Return>", lambda e: confirm())
        dlg.wait_window()
        return result["selected"]

    def _question_text_similarity(self, left, right):
        """Compute fuzzy similarity between two question titles."""
        if not left or not right:
            return 0.0
        seq = SequenceMatcher(None, left, right).ratio()
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        union = left_tokens | right_tokens
        jaccard = (len(left_tokens & right_tokens) / len(union)) if union else 0.0
        return max(seq, jaccard)

    def _question_choices_similarity(self, q1, q2):
        """Compute fuzzy similarity between two questions' choices."""
        c1 = [self._normalize_for_compare(c.get("text", "")) for c in q1.get("choices", []) or []]
        c2 = [self._normalize_for_compare(c.get("text", "")) for c in q2.get("choices", []) or []]
        c1 = [c for c in c1 if c]
        c2 = [c for c in c2 if c]
        if not c1 or not c2:
            return 0.0

        s1 = " | ".join(sorted(c1))
        s2 = " | ".join(sorted(c2))
        seq = SequenceMatcher(None, s1, s2).ratio()
        t1 = set(c1)
        t2 = set(c2)
        union = t1 | t2
        overlap = (len(t1 & t2) / len(union)) if union else 0.0
        return max(seq, overlap)

    def delete_similar_questions(self):
        """Delete likely duplicate questions using fuzzy similarity matching."""
        if len(self.questions) < 2:
            messagebox.showinfo("Not Enough Questions", "Need at least 2 questions for smart duplicate detection.")
            return

        similar_pairs = []
        for i in range(len(self.questions)):
            for j in range(i + 1, len(self.questions)):
                q1 = self.questions[i]
                q2 = self.questions[j]

                t1 = self._normalize_for_compare(q1.get("text", ""))
                t2 = self._normalize_for_compare(q2.get("text", ""))
                if not t1 or not t2:
                    continue

                title_score = self._question_text_similarity(t1, t2)
                choices_score = self._question_choices_similarity(q1, q2)
                score = (0.75 * title_score) + (0.25 * choices_score)

                # Strict enough to avoid most false positives while catching close variants.
                short_text = min(len(t1), len(t2)) < 12
                if short_text:
                    is_similar = score >= 0.92 and title_score >= 0.88
                else:
                    is_similar = score >= 0.84 and title_score >= 0.76

                if is_similar:
                    similar_pairs.append((i, j, score))

        if not similar_pairs:
            messagebox.showinfo("No Similar Questions", "No likely duplicate questions were found.")
            return

        # Keep strongest matches first for cleaner review.
        similar_pairs.sort(key=lambda item: item[2], reverse=True)
        selected_indexes = self._select_similar_to_delete(similar_pairs)
        if selected_indexes is None:
            return

        previous_idx = self.current_question_idx
        for idx in reversed(selected_indexes):
            del self.questions[idx]

        renumbered_count = self.fix_question_numbering(show_message=False)
        self.sync_question_count()
        self.refresh_questions_list()

        if self.questions:
            new_idx = 0
            if previous_idx is not None:
                removed_before = sum(1 for i in selected_indexes if i < previous_idx)
                new_idx = previous_idx - removed_before
                new_idx = max(0, min(new_idx, len(self.questions) - 1))

            self.current_question_idx = new_idx
            self.restore_question_selection([new_idx])
            self.display_question()
        else:
            self.current_question_idx = None
            self.init_editor_widgets()

        messagebox.showinfo(
            "Success",
            f"Removed {len(selected_indexes)} similar question(s).\n"
            f"Renumbered {renumbered_count} question(s).\n"
            f"Remaining questions: {len(self.questions)}"
        )

    def fix_question_numbering(self, show_message=True):
        """Renumber question.number fields sequentially from 1..N."""
        if not self.questions:
            if show_message:
                messagebox.showinfo("No Questions", "There are no questions to renumber.")
            return 0

        changed = 0
        for idx, question in enumerate(self.questions, start=1):
            new_number = str(idx)
            old_number = str(question.get("number", ""))
            if old_number != new_number:
                question["number"] = new_number
                changed += 1

        self.refresh_questions_list()

        if self.current_question_idx is not None and self.questions:
            keep_idx = max(0, min(self.current_question_idx, len(self.questions) - 1))
            self.current_question_idx = keep_idx
            self.restore_question_selection([keep_idx])
            self.display_question()

        self.sync_question_count()

        if show_message:
            if changed:
                messagebox.showinfo(
                    "Numbering Fixed",
                    f"Updated numbering for {changed} question(s)."
                )
            else:
                messagebox.showinfo(
                    "Numbering Already Correct",
                    "Question numbering is already sequential."
                )

        return changed

    def fix_escaped_newlines(self, show_message=True):
        """Convert literal escaped newline sequences in question content to real newlines."""
        if not self.questions:
            if show_message:
                messagebox.showinfo("No Questions", "There are no questions to process.")
            return 0

        replacements = 0
        touched_questions = 0
        for question in self.questions:
            fixed_count = _fix_escaped_newlines_in_question(question)
            if fixed_count:
                touched_questions += 1
                replacements += fixed_count

        if touched_questions:
            self.refresh_questions_list()
            if self.current_question_idx is not None and self.questions:
                keep_idx = max(0, min(self.current_question_idx, len(self.questions) - 1))
                self.current_question_idx = keep_idx
                self.restore_question_selection([keep_idx])
                self.display_question()

        if show_message:
            if touched_questions:
                messagebox.showinfo(
                    "Escaped Newlines Fixed",
                    f"Updated {touched_questions} question(s).\n"
                    f"Replaced {replacements} escaped newline sequence(s)."
                )
            else:
                messagebox.showinfo(
                    "Already Clean",
                    "No escaped newline sequences were found."
                )

        return replacements

    def sync_question_count(self):
        """Keep the chapter Questions field aligned with the actual question count."""
        count = len(self.questions)
        if hasattr(self, "ch_count"):
            self.ch_count.delete(0, tk.END)
            self.ch_count.insert(0, str(count))
        if self.chapter_data is not None:
            self.chapter_data["q"] = count
        return count

    def delete_duplicate_questions(self):
        """Delete questions that have the same title and the same choices."""
        if not self.questions:
            messagebox.showinfo("No Questions", "There are no questions to deduplicate.")
            return

        first_seen = {}
        duplicate_groups = []

        for idx, question in enumerate(self.questions):
            sig = self._question_signature(question)
            if sig in first_seen:
                duplicate_groups.append((first_seen[sig], idx))
            else:
                first_seen[sig] = idx

        if not duplicate_groups:
            messagebox.showinfo("No Duplicates", "No duplicate questions were found.")
            return

        duplicate_indexes = self._select_duplicates_to_delete(duplicate_groups)
        if duplicate_indexes is None:
            return

        previous_idx = self.current_question_idx

        for idx in reversed(duplicate_indexes):
            del self.questions[idx]

        renumbered_count = self.fix_question_numbering(show_message=False)
        self.sync_question_count()

        self.refresh_questions_list()

        if self.questions:
            new_idx = 0
            if previous_idx is not None:
                removed_before = sum(1 for i in duplicate_indexes if i < previous_idx)
                new_idx = previous_idx - removed_before
                new_idx = max(0, min(new_idx, len(self.questions) - 1))

            self.current_question_idx = new_idx
            self.restore_question_selection([new_idx])
            self.display_question()
        else:
            self.current_question_idx = None
            self.init_editor_widgets()

        messagebox.showinfo(
            "Success",
            f"Removed {len(duplicate_indexes)} duplicate question(s).\n"
            f"Renumbered {renumbered_count} question(s).\n"
            f"Remaining questions: {len(self.questions)}"
        )
    
    def delete_question(self):
        """Delete the currently selected question(s)."""
        selected_question_indices = self.get_selected_question_indices()
        if not selected_question_indices and self.current_question_idx is not None:
            selected_question_indices = [self.current_question_idx]

        if not selected_question_indices:
            messagebox.showwarning("Warning", "Select at least one question first")
            return

        selected_question_indices = sorted(set(selected_question_indices))
        selected_questions = [self.questions[idx] for idx in selected_question_indices]
        has_any_image = any(question.get('image', '') for question in selected_questions)

        dlg = tk.Toplevel(self.window)
        _style_dialog(dlg, "Delete Question(s)", "720x360" if has_any_image else "720x300")
        dlg.transient(self.window)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=12, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=f"Delete {len(selected_question_indices)} selected question(s)?",
            style="Header.TLabel"
        ).pack(anchor=tk.W, pady=(0, 8))

        preview_frame = ttk.Frame(frame)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        preview_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL)
        preview_list = tk.Listbox(
            preview_frame,
            height=8,
            yscrollcommand=preview_scroll.set,
            exportselection=False,
        )
        _style_tk_listbox(preview_list)
        preview_scroll.config(command=preview_list.yview)

        for idx in selected_question_indices:
            question = self.questions[idx]
            q_num = question.get('number', str(idx + 1))
            title = str(question.get('text', '')).strip().replace('\n', ' ')
            title = re.sub(r'\s+', ' ', title)
            if len(title) > 90:
                title = title[:90] + '...'
            preview_list.insert(tk.END, f"Q{q_num} - {title}")

        preview_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        del_image_var = tk.BooleanVar(value=False)
        if has_any_image:
            ttk.Label(frame, text="Some selected questions have images.").pack(anchor=tk.W, pady=(8, 0))
            ttk.Checkbutton(
                frame,
                text="Also delete image files from disk (permanent)",
                variable=del_image_var,
                bootstyle="warning"
            ).pack(anchor=tk.W, pady=(4, 8))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        def do_delete():
            if del_image_var.get():
                for idx in selected_question_indices:
                    image_path = self.questions[idx].get('image', '')
                    if not image_path:
                        continue
                    try:
                        img_path = self.base_path / image_path
                        if img_path.exists():
                            img_path.unlink()
                            print(f"Deleted image: {image_path}")
                    except Exception as e:
                        print(f"Warning: Failed to delete image {image_path}: {e}")

            previous_idx = self.current_question_idx
            for idx in reversed(selected_question_indices):
                del self.questions[idx]

            self.fix_question_numbering(show_message=False)
            self.sync_question_count()

            remaining_count = len(self.questions)
            if remaining_count:
                next_idx = min(previous_idx if previous_idx is not None else 0, remaining_count - 1)
                self.current_question_idx = next_idx
                self.refresh_questions_list()
                self.restore_question_selection([next_idx])
                self.display_question()
            else:
                self.current_question_idx = None
                self.refresh_questions_list()
                self.init_editor_widgets()

            self.sync_question_count()

            dlg.destroy()
            messagebox.showinfo("Success", f"Deleted {len(selected_question_indices)} question(s)")

        def cancel():
            dlg.destroy()

        ttk.Button(btn_frame, text="Delete", command=do_delete, width=12, bootstyle="danger").pack(side=tk.RIGHT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=cancel, width=12, bootstyle="secondary-outline").pack(side=tk.RIGHT)
    
    def move_question_up(self):
        """Move the selected question up in the list"""
        if self.current_question_idx is None:
            messagebox.showwarning("Warning", "Select a question first")
            return

        idx = self.current_question_idx
        if idx <= 0:
            return

        self.questions[idx], self.questions[idx - 1] = self.questions[idx - 1], self.questions[idx]
        self.current_question_idx = idx - 1
        self.refresh_questions_list()
        self.restore_question_selection([self.current_question_idx])
        self.display_question()

    def move_question_down(self):
        """Move the selected question down in the list"""
        if self.current_question_idx is None:
            messagebox.showwarning("Warning", "Select a question first")
            return

        idx = self.current_question_idx
        if idx >= len(self.questions) - 1:
            return

        self.questions[idx], self.questions[idx + 1] = self.questions[idx + 1], self.questions[idx]
        self.current_question_idx = idx + 1
        self.refresh_questions_list()
        self.restore_question_selection([self.current_question_idx])
        self.display_question()

    def save_chapter(self):
        """Save chapter data back to JSON file"""
        try:
            # First, make sure current question is updated
            if self.current_question_idx is not None:
                q = self.questions[self.current_question_idx]
                
                print(f"DEBUG: Updating question #{self.current_question_idx}: {q.get('number', 'N/A')}")
                
                # Update all fields from the editor
                q['id'] = self.q_id.get()
                q['number'] = self.q_number.get()
                q['text'] = self.q_text.get(1.0, tk.END).strip()
                
                # Save image path
                image_path = self.q_image.get().strip()
                print(f"DEBUG: Entry field contains: '{image_path}'")
                print(f"DEBUG: Entry field state: {self.q_image.cget('state')}")
                
                if image_path:
                    q['image'] = image_path
                    print(f"DEBUG: Saving image path for question {q['number']}: {image_path}")
                else:
                    print(f"DEBUG: Image path is empty, removing from question")
                    q.pop('image', None)
                
                q['inputType'] = self.q_input_type.get()
                q['correctAnswer'] = self.q_correct.get()
                self._normalize_question_answer_fields(q, force_input_type=True)
                self._normalize_question_choice_ids(q)
                q['explanation'] = self.q_explanation.get(1.0, tk.END).strip()

            # Ensure every question follows website-compatible answer format.
            self.fix_escaped_newlines(show_message=False)
            self.fix_input_typing(show_message=False)
            self.fix_choice_ids(show_message=False)
            
            # Update chapter data
            if self.chapter_data:
                self.chapter_data["questions"] = self.questions
            
            # Save to file
            with open(self.chapter_file, 'w', encoding='utf-8') as f:
                json.dump(self.chapter_data, f, indent=2, ensure_ascii=False)
            
            # Count questions with images
            questions_with_images = sum(1 for q in self.questions if q.get('image'))
            print(f"DEBUG: Saved chapter with {len(self.questions)} questions ({questions_with_images} with images)")
            
            # Debug: Print first 3 questions to see what was saved
            for idx, q in enumerate(self.questions[:3]):
                print(f"  Q{idx}: id={q.get('id')}, image='{q.get('image', 'N/A')}'")
            
            messagebox.showinfo("Success", 
                f"Chapter saved successfully! ✓\n\n"
                f"Total questions: {len(self.questions)}\n"
                f"Questions with images: {questions_with_images}\n"
                f"File: {self.chapter_file.name}")
        except Exception as e:
            print(f"DEBUG: Error saving chapter: {e}")
            messagebox.showerror("Error", f"Failed to save chapter: {e}")

class ExamEditor:
    def __init__(self, root):
        self.root = root

        self.base_path = Path(__file__).parent.parent
        self.data_path = self.base_path / "data"
        self.config_path = self.base_path / "config"
        
        self.sections = []
        self.current_section = None
        self.current_section_idx = None
        self.chapters = []
        self.current_chapter_idx = None
        
        self.setup_ui()
        self.load_sections()
        
    def setup_ui(self):
        """Setup main UI with improved layout"""
        # Top toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        ttk.Button(toolbar, text="Save All", command=self.save_all,
                  width=15, bootstyle="primary").pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_all,
                  width=12, bootstyle="info-outline").pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(toolbar, text="Ready",
                                       foreground=COLORS["success"],
                                       style="Status.TLabel")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # Main container with PanedWindow
        paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.main_paned = paned

        # Left Panel - Sections
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        # Sections header
        sections_header = ttk.Frame(left_frame)
        sections_header.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(sections_header, text="Sections",
                 style="Header.TLabel").pack(side=tk.LEFT)

        ttk.Button(sections_header, text="+", command=self.add_section,
                  width=3, bootstyle="success-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(sections_header, text="Import", command=self.import_section,
              width=6, bootstyle="info-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(sections_header, text="Edit", command=self.edit_section,
                  width=4, bootstyle="warning-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(sections_header, text="Del", command=self.delete_section,
                  width=3, bootstyle="danger-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(sections_header, text="Dn", command=self.move_section_down,
              width=4, bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(sections_header, text="Up", command=self.move_section_up,
              width=4, bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=2)

        # Sections table
        sections_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL)

        self.sections_tree = ttk.Treeview(left_frame,
                                         columns=("Name", "ID", "Path"),
                                         show="headings",
                                         yscrollcommand=sections_scroll.set,
                                         selectmode="browse",
                                         height=15)

        sections_scroll.config(command=self.sections_tree.yview)

        self.sections_tree.heading("Name", text="Name")
        self.sections_tree.heading("ID", text="ID")
        self.sections_tree.heading("Path", text="Path")

        self.sections_tree.column("Name", width=125, minwidth=90, stretch=True)
        self.sections_tree.column("ID", width=70, minwidth=55, stretch=True)
        self.sections_tree.column("Path", width=105, minwidth=80, stretch=True)

        self.sections_tree.tag_configure("oddrow", background=COLORS["treeview_row_odd"])
        self.sections_tree.tag_configure("evenrow", background=COLORS["treeview_row_even"])

        self.sections_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sections_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.sections_tree.bind("<<TreeviewSelect>>", self.on_section_select)

        # Right Panel - Chapters
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        # Chapters header
        chapters_header = ttk.Frame(right_frame)
        chapters_header.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(chapters_header, text="Chapters",
                 style="Header.TLabel").pack(side=tk.LEFT)

        self.chapter_tools_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=COLORS["bg_card"],
            fg=COLORS["text_main"],
            activebackground=COLORS["primary"],
            activeforeground=COLORS["selection_fg"],
            relief=tk.FLAT,
            font=("Segoe UI", 9),
        )
        self.chapter_tools_menu.add_command(
            label="Fix Numbering (Selected)",
            command=lambda: self.apply_tools_to_selected_chapters("fix_numbering"),
        )
        self.chapter_tools_menu.add_command(
            label="Fix Escaped \\n (Selected)",
            command=lambda: self.apply_tools_to_selected_chapters("fix_escaped_newlines"),
        )
        self.chapter_tools_menu.add_command(
            label="Fix Input Typing (Selected)",
            command=lambda: self.apply_tools_to_selected_chapters("fix_input_typing"),
        )
        self.chapter_tools_menu.add_separator()
        self.chapter_tools_menu.add_command(
            label="Fix Chapter ID Numbering",
            command=self.fix_chapter_id_numbering,
        )
        self.chapter_tools_menu.add_separator()
        self.chapter_tools_menu.add_command(
            label="Delete Duplicates (Selected)",
            command=lambda: self.apply_tools_to_selected_chapters("delete_duplicates"),
        )
        self.chapter_tools_menu.add_command(
            label="Smart Duplicates (Selected)",
            command=lambda: self.apply_tools_to_selected_chapters("smart_duplicates"),
        )
        self.chapter_tools_menu.add_separator()
        self.chapter_tools_menu.add_command(
            label="Delete Selected Chapters",
            command=self.delete_chapter,
        )

        self.chapter_tools_btn = ttk.Button(
            chapters_header,
            text="Tools ▼",
            width=9,
            bootstyle="warning-outline",
            command=self.show_chapter_tools_menu,
        )
        self.chapter_tools_btn.pack(side=tk.RIGHT, padx=2)
        self.chapter_tools_btn.bind("<Enter>", self.show_chapter_tools_menu)

        ttk.Button(chapters_header, text="+", command=self.add_chapter,
                  width=3, bootstyle="success-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(chapters_header, text="Import", command=self.import_chapters,
              width=6, bootstyle="info-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(chapters_header, text="Del", command=self.delete_chapter,
                  width=3, bootstyle="danger-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(chapters_header, text="Dn", command=self.move_chapter_down,
              width=4, bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=2)
        ttk.Button(chapters_header, text="Up", command=self.move_chapter_up,
              width=4, bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=2)

        # Chapters table
        chapters_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL)

        self.chapters_tree = ttk.Treeview(right_frame,
                                         columns=("ID", "Name", "Questions", "File"),
                                         show="headings",
                                         yscrollcommand=chapters_scroll.set,
                                         selectmode="extended",
                                         height=10)

        chapters_scroll.config(command=self.chapters_tree.yview)

        self.chapters_tree.heading("ID", text="ID")
        self.chapters_tree.heading("Name", text="Chapter Name")
        self.chapters_tree.heading("Questions", text="Questions")
        self.chapters_tree.heading("File", text="File")

        self.chapters_tree.column("ID", width=50, minwidth=45, stretch=True)
        self.chapters_tree.column("Name", width=220, minwidth=150, stretch=True)
        self.chapters_tree.column("Questions", width=75, minwidth=70, stretch=True)
        self.chapters_tree.column("File", width=130, minwidth=100, stretch=True)

        # Keep enough room on the sections side so header controls stay visible.
        self.root.after(120, lambda: self.main_paned.sashpos(0, 420))

        self.chapters_tree.tag_configure("oddrow", background=COLORS["treeview_row_odd"])
        self.chapters_tree.tag_configure("evenrow", background=COLORS["treeview_row_even"])

        self.chapters_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chapters_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.chapters_tree.bind("<<TreeviewSelect>>", self.on_chapter_select)
        self.chapters_tree.bind("<Double-1>", self.on_chapter_double_click)

        # Chapter editor panel
        editor_frame = ttk.LabelFrame(right_frame, text="Edit Chapter")
        editor_frame.pack(fill=tk.X, pady=(10, 0))

        # ID
        ttk.Label(editor_frame, text="ID:", style="SubHeader.TLabel").grid(
            row=0, column=0, sticky=tk.W, pady=8)
        self.ch_id = ttk.Entry(editor_frame, width=15, bootstyle="info")
        self.ch_id.grid(row=0, column=1, sticky=tk.W, padx=10, pady=8)

        # Name
        ttk.Label(editor_frame, text="Name:", style="SubHeader.TLabel").grid(
            row=0, column=2, sticky=tk.W, pady=8, padx=(20, 0))
        self.ch_name = ttk.Entry(editor_frame, width=40, bootstyle="info")
        self.ch_name.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=10, pady=8)

        # Questions count
        ttk.Label(editor_frame, text="Questions:", style="SubHeader.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=8)
        self.ch_count = ttk.Entry(editor_frame, width=15, bootstyle="info")
        self.ch_count.grid(row=1, column=1, sticky=tk.W, padx=10, pady=8)

        # Update button
        self.update_chapter_btn = ttk.Button(editor_frame, text="Update Chapter",
                                            command=self.update_chapter,
                                            state="disabled",
                                            bootstyle="primary")
        self.update_chapter_btn.grid(row=1, column=3, sticky=tk.E, padx=10, pady=8)

        editor_frame.columnconfigure(3, weight=1)

    def update_status(self, message, color="green"):
        """Update status message"""
        color_map = {
            "green": COLORS["success"],
            "blue": COLORS["primary_light"],
            "orange": COLORS["warning"],
            "red": COLORS["danger"],
        }
        mapped = color_map.get(color, color)
        self.status_label.config(text=message, foreground=mapped)
        self.root.after(3000, lambda: self.status_label.config(
            text="Ready", foreground=COLORS["success"]))

    def _normalize_rel_path(self, path_text):
        """Normalize a config-relative path using forward slashes."""
        return str(path_text or "").strip().replace("\\", "/").strip("/")

    def _looks_like_icon_path(self, icon_value):
        """Return True when icon value looks like a file path or URL."""
        text = str(icon_value or "").strip()
        if not text:
            return False
        if re.match(r"^(https?://|\./|\.\./|/)", text, flags=re.IGNORECASE):
            return True
        if "/" in text or "\\" in text:
            return True
        if re.search(r"\.(png|jpg|jpeg|webp|gif|bmp|ico|svg)$", text, flags=re.IGNORECASE):
            return True
        return False

    def _default_section_icon_rel(self, section_id, section_path=None):
        """Return default section icon path (data/<section>/icon.png)."""
        section_id = str(section_id or "").strip()
        section_path = self._normalize_rel_path(section_path)
        if not section_path:
            section_path = f"data/{section_id}" if section_id else "data/section"
        return f"{section_path.rstrip('/')}/icon.png"

    def _build_section_path(self, section_root_text, section_id):
        """Build a normalized section data path from root/id inputs."""
        section_id = str(section_id or "").strip()
        root = str(section_root_text or "").strip().replace("\\", "/")
        root = root.rstrip("/")

        if not root:
            return f"data/{section_id}" if section_id else "data/section"

        if section_id and root.lower().endswith(f"/{section_id.lower()}"):
            return root
        if section_id and root.lower() == section_id.lower():
            return f"data/{section_id}"
        if root.lower() == "data" and section_id:
            return f"data/{section_id}"
        if section_id:
            return f"{root}/{section_id}"
        return root

    def _store_section_icon(self, source_path, section_path_rel, resize_if_large=True, max_size=128):
        """Store uploaded section icon in the section folder and return relative icon path."""
        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"Icon source not found: {src}")

        section_path_rel = self._normalize_rel_path(section_path_rel)
        section_abs = self.base_path / section_path_rel
        section_abs.mkdir(parents=True, exist_ok=True)

        max_size = max(16, int(max_size or 128))
        if Image is not None:
            dst = section_abs / "icon.png"
            with Image.open(src) as img:
                img = img.convert("RGBA")
                resized = False
                if resize_if_large and (img.width > max_size or img.height > max_size):
                    lanczos = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
                    img.thumbnail((max_size, max_size), lanczos)
                    resized = True
                img.save(dst, format="PNG")
            return f"{section_path_rel}/icon.png", resized

        # Pillow fallback: copy file as-is (cannot resize/convert formats).
        ext = src.suffix.lower() or ".png"
        dst_name = "icon.png" if ext == ".png" else f"icon{ext}"
        dst = section_abs / dst_name
        shutil.copy2(src, dst)
        return f"{section_path_rel}/{dst_name}", False

    def _download_icon_url_to_temp(self, icon_url):
        """Download icon URL to a temporary file and return its path."""
        raw = str(icon_url or "").strip()
        if not raw:
            raise ValueError("Icon URL is empty")
        if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
            raw = f"https://{raw}"

        req = urllib.request.Request(raw, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read()
            content_type = (response.headers.get("Content-Type") or "").lower()

        suffix = ".png"
        parsed = urllib.parse.urlparse(raw)
        url_ext = Path(parsed.path).suffix.lower()
        if url_ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ico"}:
            suffix = url_ext
        elif "jpeg" in content_type:
            suffix = ".jpg"
        elif "webp" in content_type:
            suffix = ".webp"
        elif "gif" in content_type:
            suffix = ".gif"
        elif "bmp" in content_type:
            suffix = ".bmp"
        elif "icon" in content_type:
            suffix = ".ico"

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.write(data)
        temp_file.flush()
        temp_file.close()
        return temp_file.name

    def _store_section_icon_from_url(self, icon_url, section_path_rel, resize_if_large=True, max_size=128):
        """Download icon from URL, then store it in the section folder."""
        temp_path = self._download_icon_url_to_temp(icon_url)
        try:
            return self._store_section_icon(
                temp_path,
                section_path_rel,
                resize_if_large=resize_if_large,
                max_size=max_size,
            )
        finally:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _open_icon_search(self, query_text):
        """Open a browser image search for icons."""
        query = urllib.parse.quote_plus(str(query_text or "section icon"))
        webbrowser.open(f"https://www.google.com/search?tbm=isch&q={query}")

    def _open_windows_emoji_picker(self, target_entry=None):
        """Open native Windows emoji picker (Win + .) focused on a target entry."""
        if target_entry is not None:
            try:
                target_entry.focus_force()
                target_entry.icursor(tk.END)
            except Exception:
                pass

        if os.name != "nt":
            messagebox.showinfo("Emoji Picker", "Windows emoji picker is available on Windows only.")
            return

        try:
            import ctypes

            user32 = ctypes.windll.user32
            VK_LWIN = 0x5B
            VK_OEM_PERIOD = 0xBE
            KEYEVENTF_KEYUP = 0x0002

            user32.keybd_event(VK_LWIN, 0, 0, 0)
            user32.keybd_event(VK_OEM_PERIOD, 0, 0, 0)
            user32.keybd_event(VK_OEM_PERIOD, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
        except Exception as e:
            messagebox.showerror("Emoji Picker", f"Could not open Windows emoji picker: {e}")

    def _set_icon_preview(self, preview_label, icon_rel=None, source_path=None, icon_url=None, max_preview=140):
        """Render icon preview from local file, icon path, or URL."""
        preview_label.configure(text="No icon preview", image="")
        preview_label._preview_image = None

        candidate_path = None
        temp_path = None
        try:
            if source_path:
                candidate_path = Path(source_path)
            elif icon_url:
                temp_path = self._download_icon_url_to_temp(icon_url)
                candidate_path = Path(temp_path)
            elif icon_rel:
                if not self._looks_like_icon_path(icon_rel):
                    preview_label.configure(text=str(icon_rel), image="", font=("Segoe UI Emoji", 34))
                    return
                preview_label.configure(font=("Segoe UI", 10))
                candidate_path = self.base_path / self._normalize_rel_path(icon_rel)

            if not candidate_path or not candidate_path.exists():
                if icon_rel:
                    preview_label.configure(text=f"No icon found\n{icon_rel}")
                return

            if Image is not None and ImageTk is not None:
                with Image.open(candidate_path) as img:
                    img = img.convert("RGBA")
                    lanczos = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
                    img.thumbnail((max_preview, max_preview), lanczos)
                    tk_img = ImageTk.PhotoImage(img)
                preview_label.configure(image=tk_img, text="")
                preview_label._preview_image = tk_img
                return

            tk_img = tk.PhotoImage(file=str(candidate_path))
            preview_label.configure(image=tk_img, text="")
            preview_label._preview_image = tk_img
        except Exception as e:
            preview_label.configure(text=f"Preview unavailable\n{Path(str(candidate_path or '')).name}")
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _ensure_section_icon_defaults(self):
        """Ensure every section has an icon path, defaulting to data/<section>/icon.png."""
        changed = False
        for section in self.sections:
            section_id = section.get("id", "")
            section_path = section.get("path", "")
            default_icon = self._default_section_icon_rel(section_id, section_path)
            icon_rel = self._normalize_rel_path(section.get("icon", ""))
            if not icon_rel:
                section["icon"] = default_icon
                changed = True
            else:
                normalized_icon = icon_rel
                if normalized_icon != section.get("icon", ""):
                    section["icon"] = normalized_icon
                    changed = True
        return changed
    
    def refresh_all(self):
        """Refresh all data and auto-configure engine"""
        self.load_sections()
        if self.current_section:
            self.load_chapters()
        
        # Auto-configure engine on refresh
        try:
            self.generate_js_config()
            self.update_status("✓ Refreshed & Configured", "green")
        except Exception as e:
            self.update_status("Refreshed (config failed)", "orange")
            print(f"Auto-config error: {e}")
    
    def load_sections(self):
        """Load sections from config"""
        try:
                config_file = self.config_path / "sections.json"
                self.sections = _load_json_file(config_file)
        except:
            self.sections = []

        if self._ensure_section_icon_defaults():
            self.save_sections()
        
        self.refresh_sections_tree()
    
    def refresh_sections_tree(self):
        """Refresh sections tree"""
        for item in self.sections_tree.get_children():
            self.sections_tree.delete(item)

        for idx, section in enumerate(self.sections):
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.sections_tree.insert("", tk.END, iid=str(idx), values=(
                section['name'],
                section['id'],
                section.get('path', '')
            ), tags=(tag,))
    
    def on_section_select(self, event):
        """Handle section selection"""
        selection = self.sections_tree.selection()
        if selection:
            self.current_section_idx = int(selection[0])
            self.current_section = self.sections[self.current_section_idx]['id']
            self.load_chapters()
            self.update_status(f"Selected: {self.sections[self.current_section_idx]['name']}", "blue")
    
    def load_chapters(self):
        """Load chapters for current section"""
        if not self.current_section:
            self.chapters = []
            self.refresh_chapters_tree()
            return
        
        section = next((s for s in self.sections if s['id'] == self.current_section), None)
        if not section:
            return
        
        try:
                ch_file = self.base_path / f"{section['path']}" / "chapters.json"
                self.chapters = _load_json_file(ch_file)
        except:
            self.chapters = []
        
        self.refresh_chapters_tree()
    
    def refresh_chapters_tree(self):
        """Refresh chapters tree"""
        for item in self.chapters_tree.get_children():
            self.chapters_tree.delete(item)

        for idx, chapter in enumerate(self.chapters):
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.chapters_tree.insert("", tk.END, iid=str(idx), values=(
                chapter.get('id', ''),
                chapter.get('name', ''),
                chapter.get('q', 0),
                chapter.get('file', '')
            ), tags=(tag,))

    def get_selected_chapter_indices(self):
        """Return selected chapter indices from the chapters tree."""
        indices = []
        for iid in self.chapters_tree.selection():
            try:
                idx = int(iid)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(self.chapters):
                indices.append(idx)
        return sorted(set(indices))

    def show_chapter_tools_menu(self, event=None):
        """Show chapter batch-tools menu below the tools button."""
        if not hasattr(self, "chapter_tools_btn"):
            return "break"
        x = self.chapter_tools_btn.winfo_rootx()
        y = self.chapter_tools_btn.winfo_rooty() + self.chapter_tools_btn.winfo_height()
        try:
            self.chapter_tools_menu.tk_popup(x, y)
        finally:
            self.chapter_tools_menu.after_idle(self.chapter_tools_menu.grab_release)
        return "break"
    
    def on_chapter_select(self, event):
        """Handle chapter selection"""
        selected_indices = self.get_selected_chapter_indices()
        if selected_indices:
            self.current_chapter_idx = selected_indices[0]
            chapter = self.chapters[self.current_chapter_idx]

            self.ch_id.delete(0, tk.END)
            self.ch_name.delete(0, tk.END)
            self.ch_count.delete(0, tk.END)

            if len(selected_indices) == 1:
                self.ch_id.insert(0, chapter.get('id', ''))
                self.ch_name.insert(0, chapter.get('name', ''))
                self.ch_count.insert(0, str(chapter.get('q', 0)))
                self.update_chapter_btn.config(state="normal")
            else:
                total_questions = sum(int(self.chapters[i].get('q', 0) or 0) for i in selected_indices)
                self.ch_id.insert(0, f"{len(selected_indices)} selected")
                self.ch_name.insert(0, "Use Tools menu to apply batch actions")
                self.ch_count.insert(0, str(total_questions))
                self.update_chapter_btn.config(state="disabled")
        else:
            self.current_chapter_idx = None
            self.update_chapter_btn.config(state="disabled")

    def _normalize_for_compare(self, value):
        """Normalize text for duplicate comparisons."""
        return re.sub(r"\s+", " ", str(value or "")).strip().lower()

    def _question_signature(self, question):
        """Build stable signature from question text and choices."""
        title = self._normalize_for_compare(question.get("text", ""))
        normalized_choices = []
        for choice in question.get("choices", []) or []:
            cval = self._normalize_for_compare(choice.get("value", ""))
            ctext = self._normalize_for_compare(choice.get("text", ""))
            normalized_choices.append((cval, ctext))
        normalized_choices.sort()
        return (title, tuple(normalized_choices))

    def _question_text_similarity(self, left, right):
        """Compute fuzzy similarity between two question titles."""
        if not left or not right:
            return 0.0
        seq = SequenceMatcher(None, left, right).ratio()
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        union = left_tokens | right_tokens
        jaccard = (len(left_tokens & right_tokens) / len(union)) if union else 0.0
        return max(seq, jaccard)

    def _question_choices_similarity(self, q1, q2):
        """Compute fuzzy similarity between two questions' choices."""
        c1 = [self._normalize_for_compare(c.get("text", "")) for c in q1.get("choices", []) or []]
        c2 = [self._normalize_for_compare(c.get("text", "")) for c in q2.get("choices", []) or []]
        c1 = [c for c in c1 if c]
        c2 = [c for c in c2 if c]
        if not c1 or not c2:
            return 0.0

        s1 = " | ".join(sorted(c1))
        s2 = " | ".join(sorted(c2))
        seq = SequenceMatcher(None, s1, s2).ratio()
        t1 = set(c1)
        t2 = set(c2)
        union = t1 | t2
        overlap = (len(t1 & t2) / len(union)) if union else 0.0
        return max(seq, overlap)

    def _normalize_answer_letters(self, value, question=None):
        """Normalize answer keys to compact uppercase form (e.g., A, B, C -> ABC)."""
        raw = str(value or "").upper()
        allowed = []
        if isinstance(question, dict):
            for choice in question.get("choices", []) or []:
                key = str(choice.get("value", "")).strip().upper()
                if len(key) == 1:
                    allowed.append(key)

        allowed_set = set(allowed)
        letters = []
        for ch in re.findall(r"[A-Z0-9]", raw):
            if allowed_set and ch not in allowed_set:
                continue
            if ch not in letters:
                letters.append(ch)
        return "".join(letters)

    def _normalize_question_answer_fields(self, question, force_input_type=False):
        """Normalize a question's correctAnswer and optionally enforce matching inputType."""
        if not isinstance(question, dict):
            return False, False

        old_answer = str(question.get("correctAnswer", ""))
        old_input_type = str(question.get("inputType", "radio") or "radio").lower()
        normalized_answer = self._normalize_answer_letters(old_answer, question)
        question["correctAnswer"] = normalized_answer

        type_changed = False
        if force_input_type:
            new_type = "checkbox" if len(normalized_answer) > 1 else "radio"
            if old_input_type != new_type:
                type_changed = True
            question["inputType"] = new_type
        elif old_input_type not in {"radio", "checkbox"}:
            question["inputType"] = "radio"
            type_changed = True

        return normalized_answer != old_answer, type_changed

    def _load_chapter_payload(self, section, chapter):
        """Load chapter JSON payload and return (path, payload, chapter_data, questions)."""
        fpath = self.base_path / section.get('path', '') / chapter.get('file', '')
        if not fpath.exists():
            raise FileNotFoundError(f"Chapter file not found: {fpath}")

        payload = _load_json_file(fpath)

        if isinstance(payload, list):
            if payload and isinstance(payload[0], dict):
                chapter_data = payload[0]
            else:
                chapter_data = {"questions": []}
                payload = [chapter_data]
        elif isinstance(payload, dict):
            chapter_data = payload
        else:
            chapter_data = {"questions": []}
            payload = chapter_data

        questions = chapter_data.get("questions", [])
        if not isinstance(questions, list):
            questions = []
            chapter_data["questions"] = questions

        return fpath, payload, chapter_data, questions

    def _save_chapter_payload(self, fpath, payload):
        """Persist chapter JSON payload."""
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def apply_tools_to_selected_chapters(self, tool_name):
        """Apply a chapter tool to all selected chapters."""
        if not self.current_section:
            messagebox.showwarning("Warning", "Select a section first")
            return

        selected_indices = self.get_selected_chapter_indices()
        if not selected_indices and self.current_chapter_idx is not None:
            selected_indices = [self.current_chapter_idx]
        if not selected_indices:
            messagebox.showwarning("Warning", "Select one or more chapters first")
            return

        section = next((s for s in self.sections if s['id'] == self.current_section), None)
        if not section:
            messagebox.showerror("Error", "Selected section not found")
            return

        if tool_name == "delete_chapters":
            self.delete_chapter()
            return

        stats = {
            "chapters": 0,
            "questions_removed": 0,
            "numbering_fixed": 0,
            "newline_fixed": 0,
            "typing_fixed": 0,
            "type_fixed": 0,
        }

        errors = []
        for idx in selected_indices:
            chapter = self.chapters[idx]
            try:
                fpath, payload, chapter_data, questions = self._load_chapter_payload(section, chapter)
                changed = False

                if tool_name == "fix_numbering":
                    renumbered = 0
                    for q_idx, question in enumerate(questions, start=1):
                        target = str(q_idx)
                        if str(question.get("number", "")) != target:
                            question["number"] = target
                            renumbered += 1
                    changed = renumbered > 0
                    stats["numbering_fixed"] += renumbered

                elif tool_name == "fix_escaped_newlines":
                    replacements = 0
                    for question in questions:
                        replacements += _fix_escaped_newlines_in_question(question)
                    changed = replacements > 0
                    stats["newline_fixed"] += replacements

                elif tool_name == "fix_input_typing":
                    answer_changes = 0
                    type_changes = 0
                    for question in questions:
                        answer_changed, type_changed = self._normalize_question_answer_fields(
                            question,
                            force_input_type=True,
                        )
                        if answer_changed:
                            answer_changes += 1
                        if type_changed:
                            type_changes += 1
                    changed = (answer_changes + type_changes) > 0
                    stats["typing_fixed"] += answer_changes
                    stats["type_fixed"] += type_changes

                elif tool_name == "delete_duplicates":
                    first_seen = {}
                    keep = []
                    removed = 0
                    for question in questions:
                        sig = self._question_signature(question)
                        if sig in first_seen:
                            removed += 1
                            continue
                        first_seen[sig] = True
                        keep.append(question)
                    if removed:
                        questions[:] = keep
                        for q_idx, question in enumerate(questions, start=1):
                            question["number"] = str(q_idx)
                        changed = True
                    stats["questions_removed"] += removed

                elif tool_name == "smart_duplicates":
                    similar_delete_indexes = set()
                    for i in range(len(questions)):
                        for j in range(i + 1, len(questions)):
                            if j in similar_delete_indexes:
                                continue
                            q1 = questions[i]
                            q2 = questions[j]

                            t1 = self._normalize_for_compare(q1.get("text", ""))
                            t2 = self._normalize_for_compare(q2.get("text", ""))
                            if not t1 or not t2:
                                continue

                            title_score = self._question_text_similarity(t1, t2)
                            choices_score = self._question_choices_similarity(q1, q2)
                            score = (0.75 * title_score) + (0.25 * choices_score)

                            short_text = min(len(t1), len(t2)) < 12
                            if short_text:
                                is_similar = score >= 0.92 and title_score >= 0.88
                            else:
                                is_similar = score >= 0.84 and title_score >= 0.76

                            if is_similar:
                                similar_delete_indexes.add(j)

                    if similar_delete_indexes:
                        questions[:] = [q for q_idx, q in enumerate(questions) if q_idx not in similar_delete_indexes]
                        for q_idx, question in enumerate(questions, start=1):
                            question["number"] = str(q_idx)
                        changed = True
                    stats["questions_removed"] += len(similar_delete_indexes)

                chapter_data["questions"] = questions
                chapter["q"] = len(questions)
                if changed:
                    self._save_chapter_payload(fpath, payload)
                stats["chapters"] += 1
            except Exception as e:
                errors.append(f"{chapter.get('name', chapter.get('id', 'Unknown'))}: {e}")

        self.refresh_chapters_tree()
        self.save_chapter()

        if errors:
            messagebox.showwarning(
                "Completed With Errors",
                "Some chapters failed:\n\n" + "\n".join(errors[:10])
            )

        if tool_name == "fix_numbering":
            message = (
                f"Processed {stats['chapters']} chapter(s).\n"
                f"Renumbered {stats['numbering_fixed']} question(s)."
            )
        elif tool_name == "fix_escaped_newlines":
            message = (
                f"Processed {stats['chapters']} chapter(s).\n"
                f"Replaced {stats['newline_fixed']} escaped newline sequence(s)."
            )
        elif tool_name == "fix_input_typing":
            message = (
                f"Processed {stats['chapters']} chapter(s).\n"
                f"Normalized answers in {stats['typing_fixed']} question(s).\n"
                f"Adjusted input type in {stats['type_fixed']} question(s)."
            )
        elif tool_name == "delete_duplicates":
            message = (
                f"Processed {stats['chapters']} chapter(s).\n"
                f"Removed {stats['questions_removed']} duplicate question(s)."
            )
        elif tool_name == "smart_duplicates":
            message = (
                f"Processed {stats['chapters']} chapter(s).\n"
                f"Removed {stats['questions_removed']} likely-duplicate question(s)."
            )
        else:
            message = f"Processed {stats['chapters']} chapter(s)."

        messagebox.showinfo("Batch Tools Complete", message)
    
    def on_chapter_double_click(self, event):
        """Open advanced chapter editor when double-clicking a chapter"""
        selection = self.chapters_tree.selection()
        if not selection:
            return
        
        if not self.current_section:
            messagebox.showwarning("Warning", "Select a section first")
            return
        
        self.current_chapter_idx = int(selection[0])
        chapter = self.chapters[self.current_chapter_idx]
        
        # Get the chapter file path
        section = next((s for s in self.sections if s['id'] == self.current_section), None)
        if not section:
            messagebox.showerror("Error", "Section not found")
            return
        
        chapter_file_path = self.base_path / section['path'] / chapter.get('file', '')
        
        if not chapter_file_path.exists():
            messagebox.showerror("Error", f"Chapter file not found: {chapter_file_path}")
            return
        
        # Open advanced editor
        AdvancedChapterEditor(self.root, chapter_file_path, section['path'], self.base_path)
    
    def update_chapter(self):
        """Update the selected chapter"""
        if self.current_chapter_idx is None:
            messagebox.showwarning("Warning", "No chapter selected")
            return
        
        chapter = self.chapters[self.current_chapter_idx]
        chapter['id'] = self.ch_id.get()
        chapter['name'] = self.ch_name.get()
        try:
            chapter['q'] = int(self.ch_count.get())
        except:
            chapter['q'] = 0
        
        self.refresh_chapters_tree()
        self.chapters_tree.selection_set(str(self.current_chapter_idx))
        
        # Sync changes to the actual file
        try:
            self._sync_chapter_file(chapter)
            self.update_status("Chapter updated and file synced", "orange")
        except Exception as e:
            messagebox.showerror("Sync Error", f"Failed to sync to file: {e}")
            self.update_status("Chapter updated in list (Sync Failed)", "red")

    def fix_chapter_id_numbering(self, show_message=True):
        """Renumber chapter IDs sequentially based on current chapter order."""
        if not self.current_section:
            if show_message:
                messagebox.showwarning("Warning", "Select a section first")
            return 0

        if not self.chapters:
            if show_message:
                messagebox.showinfo("No Chapters", "There are no chapters to renumber.")
            return 0

        section = next((s for s in self.sections if s['id'] == self.current_section), None)
        changed = 0
        synced_files = 0
        errors = []

        for idx, chapter in enumerate(self.chapters, start=1):
            new_id = str(idx)
            old_id = str(chapter.get("id", ""))
            if old_id != new_id:
                chapter["id"] = new_id
                changed += 1

            if not section:
                continue

            try:
                fpath, payload, chapter_data, _ = self._load_chapter_payload(section, chapter)
                params = chapter_data.get("params")
                if not isinstance(params, dict):
                    params = {}
                    chapter_data["params"] = params

                file_changed = False
                if str(params.get("chapter", "")) != new_id:
                    params["chapter"] = new_id
                    file_changed = True

                if file_changed:
                    self._save_chapter_payload(fpath, payload)
                    synced_files += 1
            except Exception as e:
                errors.append(f"{chapter.get('name', chapter.get('file', 'Unknown'))}: {e}")

        self.refresh_chapters_tree()
        if self.current_chapter_idx is not None and self.chapters:
            keep_idx = max(0, min(self.current_chapter_idx, len(self.chapters) - 1))
            self.current_chapter_idx = keep_idx
            self.chapters_tree.selection_set(str(keep_idx))

        self.save_chapter()

        if errors:
            messagebox.showwarning(
                "Renumbered With Errors",
                "Some chapter files could not be synced:\n\n" + "\n".join(errors[:10])
            )

        if show_message:
            if changed:
                messagebox.showinfo(
                    "Chapter IDs Fixed",
                    f"Renumbered {changed} chapter ID(s).\n"
                    f"Synced params.chapter in {synced_files} chapter file(s)."
                )
            else:
                messagebox.showinfo(
                    "Already Correct",
                    "Chapter IDs are already sequential."
                )

        return changed

    def _sync_chapter_file(self, chapter_data):
        """Sync chapter metadata to the actual JSON file and rename if ID changed"""
        section = next((s for s in self.sections if s['id'] == self.current_section), None)
        if not section:
            return

        old_file_name = chapter_data.get('file', '')
        if not old_file_name:
            return

        section_path = self.base_path / section['path']
        old_file_path = section_path / old_file_name

        if not old_file_path.exists():
            return

        # 1. Load content
        content = _load_json_file(old_file_path)

        data = content[0] if isinstance(content, list) and content else content
        if isinstance(content, list) and not content:
            data = {}
            content = [data]

        # 2. Update Content
        new_id = chapter_data['id']
        new_name = chapter_data['name']
        
        # Update params.chapter
        if 'params' not in data:
            data['params'] = {}
        data['params']['chapter'] = new_id
        
        # Update title - preserve format if possible or just set it
        # Try to construct "Chapter {ID} {Name}" if it looks like that pattern was used
        if data.get('title', '').startswith('Chapter'):
             data['title'] = f"Chapter {new_id} {new_name}"
        else:
             data['title'] = new_name

        # 3. Determine new filename
        # If the file follows the pattern chapterN.json, rename it to match new ID
        new_file_name = old_file_name
        if re.match(r'chapter\d+\.json', old_file_name):
            new_file_name = f"chapter{new_id}.json"
        
        # 4. Save file
        # If renaming, we write to new path and remove old one (or git mv equivalent)
        new_file_path = section_path / new_file_name
        
        # If target exists and it's not the same file, warn? 
        # For now, just overwrite if it's a rename
        
        if new_file_name != old_file_name:
            # Rename logic
            if new_file_path.exists():
                 # basic collision avoidance
                 pass 
            
            with open(new_file_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            
            try:
                old_file_path.unlink()
            except:
                pass
            
            # Update chapter data with new filename
            chapter_data['file'] = new_file_name
        else:
            # Just save content
            with open(old_file_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
    
    def add_section(self):
        """Add new section"""
        dialog = tk.Toplevel(self.root)
        _style_dialog(dialog, "Add New Section", "620x560")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Section ID:", style="SubHeader.TLabel").grid(
            row=0, column=0, sticky=tk.W, pady=10)
        sec_id = ttk.Entry(frame, width=30, bootstyle="info")
        sec_id.grid(row=0, column=1, pady=10, padx=10)
        sec_id.focus()

        ttk.Label(frame, text="Section Name:", style="SubHeader.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=10)
        sec_name = ttk.Entry(frame, width=30, bootstyle="info")
        sec_name.grid(row=1, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Data Path:", style="SubHeader.TLabel").grid(
            row=2, column=0, sticky=tk.W, pady=10)
        sec_path = ttk.Entry(frame, width=30, bootstyle="info")
        sec_path.insert(0, "data/")
        sec_path.grid(row=2, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Description:", style="SubHeader.TLabel").grid(
            row=3, column=0, sticky=tk.W, pady=10)
        sec_desc = ttk.Entry(frame, width=30, bootstyle="info")
        sec_desc.grid(row=3, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Icon Path:", style="SubHeader.TLabel").grid(
            row=4, column=0, sticky=tk.W, pady=10)
        icon_var = tk.StringVar(value="data/section/icon.png")
        icon_entry = ttk.Entry(frame, width=30, bootstyle="info", textvariable=icon_var)
        icon_entry.grid(row=4, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Icon URL:", style="SubHeader.TLabel").grid(
            row=5, column=0, sticky=tk.W, pady=10)
        icon_url_var = tk.StringVar(value="")
        ttk.Entry(frame, width=30, bootstyle="info", textvariable=icon_url_var).grid(row=5, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Icon Emoji:", style="SubHeader.TLabel").grid(
            row=6, column=0, sticky=tk.W, pady=10)
        icon_emoji_var = tk.StringVar(value="")
        emoji_entry = ttk.Entry(frame, width=30, bootstyle="info", textvariable=icon_emoji_var)
        emoji_entry.grid(row=6, column=1, pady=10, padx=10)

        resize_icon_var = tk.BooleanVar(value=False)
        resize_max_var = tk.StringVar(value="768")
        icon_upload_source = {"path": ""}

        icon_controls = ttk.Frame(frame)
        icon_controls.grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))

        preview_frame = ttk.Frame(frame)
        preview_frame.grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        ttk.Label(preview_frame, text="Icon Preview:", style="SubHeader.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        preview_label = ttk.Label(preview_frame, text="No icon preview", width=28, style="Muted.TLabel")
        preview_label.pack(side=tk.LEFT)

        def choose_icon_file():
            file_path = filedialog.askopenfilename(
                title="Select Section Icon",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("All Files", "*.*")],
            )
            if not file_path:
                return
            icon_upload_source["path"] = file_path
            self._set_icon_preview(preview_label, source_path=file_path)
            self.update_status(f"Icon selected: {Path(file_path).name}", "blue")

        def preview_icon_from_url():
            url = icon_url_var.get().strip()
            if not url:
                messagebox.showwarning("Icon URL", "Enter an icon URL first")
                return
            self._set_icon_preview(preview_label, icon_url=url)

        def search_icons_web():
            q = f"{sec_name.get().strip() or sec_id.get().strip() or 'section'} icon png"
            self._open_icon_search(q)

        def open_emoji_picker():
            self._open_windows_emoji_picker(emoji_entry)

        def sync_emoji_to_icon(*_):
            emoji = icon_emoji_var.get().strip()
            if not emoji:
                return
            icon_var.set(emoji)
            self._set_icon_preview(preview_label, icon_rel=emoji)

        def preview_from_icon_path(*_):
            if icon_upload_source["path"]:
                return
            icon_rel = icon_var.get().strip()
            self._set_icon_preview(preview_label, icon_rel=icon_rel)

        ttk.Button(icon_controls, text="Upload Icon", command=choose_icon_file,
                   width=14, bootstyle="info-outline").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(icon_controls, text="Preview URL", command=preview_icon_from_url,
                   width=12, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(icon_controls, text="Search Icons", command=search_icons_web,
                   width=12, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(icon_controls, text="Emoji Picker", command=open_emoji_picker,
                   width=12, bootstyle="warning-outline").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(icon_controls,
                        text="Resize if bigger",
                        variable=resize_icon_var,
                        bootstyle="info-round-toggle").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(icon_controls, text="Max px:", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Entry(icon_controls, width=6, textvariable=resize_max_var, bootstyle="info").pack(side=tk.LEFT, padx=(4, 0))

        def refresh_default_icon(*_):
            section_path_rel = self._build_section_path(sec_path.get(), sec_id.get())
            icon_var.set(self._default_section_icon_rel(sec_id.get(), section_path_rel))

        sec_id.bind("<KeyRelease>", refresh_default_icon)
        sec_path.bind("<KeyRelease>", refresh_default_icon)
        icon_var.trace_add("write", preview_from_icon_path)
        icon_emoji_var.trace_add("write", sync_emoji_to_icon)
        refresh_default_icon()

        def save():
            if not sec_id.get() or not sec_name.get():
                messagebox.showerror("Error", "ID and Name are required")
                return

            section_path_rel = self._build_section_path(sec_path.get(), sec_id.get())
            icon_rel = self._normalize_rel_path(icon_var.get())
            if not icon_rel:
                icon_rel = self._default_section_icon_rel(sec_id.get(), section_path_rel)

            new_section = {
                "id": sec_id.get(),
                "name": sec_name.get(),
                "path": section_path_rel,
                "description": sec_desc.get(),
                "icon": icon_rel,
            }

            # Create directory and init chapters.json
            try:
                full_path = self.base_path / new_section['path']
                full_path.mkdir(parents=True, exist_ok=True)
                ch_file = full_path / "chapters.json"
                if not ch_file.exists():
                    with open(ch_file, 'w') as f:
                        json.dump([], f)

                if icon_upload_source["path"]:
                    max_px = int(str(resize_max_var.get() or "768").strip() or "768")
                    saved_icon_rel, resized = self._store_section_icon(
                        icon_upload_source["path"],
                        new_section["path"],
                        resize_if_large=resize_icon_var.get(),
                        max_size=max_px,
                    )
                    new_section["icon"] = saved_icon_rel
                    if Image is None and resize_icon_var.get():
                        messagebox.showwarning(
                            "Resize Unavailable",
                            "Pillow is not installed, so icon resize was skipped.\n"
                            "Install with: pip install pillow"
                        )
                elif icon_url_var.get().strip():
                    max_px = int(str(resize_max_var.get() or "768").strip() or "768")
                    saved_icon_rel, resized = self._store_section_icon_from_url(
                        icon_url_var.get().strip(),
                        new_section["path"],
                        resize_if_large=resize_icon_var.get(),
                        max_size=max_px,
                    )
                    new_section["icon"] = saved_icon_rel
                elif icon_emoji_var.get().strip():
                    new_section["icon"] = icon_emoji_var.get().strip()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create directory: {e}")
                return

            self.sections.append(new_section)
            self.save_sections()
            self.load_sections()
            self.update_status(f"Added section: {sec_id.get()}", "green")
            dialog.destroy()

        ttk.Button(frame, text="Create Section", command=save,
                  width=20, bootstyle="success").grid(row=9, column=0, columnspan=2, pady=20)

        dialog.bind('<Return>', lambda e: save())
    
    def delete_section(self):
        """Delete selected section"""
        if self.current_section_idx is None:
            messagebox.showwarning("Warning", "Select a section first")
            return

        section = self.sections[self.current_section_idx]
        dlg = tk.Toplevel(self.root)
        _style_dialog(dlg, "Delete Section", "480x180")
        dlg.transient(self.root)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=12, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Delete section '{section['name']}'?", style="Header.TLabel").pack(anchor=tk.W, pady=(0,8))
        ttk.Label(frame, text="This will remove the section from the config.").pack(anchor=tk.W)

        del_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Also delete section files from disk (permanent)", variable=del_var, bootstyle="warning").pack(anchor=tk.W, pady=8)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10,0))

        def do_delete():
            if del_var.get():
                try:
                    full_path = self.base_path / section.get('path', '')
                    if full_path.exists():
                        shutil.rmtree(full_path)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete section files: {e}")
                    return

            try:
                del self.sections[self.current_section_idx]
            except Exception:
                pass
            self.current_section = None
            self.current_section_idx = None
            self.save_sections()
            self.load_sections()
            self.chapters = []
            self.refresh_chapters_tree()
            self.update_status("Section deleted", "orange")
            dlg.destroy()

        def cancel():
            dlg.destroy()

        ttk.Button(btn_frame, text="Delete", command=do_delete, width=12, bootstyle="danger").pack(side=tk.RIGHT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=cancel, width=12, bootstyle="secondary-outline").pack(side=tk.RIGHT)
    
    def edit_section(self):
        """Edit the selected section"""
        if self.current_section_idx is None:
            messagebox.showwarning("Warning", "Select a section first")
            return

        section = self.sections[self.current_section_idx]

        dialog = tk.Toplevel(self.root)
        _style_dialog(dialog, "Edit Section", "620x560")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Section ID:", style="SubHeader.TLabel").grid(
            row=0, column=0, sticky=tk.W, pady=10)
        sec_id = ttk.Entry(frame, width=30, bootstyle="info")
        sec_id.insert(0, section.get('id', ''))
        sec_id.grid(row=0, column=1, pady=10, padx=10)
        sec_id.focus()

        ttk.Label(frame, text="Section Name:", style="SubHeader.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=10)
        sec_name = ttk.Entry(frame, width=30, bootstyle="info")
        sec_name.insert(0, section.get('name', ''))
        sec_name.grid(row=1, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Data Path:", style="SubHeader.TLabel").grid(
            row=2, column=0, sticky=tk.W, pady=10)
        sec_path = ttk.Entry(frame, width=30, bootstyle="info")
        sec_path.insert(0, section.get('path', ''))
        sec_path.grid(row=2, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Description:", style="SubHeader.TLabel").grid(
            row=3, column=0, sticky=tk.W, pady=10)
        sec_desc = ttk.Entry(frame, width=30, bootstyle="info")
        sec_desc.insert(0, section.get('description', ''))
        sec_desc.grid(row=3, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Icon Path:", style="SubHeader.TLabel").grid(
            row=4, column=0, sticky=tk.W, pady=10)
        icon_var = tk.StringVar(value=section.get('icon', self._default_section_icon_rel(section.get('id', ''), section.get('path', ''))))
        ttk.Entry(frame, width=30, bootstyle="info", textvariable=icon_var).grid(row=4, column=1, pady=10, padx=10)

        ttk.Label(frame, text="Icon URL:", style="SubHeader.TLabel").grid(
            row=5, column=0, sticky=tk.W, pady=10)
        icon_url_var = tk.StringVar(value="")
        ttk.Entry(frame, width=30, bootstyle="info", textvariable=icon_url_var).grid(row=5, column=1, pady=10, padx=10)

        default_icon_val = section.get('icon', self._default_section_icon_rel(section.get('id', ''), section.get('path', '')))
        current_icon_is_path = self._looks_like_icon_path(default_icon_val)

        ttk.Label(frame, text="Icon Emoji:", style="SubHeader.TLabel").grid(
            row=6, column=0, sticky=tk.W, pady=10)
        icon_emoji_var = tk.StringVar(value="" if current_icon_is_path else str(default_icon_val))
        emoji_entry = ttk.Entry(frame, width=30, bootstyle="info", textvariable=icon_emoji_var)
        emoji_entry.grid(row=6, column=1, pady=10, padx=10)

        resize_icon_var = tk.BooleanVar(value=False)
        resize_max_var = tk.StringVar(value="768")
        icon_upload_source = {"path": ""}

        icon_controls = ttk.Frame(frame)
        icon_controls.grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))

        preview_frame = ttk.Frame(frame)
        preview_frame.grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        ttk.Label(preview_frame, text="Icon Preview:", style="SubHeader.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        preview_label = ttk.Label(preview_frame, text="No icon preview", width=28, style="Muted.TLabel")
        preview_label.pack(side=tk.LEFT)

        def choose_icon_file():
            file_path = filedialog.askopenfilename(
                title="Select Section Icon",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("All Files", "*.*")],
            )
            if not file_path:
                return
            icon_upload_source["path"] = file_path
            self._set_icon_preview(preview_label, source_path=file_path)
            self.update_status(f"Icon selected: {Path(file_path).name}", "blue")

        def preview_icon_from_url():
            url = icon_url_var.get().strip()
            if not url:
                messagebox.showwarning("Icon URL", "Enter an icon URL first")
                return
            self._set_icon_preview(preview_label, icon_url=url)

        def search_icons_web():
            q = f"{sec_name.get().strip() or sec_id.get().strip() or 'section'} icon png"
            self._open_icon_search(q)

        def open_emoji_picker():
            self._open_windows_emoji_picker(emoji_entry)

        def sync_emoji_to_icon(*_):
            emoji = icon_emoji_var.get().strip()
            if not emoji:
                return
            icon_var.set(emoji)
            self._set_icon_preview(preview_label, icon_rel=emoji)

        def preview_from_icon_path(*_):
            if icon_upload_source["path"]:
                return
            self._set_icon_preview(preview_label, icon_rel=icon_var.get().strip())

        ttk.Button(icon_controls, text="Upload Icon", command=choose_icon_file,
                   width=14, bootstyle="info-outline").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(icon_controls, text="Preview URL", command=preview_icon_from_url,
                   width=12, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(icon_controls, text="Search Icons", command=search_icons_web,
                   width=12, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(icon_controls, text="Emoji Picker", command=open_emoji_picker,
                   width=12, bootstyle="warning-outline").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(icon_controls,
                        text="Resize if bigger",
                        variable=resize_icon_var,
                        bootstyle="info-round-toggle").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(icon_controls, text="Max px:", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Entry(icon_controls, width=6, textvariable=resize_max_var, bootstyle="info").pack(side=tk.LEFT, padx=(4, 0))
        icon_var.trace_add("write", preview_from_icon_path)
        icon_emoji_var.trace_add("write", sync_emoji_to_icon)
        self._set_icon_preview(preview_label, icon_rel=icon_var.get().strip())

        def save():
            if not sec_id.get() or not sec_name.get():
                messagebox.showerror("Error", "ID and Name are required")
                return

            section_path_rel = self._normalize_rel_path(sec_path.get())
            if not section_path_rel:
                section_path_rel = self._build_section_path("data", sec_id.get())

            section['id'] = sec_id.get()
            section['name'] = sec_name.get()
            section['path'] = section_path_rel
            section['description'] = sec_desc.get()
            section['icon'] = self._normalize_rel_path(icon_var.get()) or self._default_section_icon_rel(section['id'], section['path'])

            if icon_upload_source["path"]:
                try:
                    max_px = int(str(resize_max_var.get() or "768").strip() or "768")
                    saved_icon_rel, resized = self._store_section_icon(
                        icon_upload_source["path"],
                        section['path'],
                        resize_if_large=resize_icon_var.get(),
                        max_size=max_px,
                    )
                    section['icon'] = saved_icon_rel
                    if Image is None and resize_icon_var.get():
                        messagebox.showwarning(
                            "Resize Unavailable",
                            "Pillow is not installed, so icon resize was skipped.\n"
                            "Install with: pip install pillow"
                        )
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save icon: {e}")
                    return
            elif icon_url_var.get().strip():
                try:
                    max_px = int(str(resize_max_var.get() or "768").strip() or "768")
                    saved_icon_rel, resized = self._store_section_icon_from_url(
                        icon_url_var.get().strip(),
                        section['path'],
                        resize_if_large=resize_icon_var.get(),
                        max_size=max_px,
                    )
                    section['icon'] = saved_icon_rel
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to download icon URL: {e}")
                    return
            elif icon_emoji_var.get().strip():
                section['icon'] = icon_emoji_var.get().strip()

            self.current_section = section['id']
            self.refresh_sections_tree()
            self.sections_tree.selection_set(str(self.current_section_idx))
            self.update_status(f"Section updated: {section['name']}", "orange")
            dialog.destroy()

        ttk.Button(frame, text="Save Changes", command=save,
                  width=20, bootstyle="success").grid(row=9, column=0, columnspan=2, pady=20)

        dialog.bind('<Return>', lambda e: save())

    def move_section_up(self):
        """Move the selected section up in the list"""
        if self.current_section_idx is None:
            messagebox.showwarning("Warning", "Select a section first")
            return

        idx = self.current_section_idx
        if idx <= 0:
            return

        self.sections[idx], self.sections[idx - 1] = self.sections[idx - 1], self.sections[idx]
        self.current_section_idx = idx - 1
        self.current_section = self.sections[self.current_section_idx].get('id')

        self.refresh_sections_tree()
        self.sections_tree.selection_set(str(self.current_section_idx))
        self.sections_tree.focus(str(self.current_section_idx))
        self.sections_tree.see(str(self.current_section_idx))
        self.load_chapters()
        self.update_status("Section moved up (click Save All)", "orange")

    def move_section_down(self):
        """Move the selected section down in the list"""
        if self.current_section_idx is None:
            messagebox.showwarning("Warning", "Select a section first")
            return

        idx = self.current_section_idx
        if idx >= len(self.sections) - 1:
            return

        self.sections[idx], self.sections[idx + 1] = self.sections[idx + 1], self.sections[idx]
        self.current_section_idx = idx + 1
        self.current_section = self.sections[self.current_section_idx].get('id')

        self.refresh_sections_tree()
        self.sections_tree.selection_set(str(self.current_section_idx))
        self.sections_tree.focus(str(self.current_section_idx))
        self.sections_tree.see(str(self.current_section_idx))
        self.load_chapters()
        self.update_status("Section moved down (click Save All)", "orange")

    def move_chapter_up(self):
        """Move the selected chapter up in the list"""
        selected_indices = self.get_selected_chapter_indices()
        if len(selected_indices) > 1:
            messagebox.showwarning("Warning", "Select a single chapter to move.")
            return
        if self.current_chapter_idx is None:
            messagebox.showwarning("Warning", "Select a chapter first")
            return

        idx = self.current_chapter_idx
        if idx <= 0:
            return

        self.chapters[idx], self.chapters[idx - 1] = self.chapters[idx - 1], self.chapters[idx]
        self.current_chapter_idx = idx - 1
        self.refresh_chapters_tree()
        self.chapters_tree.selection_set(str(self.current_chapter_idx))
        self.update_status("Chapter moved up (click Save All)", "orange")

    def move_chapter_down(self):
        """Move the selected chapter down in the list"""
        selected_indices = self.get_selected_chapter_indices()
        if len(selected_indices) > 1:
            messagebox.showwarning("Warning", "Select a single chapter to move.")
            return
        if self.current_chapter_idx is None:
            messagebox.showwarning("Warning", "Select a chapter first")
            return

        idx = self.current_chapter_idx
        if idx >= len(self.chapters) - 1:
            return

        self.chapters[idx], self.chapters[idx + 1] = self.chapters[idx + 1], self.chapters[idx]
        self.current_chapter_idx = idx + 1
        self.refresh_chapters_tree()
        self.chapters_tree.selection_set(str(self.current_chapter_idx))
        self.update_status("Chapter moved down (click Save All)", "orange")

    def add_chapter(self):
        """Add new chapter"""
        if not self.current_section:
            messagebox.showwarning("Warning", "Select a section first")
            return
        
        new_chapter = {
            "id": str(len(self.chapters) + 1),
            "name": "New Chapter",
            "q": 0,
            "file": f"chapter{len(self.chapters) + 1}.json"
        }
        self.chapters.append(new_chapter)
        self.refresh_chapters_tree()
        self.update_status("Chapter added (click Save All)", "orange")

    def _copy_source_to_dest(self, src_path, dest_path):
        """Copy or extract src_path (dir or zip) into dest_path.
        Handles copying 'theme' or 'themes' directories correctly."""
        src = Path(src_path)
        dest = Path(dest_path)
        try:
            dest.mkdir(parents=True, exist_ok=True)

            # If zip file
            if src.is_file() and zipfile.is_zipfile(src):
                with zipfile.ZipFile(src, 'r') as z:
                    z.extractall(dest)
                return True, None

            # If directory, copy contents
            if src.is_dir():
                for item in src.iterdir():
                    target = dest / item.name
                    if item.is_dir():
                        # If target exists, merge by removing and replacing
                        if target.exists():
                            shutil.rmtree(target)
                        shutil.copytree(item, target)
                    else:
                        shutil.copy2(item, target)
                return True, None

            # If single file, copy
            if src.is_file():
                shutil.copy2(src, dest / src.name)
                return True, None

            return False, 'Source not found'
        except Exception as e:
            return False, str(e)

    def import_section(self):
        """Import a section from a directory or zip. Copies theme if present."""
        src_dir = filedialog.askdirectory(title="Select section folder to import")
        if not src_dir:
            # allow zip selection as alternative
            src_file = filedialog.askopenfilename(title="Select section zip to import",
                                                  filetypes=[("Zip Archives","*.zip")])
            if not src_file:
                return
            src_dir = src_file

        src = Path(src_dir)
        sec_id = src.stem if src.is_file() else src.name
        section_exists = any(s['id'] == sec_id for s in self.sections)
        if section_exists:
            if not messagebox.askyesno("Exists", f"Section '{sec_id}' already exists. Overwrite?"):
                return

        dest_rel = f"data/{sec_id}"
        dest = self.base_path / dest_rel

        ok, err = self._copy_source_to_dest(src, dest)
        if not ok:
            messagebox.showerror("Import Failed", f"Failed to import section: {err}")
            return

        # Add or update section entry
        new_section = {
            "id": sec_id,
            "name": sec_id,
            "path": dest_rel,
            "description": "",
            "icon": f"{dest_rel}/icon.png",
        }

        # Prefer existing icon file if present under another common extension.
        icon_png = self.base_path / dest_rel / "icon.png"
        if not icon_png.exists():
            for candidate in ["icon.webp", "icon.jpg", "icon.jpeg", "icon.gif", "icon.bmp"]:
                candidate_path = self.base_path / dest_rel / candidate
                if candidate_path.exists():
                    new_section["icon"] = f"{dest_rel}/{candidate}"
                    break

        # remove existing section with same id
        self.sections = [s for s in self.sections if s['id'] != sec_id]
        self.sections.append(new_section)
        self.save_sections()
        self.load_sections()
        self.update_status(f"Imported section: {sec_id}", "green")

    def import_chapters(self):
        """Import chapter files (JSON or ZIP) into the currently selected section."""
        if not self.current_section:
            messagebox.showwarning("Warning", "Select a section first")
            return

        files = filedialog.askopenfilenames(title="Select chapter files or zip",
                                            filetypes=[("JSON","*.json"), ("Zip","*.zip"), ("All","*.*")])
        if not files:
            return

        section = next((s for s in self.sections if s['id'] == self.current_section), None)
        if not section:
            messagebox.showerror("Error", "Selected section not found")
            return

        dest = self.base_path / section.get('path', '')
        dest.mkdir(parents=True, exist_ok=True)

        for f in files:
            src = Path(f)
            if src.is_file() and zipfile.is_zipfile(src):
                ok, err = self._copy_source_to_dest(src, dest)
                if not ok:
                    messagebox.showerror("Import Failed", f"Failed to extract {src.name}: {err}")
                    return
            else:
                try:
                    # copy single file
                    shutil.copy2(src, dest / src.name)
                except Exception as e:
                    messagebox.showerror("Import Failed", f"Failed to copy {src.name}: {e}")
                    return

        # Reload chapters and save
        self.load_chapters()
        self.save_chapter()
        self.update_status("Chapters imported (and saved)", "green")
    
    def delete_chapter(self):
        """Delete chapter"""
        selected_indices = self.get_selected_chapter_indices()
        if not selected_indices and self.current_chapter_idx is not None:
            selected_indices = [self.current_chapter_idx]
        if not selected_indices:
            messagebox.showwarning("Warning", "Select one or more chapters first")
            return

        selected_chapters = [self.chapters[i] for i in selected_indices]
        chapter_names = [c.get('name', c.get('id', '')) for c in selected_chapters]
        preview_names = "\n".join(f"- {name}" for name in chapter_names[:8])
        if len(chapter_names) > 8:
            preview_names += f"\n... and {len(chapter_names) - 8} more"

        dlg = tk.Toplevel(self.root)
        _style_dialog(dlg, "Delete Chapter", "600x320")
        dlg.transient(self.root)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=12, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Delete {len(selected_chapters)} chapter(s)?", style="Header.TLabel").pack(anchor=tk.W, pady=(0,8))
        ttk.Label(frame, text="This will remove the chapter from the list.").pack(anchor=tk.W)
        ttk.Label(frame, text=preview_names, style="Muted.TLabel", justify=tk.LEFT).pack(anchor=tk.W, pady=(8, 0))

        del_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Also delete chapter file from disk (permanent)", variable=del_var, bootstyle="warning").pack(anchor=tk.W, pady=(8, 0))

        del_images_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Also delete chapter images from disk (permanent)", variable=del_images_var, bootstyle="warning").pack(anchor=tk.W, pady=(4, 8))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10,0))

        def do_delete():
            section = next((s for s in self.sections if s['id'] == self.current_section), None)

            for idx in reversed(selected_indices):
                chapter = self.chapters[idx]
                image_paths = []

                # Collect image paths from chapter JSON before deleting files.
                if section and (del_var.get() or del_images_var.get()):
                    try:
                        fpath = self.base_path / section.get('path', '') / chapter.get('file', '')
                        if fpath.exists():
                            data = _load_json_file(fpath)
                            chapter_data = data[0] if isinstance(data, list) and data else data
                            if isinstance(chapter_data, dict):
                                for q in chapter_data.get('questions', []):
                                    img = q.get('image', '')
                                    if img:
                                        image_paths.append(img)
                    except Exception as e:
                        print(f"Warning: Could not read chapter images: {e}")

                if del_images_var.get() and image_paths:
                    for img_rel in image_paths:
                        try:
                            img_path = self.base_path / img_rel
                            if img_path.exists():
                                img_path.unlink()
                        except Exception as e:
                            print(f"Warning: Failed to delete image {img_rel}: {e}")

                if del_var.get():
                    try:
                        if section:
                            fpath = self.base_path / section.get('path', '') / chapter.get('file', '')
                            if fpath.exists():
                                fpath.unlink()
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to delete chapter file: {e}")
                        return

                try:
                    del self.chapters[idx]
                except Exception:
                    pass

            self.current_chapter_idx = None
            self.refresh_chapters_tree()
            self.ch_id.delete(0, tk.END)
            self.ch_name.delete(0, tk.END)
            self.ch_count.delete(0, tk.END)
            self.update_chapter_btn.config(state="disabled")
            self.update_status("Chapter(s) deleted (click Save All)", "orange")
            dlg.destroy()

        def cancel():
            dlg.destroy()

        ttk.Button(btn_frame, text="Delete", command=do_delete, width=12, bootstyle="danger").pack(side=tk.RIGHT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=cancel, width=12, bootstyle="secondary-outline").pack(side=tk.RIGHT)

    def save_chapter(self):
        """Save chapter changes"""
        if not self.current_section:
            return
        
        section = next((s for s in self.sections if s['id'] == self.current_section), None)
        if not section:
            return
        
        try:
            ch_file = self.base_path / f"{section['path']}" / "chapters.json"
            ch_file.parent.mkdir(parents=True, exist_ok=True)
            with open(ch_file, 'w', encoding='utf-8') as f:
                json.dump(self.chapters, f, indent=2)
            self.update_status("Chapters saved", "green")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def save_sections(self):
        """Save sections to config"""
        try:
            self.config_path.mkdir(parents=True, exist_ok=True)
            config_file = self.config_path / "sections.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.sections, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def save_all(self):
        """Save everything"""
        self.save_sections()
        self.save_chapter()
        try:
            self.generate_js_config()
        except Exception as e:
            print(f"Auto-config error: {e}")
        self.update_status("✓ All saved & configured", "green")
        
    def generate_js_config(self):
        """Generate js/exam-config.js from current sections and chapters"""
        try:
            full_config = []
            
            for section in self.sections:
                sec_data = {
                    "id": section['id'],
                    "name": section['name'],
                    "description": section.get('description', ''),
                    "path": section['path'],
                    "icon": section.get('icon', self._default_section_icon_rel(section.get('id', ''), section.get('path', ''))),
                    "chapters": []
                }
                
                # AUTO-SYNC: Respect existing chapters.json order, only append new files
                sec_path = self.base_path / section['path']
                if sec_path.exists():
                    # Load existing chapters.json to preserve manual ordering
                    ch_json_path = sec_path / "chapters.json"
                    existing_chapters = []
                    if ch_json_path.exists():
                        try:
                            existing_chapters = _load_json_file(ch_json_path)
                        except Exception:
                            existing_chapters = []

                    # Track which files are already in chapters.json
                    known_files = {ch.get('file', '') for ch in existing_chapters}

                    # Scan for new chapter files not yet in chapters.json
                    chapter_files = [p for p in sec_path.glob("*.json") if p.name != "chapters.json"]

                    def get_chapter_num(path):
                        match = re.search(r'chapter(\d+)', path.name)
                        return int(match.group(1)) if match else 999

                    chapter_files.sort(key=get_chapter_num)

                    new_chapters = []
                    for ch_file in chapter_files:
                        if ch_file.name in known_files:
                            continue

                        try:
                            content = _load_json_file(ch_file)

                            data_obj = content[0] if isinstance(content, list) and content else content
                            if isinstance(content, list) and not content:
                                data_obj = {}

                            f_match = re.search(r'chapter(\d+)', ch_file.name)
                            if f_match:
                                c_id = f_match.group(1)
                            else:
                                c_id = str(data_obj.get("params", {}).get("chapter", ch_file.stem))

                            c_title = data_obj.get("title", ch_file.stem)
                            c_title = c_title.replace(f"Chapter {c_id} ", "").strip()

                            c_q = len(data_obj.get("questions", []))
                            if not c_q and 'totalQuestions' in data_obj:
                                c_q = data_obj['totalQuestions']

                            new_chapters.append({
                                "id": str(c_id),
                                "name": c_title,
                                "q": c_q,
                                "file": ch_file.name
                            })
                        except Exception as e:
                            print(f"Skipping {ch_file}: {e}")

                    # Update question counts for existing chapters
                    for ch in existing_chapters:
                        ch_path = sec_path / ch.get('file', '')
                        if ch_path.exists():
                            try:
                                content = _load_json_file(ch_path)
                                data_obj = content[0] if isinstance(content, list) and content else content
                                if isinstance(content, list) and not content:
                                    data_obj = {}
                                c_q = len(data_obj.get("questions", []))
                                if c_q:
                                    ch['q'] = c_q
                            except Exception:
                                pass

                    # Preserve existing order, append new files at end
                    synced_chapters = existing_chapters + new_chapters

                    try:
                        with open(ch_json_path, 'w', encoding='utf-8') as f:
                            json.dump(synced_chapters, f, indent=2)
                    except Exception as e:
                        print(f"Failed to save chapters.json: {e}")

                ch_file = self.base_path / section['path'] / "chapters.json"
                if ch_file.exists():
                    try:
                        chapters = _load_json_file(ch_file)
                        for ch in chapters:
                            ch['file'] = f"{section['path']}/{ch.get('file', '')}"
                            if 'q' not in ch or ch['q'] == 0:
                                try:
                                    q_path = self.base_path / section['path'] / ch.get('file', '')
                                    q_data = _load_json_file(q_path)
                                    if isinstance(q_data, list):
                                        q_data = q_data[0]
                                    ch['q'] = len(q_data.get('questions', []))
                                except:
                                    pass
                        sec_data["chapters"] = chapters
                    except:
                        sec_data["chapters"] = []
                
                full_config.append(sec_data)
            
            js_path = self.base_path / "js" / "exam-config.js"
            js_path.parent.mkdir(parents=True, exist_ok=True)
            with open(js_path, 'w', encoding='utf-8') as f:
                json_str = json.dumps(full_config, indent=2)
                f.write(f"const EXAM_CONFIG = {json_str};\n")
            
            # Refresh tables after configuration
            self.load_sections()
            if self.current_section:
                self.load_chapters()
                
            messagebox.showinfo("Success", 
                              f"Engine Configured Successfully!\n\nGenerated: {js_path.relative_to(self.base_path)}\nTables refreshed with latest data.")
            self.update_status("✓ Engine configured", "green")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate config: {e}")


if __name__ == "__main__":
    root = ttk.Window(
        title="Exam Engine Editor",
        themename="darkly",
        size=(1480, 860),
    )
    style = ttk.Style()
    _configure_custom_styles(style)
    app = ExamEditor(root)
    root.mainloop()