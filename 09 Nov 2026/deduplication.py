import os, re, glob

OUTPUT_FILE = "unpaired_sentences.txt"

# Skip the output file and any "unpaired_sentences*" copies so they are
# never treated as input. Existing entries in the output file are loaded
# at the start of each run and merged with any newly discovered unpaired
# sentences, so the file is only ever appended to (never lost/overwritten).
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


def load_existing_unpaired(path):
    """
    Load sentences already stored in the output file from previous runs.
    On disk each sentence is followed by a blank line, so any non-empty
    line is treated as a sentence.
    """
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def remove_empty_txt_files(paths=None):
    """
    Delete any empty .txt file, but never the persistent unpaired output
    (or its backups / copies, which share the 'unpaired_sentences' prefix).
    """
    if paths is None:
        paths = glob.glob('*.txt')

    removed = []
    for path in paths:
        if path.startswith('unpaired_sentences'):
            continue
        if os.path.isfile(path) and os.path.getsize(path) == 0:
            try:
                os.remove(path)
                removed.append(path)
                print(f"🗑️  Removed empty file: {path}")
            except OSError as e:
                print(f"⚠️  Could not remove {path}: {e}")

    if not removed:
        print("✅ No empty .txt files to remove.")
    return removed


def main():
    # 1. Read all input files, collect pairs + unpaired, track seen English sentences
    file_pairs = {}     # path -> list of paired blocks (unique within that file)
    unpaired_all = []   # all unpaired English lines found *this run*
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
                # Unpaired → collect for the output file
                unpaired_all.append(english)
                continue

            # Paired → keep only if not seen globally
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            kept.append((english, hindi))

        file_pairs[path] = kept

    # 2. Load sentences already saved by previous runs, then merge with new ones
    existing_unpaired = load_existing_unpaired(OUTPUT_FILE)
    existing_keys = {line.strip().lower() for line in existing_unpaired}
    combined = existing_unpaired + unpaired_all

    # Dedupe combined list (case-insensitive)
    seen_unpaired = set()
    unpaired_unique = []
    for line in combined:
        key = line.strip().lower()
        if not key or key in seen_unpaired:
            continue
        seen_unpaired.add(key)
        unpaired_unique.append(line)

    new_count = len(unpaired_unique) - len(existing_keys)

    # 3. Rewrite original files with only unique paired sentences
    for path, blocks in file_pairs.items():
        write_blocks(blocks, path)
        print(f"✏️  {path}: kept {len(blocks)} unique paired block(s)")

    # 4. Merge + persist unpaired sentences (additive across runs)
    if unpaired_unique:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for line in unpaired_unique:
                f.write(line + "\n\n")
        print(
            f"📄 {OUTPUT_FILE}: {len(unpaired_unique)} total unpaired "
            f"sentence(s) (+{new_count} new this run)"
        )
    else:
        print(f"📄 {OUTPUT_FILE}: no unpaired sentences found")

    # 5. Remove any empty .txt files (but never the persistent unpaired output)
    remove_empty_txt_files()


if __name__ == "__main__":
    main()