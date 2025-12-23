# test_extractor.py
import os
import sys

# Add the parent directory to the system path to allow importing manage_agenda
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from manage_agenda.utils_web import extract_domain_and_path_from_url

def main():
    try:
        script_dir = os.path.dirname(__file__)
        file_path = os.path.join(script_dir, "test.txt")
        with open(file_path, "r") as f:
            for line in f:
                url = line.strip()
                if url:
                    extracted_path = extract_domain_and_path_from_url(url)
                    print(f"URL: {url}")
                    print(f"Extracted: {extracted_path}\n")
    except FileNotFoundError:
        print("Error: test.txt not found. Please make sure the file exists.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

