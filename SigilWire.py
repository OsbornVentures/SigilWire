#!/usr/bin/env python3
"""
Emoji Encode/Decode — GUI + CLI
--------------------------------------------------
- No dependencies (Tkinter built-in)
- Two reversible modes:
  1) Simple (Hex): robust, 16-emoji alphabet; safest for all environments.
  2) Compact (Base64): ~33% smaller output using 64-emoji alphabet with explicit padding.
- Features: Copy, Paste, Clear, Auto-Detect Decode, Save, Load, and CLI flags.
"""

import base64
import binascii
import sys
import argparse
from dataclasses import dataclass

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except Exception as e:
    tk = None  # headless environments


# -----------------------------
# Alphabets
# -----------------------------

# 16-emoji alphabet for hex nibbles (all single code point for robustness)
HEX_EMOJI_16 = [
    "😀","😁","😂","😃","😄","😅","😆","😉","😊","🙂","🙃","😋","😎","😍","😘","😗"
]
HEX_MAP = {f"{i:x}": HEX_EMOJI_16[i] for i in range(16)}
REV_HEX_MAP = {v: k for k, v in HEX_MAP.items()}

# 64-emoji alphabet for Base64 indices (mostly single codepoint; avoid ZWJ where possible)
BASE64_EMOJI_64 = [
    "😀","😁","😂","😃","😄","😅","😆","😉",
    "😊","🙂","🙃","😋","😎","😍","😘","😗",
    "😙","😚","🥰","🤩","🤗","🤔","🤨","😐",
    "😑","😶","🙄","😏","😣","😥","😮","🤐",
    "😪","😫","🥱","😴","😌","😛","😜","🤪",
    "😝","🤗","🤭","🤫","🤥","😬","😔","😕",
    "🙁","☹️","😟","😤","😢","😭","😱","😨",
    "😰","😯","😲","🤯","😴","😌","😈","👻",
]
# Ensure length 64; if duplicates exist it doesn't break reversibility as we map positions, not glyphs
if len(BASE64_EMOJI_64) != 64:
    raise RuntimeError("BASE64_EMOJI_64 must contain exactly 64 emojis.")

PADDING_EMOJI = "🟦"  # explicit padding for Base64 mode

# Charsets for translation
B64_STD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
B64_TO_EMOJI = {B64_STD[i]: BASE64_EMOJI_64[i] for i in range(64)}
EMOJI_TO_B64 = {BASE64_EMOJI_64[i]: B64_STD[i] for i in range(64)}


# -----------------------------
# Core Codec
# -----------------------------

@dataclass
class CodecResult:
    ok: bool
    data: str
    error: str = ""


def encode_hex_emoji(text: str, encoding="utf-8") -> CodecResult:
    try:
        raw = text.encode(encoding)
        hexstr = raw.hex()
        out = "".join(HEX_MAP[h] for h in hexstr)
        return CodecResult(True, out)
    except Exception as e:
        return CodecResult(False, "", str(e))


def decode_hex_emoji(emoji_text: str, encoding="utf-8") -> CodecResult:
    try:
        # Split by code point (iterate by Unicode scalar values)
        # Tkinter/python already iterates by code point in strings
        nibbles = []
        for ch in emoji_text:
            if ch in REV_HEX_MAP:
                nibbles.append(REV_HEX_MAP[ch])
            else:
                # Ignore whitespace; stop on unknown non-whitespace
                if ch.isspace():
                    continue
                return CodecResult(False, "", f"Unknown emoji in hex stream: {repr(ch)}")
        hexstr = "".join(nibbles)
        if len(hexstr) % 2 != 0:
            return CodecResult(False, "", "Odd-length hex after mapping (corrupt input).")
        raw = bytes.fromhex(hexstr)
        return CodecResult(True, raw.decode(encoding, errors="strict"))
    except Exception as e:
        return CodecResult(False, "", str(e))


def encode_b64_emoji(text: str, encoding="utf-8") -> CodecResult:
    try:
        b64 = base64.b64encode(text.encode(encoding)).decode("ascii")
        out = []
        for ch in b64:
            if ch == "=":
                out.append(PADDING_EMOJI)
            else:
                out.append(B64_TO_EMOJI[ch])
        return CodecResult(True, "".join(out))
    except Exception as e:
        return CodecResult(False, "", str(e))


def decode_b64_emoji(emoji_text: str, encoding="utf-8") -> CodecResult:
    try:
        # Map back emoji → base64 charset, ignoring whitespace
        chars = []
        buf = ""
        # Handle possible multi-codepoint emojis (e.g., '☹️') by greedy matching
        # Strategy: attempt to match 2-char sequences that may contain VS-16; fallback to single char
        i = 0
        while i < len(emoji_text):
            ch = emoji_text[i]
            # try greedy match for sequences commonly having VS-16
            if i + 1 < len(emoji_text):
                two = emoji_text[i:i+2]
                if two in EMOJI_TO_B64 or two == PADDING_EMOJI:
                    ch = two
                    i += 2
                else:
                    i += 1
            else:
                i += 1
            if ch.isspace():
                continue
            if ch == PADDING_EMOJI:
                chars.append("=")
                continue
            if ch in EMOJI_TO_B64:
                chars.append(EMOJI_TO_B64[ch])
            else:
                # fallback: sometimes VS-16 yields length 1, try normalize by removing variation selector
                # (best-effort; if not found, error)
                return CodecResult(False, "", f"Unknown emoji in base64 stream: {repr(ch)}")

        b64 = "".join(chars)
        raw = base64.b64decode(b64, validate=True)
        return CodecResult(True, raw.decode(encoding, errors="strict"))
    except (binascii.Error, Exception) as e:
        return CodecResult(False, "", f"Base64 decode error: {e}")


