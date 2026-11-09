import json, re, glob

name = glob.glob("*.srt")[0]
OUTPUT_FILENAME = f'hindi_{name}'
UNTRANSLATED_FILENAME = 'untranslated.txt'

srt_files = [f for f in glob.glob("*.srt") if f != OUTPUT_FILENAME]
if not srt_files:
    raise FileNotFoundError("No input SRT file found!")

file = srt_files[0]
db = glob.glob("*.json")[0]


def translate_srt_partial(srt_filename, json_filename, output_filename):
    with open(json_filename, 'r', encoding='utf-8') as f:
        trans_dict = json.load(f)

    sorted_keys = sorted(trans_dict.keys(), key=len, reverse=True)

    with open(srt_filename, 'r', encoding='utf-8') as f:
        content = f.read()

    raw_blocks = re.split(r'\n\s*\n', content.strip())
    blocks = []
    for b in raw_blocks:
        lines = b.strip().split('\n')
        if len(lines) >= 3:
            match = re.match(r'([\d:,]+)\s*-->\s*([\d:,]+)', lines[1])
            start_time = match.group(1) if match else ""
            end_time = match.group(2) if match else ""
            text = ' '.join(lines[2:])
            blocks.append({'start': start_time, 'end': end_time, 'text': text})

    sentences = []
    current_group_times = []
    current_text_parts = []

    # Keep full sentences that were never translated
    untranslated_sentences = []
    # NEW: keep translated sentences (full count, not unique)
    translated_sentences = []

    for block in blocks:
        if not current_group_times:
            current_group_times = [block['start'], block['end']]
        else:
            current_group_times[1] = block['end']

        current_text_parts.append(block['text'])
        combined_text = ' '.join(current_text_parts)
        combined_text_normalized = re.sub(r'\s+', ' ', combined_text).strip()

        if re.search(r'[.?!]$', combined_text_normalized) or block == blocks[-1]:
            translated_text = combined_text_normalized
            matched = False

            for key in sorted_keys:
                if key in translated_text:
                    translated_text = translated_text.replace(key, trans_dict[key])
                    matched = True

            if not matched:
                untranslated_sentences.append(combined_text_normalized)
            else:
                # NEW: track every translated sentence (full count)
                translated_sentences.append(translated_text)

            sentences.append({
                'start': current_group_times[0],
                'end': current_group_times[1],
                'text': translated_text
            })
            current_group_times = []
            current_text_parts = []

    # Write translated SRT
    with open(output_filename, 'w', encoding='utf-8') as f:
        for i, item in enumerate(sentences, 1):
            f.write(f"{i}\n{item['start']} --> {item['end']}\n{item['text']}\n\n")

    # Write unique untranslated sentences (order of first appearance)
    seen = set()
    unique_sentences = []
    for s in untranslated_sentences:
        if s not in seen:
            seen.add(s)
            unique_sentences.append(s)

    with open(UNTRANSLATED_FILENAME, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(unique_sentences))
        if unique_sentences:
            f.write('\n')

    # NEW: console summary
    total_count = len(translated_sentences) + len(untranslated_sentences)
    print(f"Total sentences:                     {total_count}")
    print(f"Translated sentences (full count):   {len(translated_sentences)}")
    print(f"Fully untranslated unique sentences: {len(unique_sentences)}")


if __name__ == '__main__':
    translate_srt_partial(file, db, OUTPUT_FILENAME)