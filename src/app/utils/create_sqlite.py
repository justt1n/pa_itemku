import pandas as pd
import sqlite3

# Load the Excel file with both sheets
file_path = '/Users/admin/code/pa_tool/storage/Game_Item_Category_List.xls'  # Replace with your file path
sheet1 = pd.read_excel(file_path, sheet_name=1)  # Server-Faction table
sheet2 = pd.read_excel(file_path, sheet_name=0)  # Item Categories table

# Join the tables on the 'Game' column
joined_data = pd.merge(sheet1, sheet2, on='Game', how='inner')

# Add an 'id' column
joined_data.insert(0, 'id', range(1, len(joined_data) + 1))

# Display the first few rows of the result
print(joined_data)

# Optionally, save to a new Excel file
joined_data.to_excel('/Users/admin/code/pa_tool/storage/joined_output.xlsx', index=False)

# Save the result to a SQLite database
conn = sqlite3.connect('/Users/admin/code/pa_tool/storage/joined_data.db')
joined_data.to_sql('joined_table', conn, if_exists='replace', index=False)
conn.close()

print("Data has been joined and saved to both Excel and SQLite.")
