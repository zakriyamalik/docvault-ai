import re

# Read the file
with open('/app/app/api/documents.py', 'r') as f:
    content = f.read()

# Apply the fix
old_line = 'meta = json.loads(doc.get("meta_json") or "{}")'
new_code = '''meta_json = doc.get("meta_json") or "{}"
        if isinstance(meta_json, dict):
            meta = meta_json
        else:
            meta = json.loads(meta_json)'''

if old_line in content:
    content = content.replace(old_line, new_code)
    with open('/app/app/api/documents.py', 'w') as f:
        f.write(content)
    print("✅ Fix applied successfully!")
else:
    print("❌ Could not find line to fix")
    # Check if already fixed
    if "isinstance(meta_json" in content:
        print("File may already be fixed")
    else:
        print("ERROR: Fix not applied")
        exit(1)
