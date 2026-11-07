import glob

file = glob.glob("*.txt")[0]
print(file)

def extract_paired_data(input_filename, output_filename):
    with open(input_filename, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    blocks = []
    current_block = []

    # Group lines into blocks, ignoring empty lines or lines with just spaces/tabs
    for line in lines:
        if not line.strip():  # Line is empty or contains only spaces/tabs
            if current_block:
                blocks.append(current_block)
                current_block = []
        else:
            current_block.append(line.strip())
            
    # Don't forget the last block if the file doesn't end with a newline
    if current_block:
        blocks.append(current_block)

    total_blocks = len(blocks)
    paired_blocks = []

    for block in blocks:
        # Keep only blocks that contain a complete pair (exactly 2 lines)
        if len(block) == 2:
            paired_blocks.append('\n'.join(block))

    fetched_blocks = len(paired_blocks)
    filtered_out = total_blocks - fetched_blocks

    # Save the result to a new file
    filtered_content = '\n\n'.join(paired_blocks)
    with open(output_filename, 'w', encoding='utf-8') as file:
        file.write(filtered_content + '\n')

    # Print summary
    print("=== Processing Summary ===")
    print(f"Total blocks processed: {total_blocks}")
    print(f"Fetched paired blocks:  {fetched_blocks}")
    print(f"Filtered out blocks:    {filtered_out}")
    print(f"Saved successfully to:  {output_filename}")

if __name__ == "__main__":
    extract_paired_data(file,  'dataset.txt')
