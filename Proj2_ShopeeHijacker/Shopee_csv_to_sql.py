import pandas as pd
import sqlite3
import os

# 1. Target your Shopee CSV (Update the name to match yours)
csv_filename = 'shopee_mechanical_keyboard_3_pages.csv' 

if os.path.exists(csv_filename):
    df = pd.read_csv(csv_filename)
    
    # 2. Connect to the same database (Digital Warehouse)
    conn = sqlite3.connect('market_intelligence.db')
    
    # 3. Load into a dedicated table
    # We use 'if_exists=replace' to keep it clean, or 'append' for a history
    df.to_sql('shopee_products', conn, if_exists='replace', index=False)
    
    conn.close()
    print(f"✅ Migrated {len(df)} products to the 'shopee_products' table!")
else:
    print(f"❌ File {csv_filename} not found. Check your folder!")