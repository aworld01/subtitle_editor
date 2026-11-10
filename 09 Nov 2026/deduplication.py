import os, re, glob

OUTPUT_FILE = "unpaired_sentences.txt"

# Skip the output file and any "unpaired_sentences*" copies so they are
# never treated as input (and never get overwritten/emptied).
files = [
    f for f in glob.glob('*.txt')
    if f != OUTPUT_FILE and not f.startswith('unpaired_sentences')
]


def parse_file(filepath):
    """
    Parse a file into blocks.
    Each block = (english, hindi_or_None)
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f]

    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        english = line
        hindi = None
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and re.search(r'[\u0900-\u097F]', next_line):
                hindi = next_line
                i += 2
            else:
                i += 1
        else:
            i += 1

        blocks.append((english, hindi))
    return blocks


def write_blocks(blocks, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for english, hindi in blocks:
            f.write(english + "\n")
            if hindi:
                f.write(hindi + "\n")
            f.write("\n")


def main():
    # 1. Read all input files, collect pairs + unpaired, track seen English sentences
    file_pairs = {}     # path -> list of paired blocks (unique within that file)
    unpaired_all = []   # all unpaired English lines
    seen_pairs = set()  # global dedupe for paired sentences

    for path in files:
        if not os.path.exists(path):
            print(f"⚠️  File not found: {path}")
            continue

        blocks = parse_file(path)
        kept = []

        for english, hindi in blocks:
            key = english.strip().lower()

            if hindi is None:
                # Unpaired → collect for new file
                unpaired_all.append(english)
                continue

            # Paired → keep only if not seen globally
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            kept.append((english, hindi))

        file_pairs[path] = kept

    # 2. Dedupe unpaired list too (case-insensitive)
    seen_unpaired = set()
    unpaired_unique = []
    for line in unpaired_all:
        key = line.strip().lower()
        if key in seen_unpaired:
            continue
        seen_unpaired.add(key)
        unpaired_unique.append(line)

    # 3. Rewrite original files with only unique paired sentences
    for path, blocks in file_pairs.items():
        write_blocks(blocks, path)
        print(f"✏️  {path}: kept {len(blocks)} unique paired block(s)")

    # 4. Write unpaired sentences to output file (blank line after each sentence)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for line in unpaired_unique:
            f.write(line + "\n\n")
    print(f"📄 {len(unpaired_unique)} unpaired sentence(s) written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()