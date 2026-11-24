import json, re, glob

name = glob.glob("*.srt")[0]
OUTPUT_FILENAME = f'hindi_{name}'
UNTRANSLATED_FILENAME = 'untranslated.txt'

srt_files = [f for f in glob.glob("*.srt") if f != OUTPUT_FILENAME]
if not srt_files:
    raise FileNotFoundError("No input SRT file found!")

file = srt_files[0]
db = glob.glob("*.json")[0]

TRAILING_PUNCT_RE = re.compile(r'[.!?,;:…।॥]+\s*$')

# Source terminal punctuation -> Hindi terminal punctuation
PUNCT_MAP = {
    '.': '।',
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r'\s+', ' ', text).strip()


def strip_trailing_punct(text: str) -> str:
    return TRAILING_PUNCT_RE.sub('', text).rstrip()


def get_trailing_punct(text: str) -> str:
    m = TRAILING_PUNCT_RE.search(text)
    return m.group(0).strip() if m else ''


def map_trailing_punct(p: str) -> str:
    return PUNCT_MAP.get(p, p)


def build_regex(key: str):
    words = re.findall(r'\w+', key.lower())
    if not words:
        return None
    # FIX: allow any non-word character (space, comma, apostrophe ' or ’,
    # hyphen, etc.) between words. The previous `[\s,]*` did not allow
    # apostrophes, so keys like "it's" never matched "it's" in the text.
    return re.compile(
        r'\b' + r'[^\w]*'.join(re.escape(w) for w in words) + r'\b',
        re.IGNORECASE,
    )


def translate_srt_partial(srt_filename, json_filename, output_filename):
    with open(json_filename, 'r', encoding='utf-8') as f:
        trans_dict = json.load(f)

    sorted_keys = sorted(trans_dict.keys(), key=len, reverse=True)

    norm_dict = {}
    for k in sorted_keys:
        nk = normalize_text(k)
        if nk and nk not in norm_dict:
            norm_dict[nk] = trans_dict[k]

    patterns, seen = [], set()
    for k in sorted_keys:
        pat = build_regex(k)
        if pat is None or pat.pattern in seen:
            continue
        seen.add(pat.pattern)
        patterns.append((pat, strip_trailing_punct(trans_dict[k])))

    with open(srt_filename, 'r', encoding='utf-8') as f:
        content = f.read()

    raw_blocks = re.split(r'\n\s*\n', content.strip())
    blocks = []
    for b in raw_blocks:
        lines = b.strip().split('\n')
        if len(lines) >= 3:
            m = re.match(r'([\d:,]+)\s*-->\s*([\d:,]+)', lines[1])
            blocks.append({
                'start': m.group(1) if m else "",
                'end':   m.group(2) if m else "",
                'text':  ' '.join(lines[2:]),
            })

    sentences, untranslated_sentences, translated_sentences = [], [], []
    current_group_times, current_text_parts = [], []

    for block in blocks:
        if not current_group_times:
            current_group_times = [block['start'], block['end']]
        else:
            current_group_times[1] = block['end']

        current_text_parts.append(block['text'])
        combined = re.sub(r'\s+', ' ', ' '.join(current_text_parts)).strip()

        if re.search(r'[.?!]$', combined) or block == blocks[-1]:
            translated_text = combined
            matched = False

            # (a) whole-sentence match
            norm_sentence = normalize_text(combined)
            if norm_sentence in norm_dict:
                body     = strip_trailing_punct(norm_dict[norm_sentence])
                trailing = map_trailing_punct(get_trailing_punct(combined))
                translated_text = body + trailing
                matched = True
            else:
                # (b) partial replacement (phrase inside a longer sentence)
                for pat, repl in patterns:
                    new_text, n = pat.subn(repl, translated_text)
                    if n:
                        translated_text, matched = new_text, True

            (translated_sentences if matched else untranslated_sentences).append(
                translated_text if matched else combined
            )

            sentences.append({
                'start': current_group_times[0],
                'end':   current_group_times[1],
                'text':  translated_text,
            })
            current_group_times, current_text_parts = [], []

    with open(output_filename, 'w', encoding='utf-8') as f:
        for i, item in enumerate(sentences, 1):
            f.write(f"{i}\n{item['start']} --> {item['end']}\n{item['text']}\n\n")

    seen, unique = set(), []
    for s in untranslated_sentences:
        if s not in seen:
            seen.add(s); unique.append(s)

    with open(UNTRANSLATED_FILENAME, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(unique))
        if unique:
            f.write('\n')

    print(f"Total sentences:                     {len(translated_sentences)+len(untranslated_sentences)}")
    print(f"Translated sentences (full count):   {len(translated_sentences)}")
    print(f"Fully untranslated unique sentences: {len(unique)}")


if __name__ == '__main__':
    translate_srt_partial(file, db, OUTPUT_FILENAME)