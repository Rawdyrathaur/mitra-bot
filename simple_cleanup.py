import sqlite3
import shutil
from datetime import datetime

# Create backup
backup_path = f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
shutil.copy2('sam_bot_production.db', backup_path)
print(f'Backup created: {backup_path}')

# Clear the data
conn = sqlite3.connect('sam_bot_production.db')
cursor = conn.cursor()

print('Before cleanup:')
print('Documents:', cursor.execute('SELECT COUNT(*) FROM documents').fetchone()[0])
print('Knowledge chunks:', cursor.execute('SELECT COUNT(*) FROM knowledge_chunks').fetchone()[0])

# Clear knowledge chunks first
cursor.execute('DELETE FROM knowledge_chunks')
print('Knowledge chunks cleared')

# Clear documents
cursor.execute('DELETE FROM documents')
print('Documents cleared')

conn.commit()

print('After cleanup:')
print('Documents:', cursor.execute('SELECT COUNT(*) FROM documents').fetchone()[0])
print('Knowledge chunks:', cursor.execute('SELECT COUNT(*) FROM knowledge_chunks').fetchone()[0])

conn.close()
print('Cleanup complete!')
