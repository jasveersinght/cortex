import subprocess, sys

result = subprocess.run(
    [sys.executable, 'main.py'],
    capture_output=True,
    text=True,
    cwd=r'c:\Users\jasve\project1-brain-1'
)

with open('C:/Users/jasve/pipeline_output.txt', 'w', encoding='ascii', errors='replace') as f:
    f.write(result.stdout)
    if result.stderr:
        f.write('\n--- STDERR ---\n')
        f.write(result.stderr)

print("Exit code:", result.returncode)
print("Done.")
