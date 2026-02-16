import requests
import pandas as pd

api_url = "https://api.schoolspring.com/api/Jobs/GetPagedJobsWithSearch?domainName=&keyword=&location=&category=&gradelevel=&jobtype=&organization=&swLat=&swLon=&neLat=&neLon=&page=1&size=25&sortDateAscending=false"

print("Fetching data from API...")
response = requests.get(api_url)
data = response.json()

# 1. Open the 'value' box
value_box = data.get('value', {})

# 2. Reach inside and open the 'jobsList' box!
actual_jobs_list = value_box.get('jobsList', [])

# 3. Hands the real list of jobs to Pandas
df = pd.DataFrame(actual_jobs_list)

# Print the columns to see if we got the real data!
print("\nHere are the REAL column names for the jobs:")
print(df.columns.tolist())

# Save it all to CSV 
df.to_csv('tcisd_ultimate_api_jobs.csv', index=False)