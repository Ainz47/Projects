import requests
import xml.etree.ElementTree as ET
import pandas as pd
import time
import os
import sys

# --- 1. NEW IMPORT FOR AZURE ---
from azure.storage.blob import BlobServiceClient

# --- 2. AZURE UPLOAD HELPER FUNCTION ---
def upload_to_azure(filename):
    conn_str = os.environ.get("AZURE_CONNECTION_STRING")
    if not conn_str:
        print("WARNING: No Azure Connection String found in environment. Skipping upload.")
        return
    
    print(f"Initiating direct upload to Azure for {filename}...")
    try:
        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        blob_client = blob_service_client.get_blob_client(container="raw-parquet-chunks", blob=f"raw/{filename}")
        
        with open(filename, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        print(f"--> Cloud Upload Complete: raw/{filename}")
    except Exception as e:
        print(f"ERROR uploading to Azure: {e}")
        sys.exit(1)
# ---------------------------------------


# Configuration
BASE_URL = "http://export.arxiv.org/api/query"
SEARCH_QUERY = "cat:math.*"
RESULTS_PER_ITERATION = 1000
CHUNK_SIZE = 10000
SLEEP_TIME = 3  # seconds

def fetch_arxiv_data():
    start_index = 0
    records_collected = []
    chunk_counter = 1
    total_downloaded = 0
    
    print("Starting data extraction from arXiv...")
    
    while True: 
        print(f"Fetching records {start_index} to {start_index + RESULTS_PER_ITERATION}...")
        
        # 1. Build the API request
        params = {
            'search_query': SEARCH_QUERY,
            'start': start_index,
            'max_results': RESULTS_PER_ITERATION,
            'sortBy' : 'submittedDate',
            'sortOrder': 'ascending'
        }
        
        response = requests.get(BASE_URL, params=params)
        if response.status_code != 200:
            print(f"Error fetching data: {response.status_code}. Ending extraction.")
            break
        
        #2. Parse the XML response
        root = ET.fromstring(response.content)
        entries = root.findall('{http://www.w3.org/2005/Atom}entry')
        
        if not entries:
            print('No more records found. Ending extraction.')
            break
        
        #3. Extract relevant data
        for entry in entries:
            # Helper function to find text safely
            def get_text(tag):
                element = entry.find(f'{{http://www.w3.org/2005/Atom}}{tag}')
                return element.text if element is not None else None
            
            authors = [author.find('{http://www.w3.org/2005/Atom}name').text
                       for author in entry.findall('{http://www.w3.org/2005/Atom}author')]
            
            # Find the PDF link
            pdf_url = None
            for link in entry.findall('{http://www.w3.org/2005/Atom}link'):
                if link.attrib.get('title') == 'pdf':
                    pdf_url = link.attrib.get('href')
                    
            record = {
                'id' : get_text('id'),
                'title' : get_text('title').replace('\n', ' ').strip() if get_text('title') else None,
                'authors' : ','.join(authors) if authors else None,
                'published_date' : get_text('published'),
                'primary_category' : entry.find('{http://arxiv.org/schemas/atom}primary_category').attrib.get('term') if entry.find('{http://arxiv.org/schemas/atom}primary_category') is not None else None,
                'abstract' : get_text('summary').replace('\n', ' ').strip() if get_text('summary') else None,
                'pdf_url' : pdf_url
            }
            records_collected.append(record)
            total_downloaded += 1
            
        #4. Memory Management: Save to disk and clear RAM if we hit 10,000 records
        if len(records_collected) >= CHUNK_SIZE:
            filename = f'arxiv_data_chunk_{chunk_counter}.parquet'
            df = pd.DataFrame(records_collected)
            df.to_parquet(filename, index=False)
            print(f"--> Saved {filename} to disk. Total records so far:{total_downloaded}")
            
            # Upload this chunk to Azure!
            upload_to_azure(filename)
            
            #Clear the list to free up RAM!
            records_collected = []
            chunk_counter += 1
            
        start_index += RESULTS_PER_ITERATION
        
        #5. Rate limiting
        time.sleep(SLEEP_TIME)
    
    # Save any leftover records that didnt make a full 10000 chunk
    if records_collected:
        filename = f'arxiv_data_chunk_{chunk_counter}.parquet'
        df = pd.DataFrame(records_collected)
        df.to_parquet(filename, index=False)
        print(f"--> Saved final chunk {filename} to disk.")
        
        # Upload the final chunk to Azure!
        upload_to_azure(filename)
        
if __name__ == "__main__":
    fetch_arxiv_data()