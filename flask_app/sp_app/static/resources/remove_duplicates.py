import argparse
from Bio import SeqIO

def find_duplicates(fasta_file):
    sequences = {}
    duplicates = {}

    for record in SeqIO.parse(fasta_file, "fasta"):
        sequence = str(record.seq)
        if sequence in sequences:
            if sequence not in duplicates:
                duplicates[sequence] = [sequences[sequence], record.id]
            else:
                duplicates[sequence].append(record.id)
        else:
            sequences[sequence] = record.id

    return sequences, duplicates

def write_output(unique_sequences, duplicate_sequences, output_file):
    with open(output_file, "w") as output_handle:
        for sequence, ids in unique_sequences.items():
            if sequence in duplicate_sequences:
                duplicate_ids = "/".join(set(duplicate_sequences[sequence]))
                output_handle.write(f">{duplicate_ids}\n")
                output_handle.write(f"{sequence}\n")
            else:
                output_handle.write(f">{ids}\n")
                output_handle.write(f"{sequence}\n")

def main():
    parser = argparse.ArgumentParser(description="Find duplicate sequences in a FASTA file.")
    parser.add_argument("input_file", help="Input FASTA file")
    parser.add_argument("output_file", help="Output FASTA file")
    args = parser.parse_args()

    fasta_file = args.input_file
    output_file = args.output_file

    unique_sequences, duplicate_sequences = find_duplicates(fasta_file)
    write_output(unique_sequences, duplicate_sequences, output_file)

    print(f"Total number of sequences: {len(list(SeqIO.parse(fasta_file, 'fasta')))}.")
    print(f"Number of sequences under several headers: {len(duplicate_sequences)}.")
    print(f"Unique sequences are written to {output_file}: {len(unique_sequences)}.")

if __name__ == "__main__":
    main()