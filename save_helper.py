"""Private elevated save worker. Invoked only after a user-confirmed save fails for permission."""
from pathlib import Path
import json
import sys

# -I excludes cwd and PYTHONPATH; import only the installed application directory.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ff11reader.elevation import execute_request


def main():
    if len(sys.argv)!=3:return 2
    request=Path(sys.argv[1]);result=request.with_suffix('.result.json')
    try:
        backup=execute_request(request,sys.argv[2])
        response={'status':'verified','backup':str(backup)};code=0
    except Exception as exc:
        response={'status':'failed','error':str(exc)};code=1
    with result.open('x',encoding='utf-8') as stream:json.dump(response,stream,ensure_ascii=False)
    return code

if __name__=='__main__':raise SystemExit(main())
