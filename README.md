# SigilWire
Emoji-based text/binary codec. Two modes:
- **Compact (Base64‑emoji)** — dense transport; uses 🟦 as pad.
- **OctaSigil (8‑emoji octal)** — human‑auditable, zero punctuation.

> Encoding ≠ encryption. This is transport/obfuscation only.

## Why
Push bytes through chat UIs, CRMs, or social platforms that mangle punctuation or strip Base64. Emojis usually survive intact. SigilWire keeps payloads lossless and copy/paste‑safe.

## Features
- Base64‑emoji encode/decode (🟦 padding).
- Optional **OctaSigil** (8‑emoji octal) mode.
- Auto‑detect for Base64‑emoji (heuristic).
- CLI + importable module (single file, Python 3).
- Zero external deps.

## Quick Start
### CLI
```bash
# Decode Base64‑emoji from stdin to UTF‑8 text
echo '😀😄😉…🟦' | python emoji_codec.py --decode --mode b64

# Encode to Base64‑emoji
echo 'hello world' | python emoji_codec.py --encode --mode b64

# Auto‑detect decode (Base64‑emoji)
echo '😀😄😉…🟦' | python emoji_codec.py --decode
```

> If your flags differ, run: `python emoji_codec.py -h`

### OctaSigil (8‑emoji octal)
Default alphabet (edit as needed):
```
😀=0, 😄=1, 😉=2, 😂=3, 😆=4, 😘=5, 😍=6, 😎=7
```

Encode (concept):
```bash
echo 'hello' | python emoji_codec.py --encode --mode oct8
```
Decode:
```bash
echo '😀😉😂…' | python emoji_codec.py --decode --mode oct8
```

## Library Use (reference)
If you want the 8‑emoji mode and it isn’t wired yet, drop these helpers in or import them from this repo:

```python
OCT8 = "😀😄😉😂😆😘😍😎"
E2O = {e:str(i) for i,e in enumerate(OCT8)}
O2E = {str(i):e for i,e in enumerate(OCT8)}

def encode_octal_emoji(text, enc="utf-8"):
    b = text.encode(enc)
    return "".join(O2E[d] for byte in b for d in f"{byte:03o}")

def decode_octal_emoji(s, enc="utf-8"):
    digits = "".join(E2O[ch] for ch in s if ch in E2O)
    if len(digits) % 3: raise ValueError("Corrupt octal stream")
    return bytes(int(digits[i:i+3], 8) for i in range(0, len(digits), 3)).decode(enc)
```

## Heuristics
- **Base64‑emoji**: large emoji alphabet; ends with optional 🟦 pads.
- **OctaSigil**: only the eight symbols above; length divisible by 3 (octal bytes).

## Troubleshooting
- **Garbled text** → wrong mode or binary output; redirect to a file (`--raw` if supported).
- **Missing glyphs** → install a full emoji font; ensure your terminal isn’t normalizing.
- **Copy/paste drift** → some apps replace emojis; paste via plain‑text editors first.
- **Padding issues** → Base64‑emoji requires 0–2 trailing 🟦 pads like standard Base64.

## Notes
- This is not cryptography. To hide content, encrypt first, then encode.
- The Base64‑emoji alphabet and padding symbol are defined in the script. Customize as needed.

## Roadmap
- Streaming decode for very long payloads
- Checksum/CRC option
- Pluggable emoji alphabets (regional, grayscale, symbols‑only)

## License
MIT — do whatever, no warranty. Attribution appreciated.
