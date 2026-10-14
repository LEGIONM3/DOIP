from pathlib import Path

services = [f.stem for f in Path("src/services").glob("*.ts") if not f.name.endswith(".test.ts")]
src_files = list(Path("src/routes").glob("*.tsx")) + list(Path("src/components").glob("**/*.tsx"))
src_content = "\n".join(f.read_text(encoding="utf-8") for f in src_files)

connected_count = 0
disconnected_count = 0

print("=== Frontend Service Connection Audit ===")
for s in services:
    referenced = f"services/{s}" in src_content or f"services/{s}.ts" in src_content or f"services/{s}\"" in src_content or f"services/{s}'" in src_content
    status = "CONNECTED" if referenced else "DISCONNECTED / UNUSED IN UI"
    if referenced:
        connected_count += 1
    else:
        disconnected_count += 1
    print(f"  {s:20s}: {status}")

print(f"\nSummary: {connected_count} Connected, {disconnected_count} Disconnected / Unused in UI")