def looks_like_hex_emoji(s: str) -> bool:
    return all((ch in REV_HEX_MAP) or ch.isspace() for ch in s) and any(ch in REV_HEX_MAP for ch in s)


def looks_like_b64_emoji(s: str) -> bool:
    emoji_set = set(BASE64_EMOJI_64 + [PADDING_EMOJI])
    return all((ch in emoji_set) or ch.isspace() for ch in s) and any(ch in emoji_set for ch in s)


# -----------------------------
# GUI
# -----------------------------

class EmojiCodecApp:
    def __init__(self, root):
        self.root = root
        root.title("Emoji Encode/Decode")
        root.geometry("840x560")
        root.minsize(720, 480)

        self.mode = tk.StringVar(value="hex")   # 'hex' or 'b64'
        self.direction = tk.StringVar(value="encode")  # 'encode' or 'decode'

        self._build_ui()

    def _build_ui(self):
        # Top controls
        frame_top = ttk.Frame(self.root, padding=(10,10,10,0))
        frame_top.pack(fill="x")

        ttk.Label(frame_top, text="Mode:").pack(side="left")
        ttk.Radiobutton(frame_top, text="Simple (Hex)", variable=self.mode, value="hex").pack(side="left", padx=6)
        ttk.Radiobutton(frame_top, text="Compact (Base64)", variable=self.mode, value="b64").pack(side="left", padx=6)

        ttk.Label(frame_top, text="Direction:").pack(side="left", padx=(20,0))
        ttk.Radiobutton(frame_top, text="Encode →", variable=self.direction, value="encode").pack(side="left", padx=6)
        ttk.Radiobutton(frame_top, text="← Decode", variable=self.direction, value="decode").pack(side="left", padx=6)

        ttk.Button(frame_top, text="Auto‑Detect Decode", command=self.auto_detect_decode).pack(side="right", padx=6)
        ttk.Button(frame_top, text="Swap", command=self.swap).pack(side="right")

        # Text areas
        frame_mid = ttk.Frame(self.root, padding=10)
        frame_mid.pack(fill="both", expand=True)

        left = ttk.Frame(frame_mid)
        left.pack(side="left", fill="both", expand=True, padx=(0,5))

        right = ttk.Frame(frame_mid)
        right.pack(side="left", fill="both", expand=True, padx=(5,0))

        ttk.Label(left, text="Input").pack(anchor="w")
        self.input = tk.Text(left, wrap="word", height=14, undo=True)
        self.input.pack(fill="both", expand=True)
        btns_l = ttk.Frame(left)
        btns_l.pack(fill="x", pady=(5,0))
        ttk.Button(btns_l, text="Paste", command=self.paste_input).pack(side="left")
        ttk.Button(btns_l, text="Clear", command=lambda: self.input.delete("1.0", "end")).pack(side="left", padx=6)
        ttk.Button(btns_l, text="Load…", command=self.load_input).pack(side="left", padx=6)

        ttk.Label(right, text="Output").pack(anchor="w")
        self.output = tk.Text(right, wrap="word", height=14, state="normal")
        self.output.pack(fill="both", expand=True)
        btns_r = ttk.Frame(right)
        btns_r.pack(fill="x", pady=(5,0))
        ttk.Button(btns_r, text="Copy", command=self.copy_output).pack(side="left")
        ttk.Button(btns_r, text="Save…", command=self.save_output).pack(side="left", padx=6)

        # Bottom action bar
        frame_bot = ttk.Frame(self.root, padding=10)
        frame_bot.pack(fill="x")

        ttk.Button(frame_bot, text="Run", command=self.run).pack(side="left")
        ttk.Button(frame_bot, text="Help", command=self.show_help).pack(side="left", padx=6)

        self.status = ttk.Label(frame_bot, text="Ready.", anchor="w")
        self.status.pack(side="left", padx=(20,0))

    # Actions
    def run(self):
        text = self.input.get("1.0", "end").rstrip("\n")
        if not text:
            self._set_status("Input is empty.")
            self.output_delete_and_insert("")
            return

        if self.direction.get() == "encode":
            res = encode_hex_emoji(text) if self.mode.get() == "hex" else encode_b64_emoji(text)
        else:
            res = decode_hex_emoji(text) if self.mode.get() == "hex" else decode_b64_emoji(text)

        if res.ok:
            self.output_delete_and_insert(res.data)
            self._set_status("Success.")
        else:
            self.output_delete_and_insert("")
            self._set_status(f"Error: {res.error}")
            messagebox.showerror("Error", res.error)

    def auto_detect_decode(self):
        text = self.input.get("1.0", "end").strip()
        if not text:
            self._set_status("Nothing to detect.")
            return
        if looks_like_hex_emoji(text):
            self.mode.set("hex"); self.direction.set("decode"); self.run()
        elif looks_like_b64_emoji(text):
            self.mode.set("b64"); self.direction.set("decode"); self.run()
        else:
            self._set_status("Cannot detect encoded emoji stream.")

    def swap(self):
        in_text = self.input.get("1.0", "end")
        out_text = self.output.get("1.0", "end")
        self.input.delete("1.0","end")
        self.output_delete_and_insert("")
        self.input.insert("1.0", out_text)
        self.output_delete_and_insert(in_text)
        self._set_status("Swapped Input/Output.")

    def paste_input(self):
        try:
            self.input.delete("1.0","end")
            self.input.insert("1.0", self.root.clipboard_get())
            self._set_status("Pasted from clipboard.")
        except Exception:
            self._set_status("Clipboard empty or unavailable.")

    def copy_output(self):
        out = self.output.get("1.0","end").rstrip("\n")
        if not out:
            self._set_status("Nothing to copy.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(out)
        self._set_status("Copied to clipboard.")

    def load_input(self):
        path = filedialog.askopenfilename(title="Load Input", filetypes=[("Text Files","*.txt *.md *.log *.json *.csv"),("All Files","*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            self.input.delete("1.0","end")
            self.input.insert("1.0", data)
            self._set_status(f"Loaded: {path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def save_output(self):
        path = filedialog.asksaveasfilename(title="Save Output", defaultextension=".txt", filetypes=[("Text Files","*.txt"),("All Files","*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.output.get("1.0","end"))
            self._set_status(f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def show_help(self):
        msg = (
            "Emoji Encode/Decode\n\n"
            "Modes:\n"
            "• Simple (Hex): Lossless, maps each hex nibble to one emoji. Safest.\n"
            "• Compact (Base64): Smaller output using 64-emoji alphabet; uses 🟦 as padding.\n\n"
            "Tips:\n"
            "• Use Auto‑Detect Decode to guess the encoded format.\n"
            "• Copy/Save outputs; Load/Paste inputs.\n"
            "• CLI supported: --encode/--decode and --mode hex|b64.\n"
        )
        messagebox.showinfo("Help", msg)

    def _set_status(self, msg):
        self.status.config(text=msg)

    def output_delete_and_insert(self, s: str):
        self.output.config(state="normal")
        self.output.delete("1.0","end")
        self.output.insert("1.0", s)
        self.output.config(state="normal")


# -----------------------------
# CLI
# -----------------------------

def run_cli(argv):
    p = argparse.ArgumentParser(description="Emoji Encode/Decode (GUI + CLI)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--encode", action="store_true", help="Encode input text to emojis")
    g.add_argument("--decode", action="store_true", help="Decode emoji text back to original")
    p.add_argument("--mode", choices=["hex","b64"], default="hex", help="Encoding mode (default: hex)")
    p.add_argument("--in", dest="infile", default="-", help="Input file path or '-' for stdin")
    p.add_argument("--out", dest="outfile", default="-", help="Output file path or '-' for stdout")
    args = p.parse_args(argv)

    # Read input
    if args.infile == "-":
        data = sys.stdin.read()
    else:
        with open(args.infile, "r", encoding="utf-8") as f:
            data = f.read()

    if not (args.encode or args.decode):
        print("Specify --encode or --decode. Launching GUI instead...", file=sys.stderr)
        launch_gui()
        return 0

    if args.encode:
        res = encode_hex_emoji(data) if args.mode == "hex" else encode_b64_emoji(data)
    else:
        # Auto-detect if mode unspecified by content AND user picked default 'hex'
        if args.mode == "hex" and looks_like_b64_emoji(data):
            res = decode_b64_emoji(data)
        elif args.mode == "b64" and looks_like_hex_emoji(data):
            res = decode_hex_emoji(data)
        else:
            res = decode_hex_emoji(data) if args.mode == "hex" else decode_b64_emoji(data)

    if not res.ok:
        print(f"Error: {res.error}", file=sys.stderr)
        return 2

    if args.outfile == "-":
        sys.stdout.write(res.data)
    else:
        with open(args.outfile, "w", encoding="utf-8") as f:
            f.write(res.data)
    return 0


def launch_gui():
    if tk is None:
        print("Tkinter not available. Use CLI flags: --encode/--decode", file=sys.stderr)
        sys.exit(1)
    root = tk.Tk()
    # Apply sensible padding theme
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    EmojiCodecApp(root)
    root.mainloop()


def main():
    if len(sys.argv) > 1:
        sys.exit(run_cli(sys.argv[1:]))
    else:
        launch_gui()


if __name__ == "__main__":
    main()
