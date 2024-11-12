import os
from datetime import datetime, timedelta

def delete_old_logs(archived_file_path):
    current_date = datetime.now().date()
    one_day_ago = current_date - timedelta(days=1)

    # Read existing logs and filter out old logs
    with open(archived_file_path, 'r') as archived_file:
        lines = archived_file.readlines()

    with open(archived_file_path, 'w') as archived_file:
        for line in lines:
            # Extract the date from the log line
            date_str = line.split(' --- ')[0]
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            # Write back logs that are not older than one day and are not empty
            if log_date >= one_day_ago and line.strip():
                archived_file.write(line)

def run(source_file_path, destination_file_path):
    try:
        with open(source_file_path, 'r') as source_file:
            lines = source_file.readlines()  # Read all lines from the source file

            if lines:
                with open(destination_file_path, 'a') as destination_file:
                    current_date = datetime.now().strftime('%Y-%m-%d')  # Only the date is written
                    for line in lines:
                        # Write each entry with the current date
                        destination_file.write(f"{current_date} --- {line.strip()}\n")

        # Clear the source file after appending
        with open(source_file_path, 'w') as source_file:
            source_file.truncate(0)  # Clear the file contents

        # Immediately delete old logs after processing
        delete_old_logs(destination_file_path)

    except IOError as e:
        print(f"An I/O error occurred: {e}")

if __name__ == "__main__":
    run('/home/kvmd-webterm/postcodelog.txt', '/home/kvmd-webterm/archived_logs.txt')  
