# diag_worker_import.py
import sys
import inspect

print("[diag] sys.path:", sys.path)
try:
    import app.tasks as tasks
    print("[diag] Imported app.tasks successfully")
except Exception as e:
    print("[diag] Failed to import app.tasks:", e)
    raise

# list all callables in tasks
funcs = [name for name, obj in inspect.getmembers(tasks) if inspect.isfunction(obj)]
print("[diag] Functions in app.tasks:", funcs)
