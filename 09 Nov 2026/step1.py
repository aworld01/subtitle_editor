import re, glob

file = glob.glob("*.srt")[0]

def srt2txt(srt_filename, txt_filename):
    with open(srt_filename, 'r', encoding='utf-8') as file:
        content = file.read()

    # Split the SRT file into individual subtitle blocks[span_1](start_span)[span_1](end_span)
    blocks = re.split(r'\n\s*\n', content.strip())
    transcript_lines = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            text_lines = lines[2:]
            # Join wrapped lines within the same subtitle cue with a space[span_2](start_span)[span_2](end_span)
            text_block = ' '.join(text_lines)
            transcript_lines.append(text_block)

    # Combine all blocks into a continuous text stream[span_3](start_span)[span_3](end_span)
    full_text = ' '.join(transcript_lines)
    full_text = re.sub(r'\s+', ' ', full_text)

    # Split lines only at punctuation, keeping it[span_4](start_span)[span_4](end_span)
    sentences = re.split(r'(?<=[.?!])\s+', full_text)
    
    # Clean sentences and remove duplicates while preserving original order[span_5](start_span)[span_5](end_span)
    seen = set()
    cleaned_sentences = []
    for s in sentences:
        cleaned = s.strip()
        if cleaned:
            if cleaned not in seen:
                seen.add(cleaned)
                cleaned_sentences.append(cleaned)

    # Print summary statistics to the console
    total_count = len([s for s in sentences if s.strip()])
    unique_count = len(cleaned_sentences)
    duplicates_removed = total_count - unique_count

    print(f"--- SRT Processing Summary ---")
    print(f"Total Sentences (Parsed): {total_count}")
    print(f"Unique Sentences (Kept):   {unique_count}")
    print(f"Duplicates Removed:        {duplicates_removed}")
    print(f"Output saved to:           {txt_filename}")

    # Write the result to the output file with double newlines separating each sentence/turn[span_6](start_span)[span_6](end_span)
    with open(txt_filename, 'w', encoding='utf-8') as file:
        file.write('\n\n'.join(cleaned_sentences))

if __name__ == '__main__':
    srt2txt(file, 'clean_data.txt')